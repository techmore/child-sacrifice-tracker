#!/usr/bin/env python3
"""Download cited originals and build the offline archive and site source indexes."""
import argparse
import csv
import datetime
import hashlib
import io
import json
import mimetypes
import pathlib
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

REPO = pathlib.Path(__file__).resolve().parent.parent
ROOT = REPO / "references"
UA = "Mozilla/5.0"
EXT = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/json": ".json",
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def file_record(path, retrieved):
    with path.open("rb") as file:
        checksum = hashlib.file_digest(file, "sha256").hexdigest()
    return {
        "retrieved": retrieved,
        "status": "saved",
        "file": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": checksum,
    }


def download(source, folder, expected_sha256):
    request = urllib.request.Request(source["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=35) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
    identifier = source["id"]
    if identifier == "bearak-2022-supp-tables":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            body = archive.read("bmjgh-2021-007151supp001.xlsx")
    expected = pathlib.PurePosixPath(source.get("filename", urllib.parse.urlparse(source["url"]).path)).suffix
    if body.startswith(b"%PDF"):
        extension = ".pdf"
    elif body.startswith(b"PK"):
        extension = ".zip" if expected == ".zip" else ".xlsx"
    elif identifier.endswith("-csv"):
        if content_type == "text/html":
            raise ValueError("Expected CSV but the server returned HTML")
        extension = ".csv"
    else:
        extension = EXT.get(content_type) or mimetypes.guess_extension(content_type) or ".bin"
    if expected in {".pdf", ".xlsx", ".zip"} and expected != extension:
        raise ValueError(f"Expected {expected} but the server returned {extension}")
    if expected_sha256 and hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError("Download differs from the archived checksum. Use --refresh to accept a newer copy.")
    path = folder / source.get("filename", f"{identifier}{extension}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(body)
    temporary.replace(path)
    return path


def archive_source(source, previous, refresh):
    folder = ROOT / source["access"]
    folder.mkdir(exist_ok=True)
    if "filename" in source:
        file = folder / source["filename"]
        file.parent.mkdir(exist_ok=True)
        paths = [file] if file.is_file() else []
    else:
        paths = sorted(folder.glob(f'{source["id"]}.*'))
    prior = previous.get(source["id"])
    previous_paths = paths
    if prior and prior["url"] != source["url"]:
        if prior["status"] == "saved":
            paths = []
        prior = None
    if len(paths) > 1:
        raise ValueError(f'Multiple local copies for {source["id"]}')
    saved = None
    if paths:
        path = paths[0]
        date = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
        record = file_record(path, prior["retrieved"] if prior and prior["status"] == "saved" else date)
        if not prior or prior["status"] != "saved" or prior["sha256"] == record["sha256"]:
            saved = {**source, **record}
            if not refresh:
                return saved
    try:
        expected_sha256 = prior.get("sha256") if prior and not refresh else None
        path = download(source, folder, expected_sha256)
        for old_path in previous_paths:
            if old_path != path:
                old_path.unlink()
        return {**source, **file_record(path, datetime.date.today().isoformat())}
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        if saved:
            return {**saved, "refresh_error": str(error)}
        return {**source, "retrieved": datetime.date.today().isoformat(), "status": "failed", "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Redownload already archived sources")
    parser.add_argument("--index-only", action="store_true", help="Regenerate only the site's bibliography, without network access")
    options = parser.parse_args()
    with (ROOT / "sources.tsv").open(encoding="utf8", newline="") as file:
        bibliography = list(csv.DictReader(file, delimiter="\t"))
    with (ROOT / "country-profiles.tsv").open(encoding="utf8", newline="") as file:
        sources = bibliography + list(csv.DictReader(file, delimiter="\t"))
    ids = {s["id"] for s in sources}
    if len(ids) != len(sources):
        parser.error("Source IDs must be unique")
    (REPO / "docs/data/sources.json").write_text(
        json.dumps([{k: s[k] for k in ("id", "title", "url")} for s in bibliography], ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    if options.index_only:
        return
    manifest = ROOT / "manifest.json"
    previous = {entry["id"]: entry for entry in json.loads(manifest.read_text(encoding="utf8"))} if manifest.exists() else {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda source: archive_source(source, previous, options.refresh), sources))
    manifest.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    for result in results:
        error = result.get("refresh_error") or result.get("error")
        if error:
            print(result["id"], error)
    count = sum(entry["status"] == "saved" for entry in results)
    print(f"{count} of {len(results)} sources archived")


if __name__ == "__main__":
    main()
