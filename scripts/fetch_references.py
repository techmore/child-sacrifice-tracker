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
import subprocess
import tempfile
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


POST_QUERIES = {
    "nih-reporter-hd000836": {
        "criteria": {"project_nums": ["R24HD000836"]},
        "include_fields": ["ApplId", "FiscalYear", "ProjectNum", "ProjectTitle",
                           "Organization", "AwardAmount"],
        "limit": 100,
    },
    "usaspending-hd000836-subawards": {
        "award_id": "ASST_NON_R24HD000836_075",
        "page": 1, "limit": 100, "sort": "action_date", "order": "desc",
    },
}


def download(source, folder, expected_sha256):
    headers = {"User-Agent": UA}
    query = POST_QUERIES.get(source["id"])
    if query is not None:
        headers["Content-Type"] = "application/json"
    payload = json.dumps(query).encode() if query is not None else None
    request = urllib.request.Request(source["url"], headers=headers, data=payload)
    with urllib.request.urlopen(request, timeout=35) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
    identifier = source["id"]
    if content_type == "text/html" and b"<title>Checking your browser - reCAPTCHA</title>" in body:
        raise ValueError("Server returned a verification page")
    if content_type == "text/html" and len(body) < 10_000:
        if (b"?bm-verify=" in body or b"<title>Making sure you&#39;re not a bot!" in body
                or b'const challengeDomain = "pubmed.ncbi.nlm.nih.gov"' in body):
            raise ValueError("Server returned a verification page")
    if identifier == "bearak-2022-supp-tables":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            body = archive.read("bmjgh-2021-007151supp001.xlsx")
    excerpt_pages = {
        "ocda-fetal-tissue-judgment-2017": "52-58",
        "fda-abr-order-2018": "28-36,161,166",
        "doj-trafficking-report-fy2006": "90",
        "nih-revitalization-act-1993": "10-11",
    }
    if identifier in excerpt_pages:
        # Retain the cited records from the longer source.
        with tempfile.TemporaryDirectory() as directory:
            original = pathlib.Path(directory) / "original.pdf"
            excerpt = pathlib.Path(directory) / "excerpt.pdf"
            original.write_bytes(body)
            result = subprocess.run(
                ["qpdf", "--deterministic-id", "--empty", "--pages",
                 str(original), excerpt_pages[identifier], "--", str(excerpt)],
                capture_output=True,
            )
            if result.returncode:
                raise ValueError("Could not extract the cited pages")
            body = excerpt.read_bytes()
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
        paths = []
        prior = None
    expected_sha256 = (prior.get("sha256") or prior.get("expected_sha256")) if prior else None
    if len(paths) > 1:
        raise ValueError(f'Multiple local copies for {source["id"]}')
    saved = None
    if paths:
        path = paths[0]
        date = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
        record = file_record(path, prior["retrieved"] if prior and prior["status"] == "saved" else date)
        if not expected_sha256 or expected_sha256 == record["sha256"]:
            saved = {**source, **record}
            if not refresh:
                return saved
    try:
        path = download(source, folder, None if refresh else expected_sha256)
        for old_path in previous_paths:
            if old_path != path:
                old_path.unlink()
        return {**source, **file_record(path, datetime.date.today().isoformat())}
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        if saved:
            return {**saved, "refresh_error": str(error)}
        failure = {**source, "retrieved": datetime.date.today().isoformat(), "status": "failed", "error": str(error)}
        if expected_sha256:
            failure["expected_sha256"] = expected_sha256
        return failure


def write_site_bibliography(bibliography, manifest):
    records = []
    for source in bibliography:
        record = {key: source[key] for key in ("id", "title", "url")}
        capture = manifest.get(source["id"], {})
        if capture.get("url") != source["url"]:
            capture = {}
        archive = {"status": "unavailable"}
        if capture.get("retrieved"):
            archive["date"] = capture["retrieved"]
        if capture.get("status") == "saved":
            archive["status"] = "local"
            archive["sha256"] = capture["sha256"]
            path = pathlib.PurePosixPath(capture["file"])
            if (source["access"] == capture["access"] == "open"
                    and path.parts[:1] == ("open",) and ".." not in path.parts):
                archive["status"] = "public"
                archive["path"] = urllib.parse.quote(f"references/{path}")
        record["archive"] = archive
        records.append(record)
    (REPO / "docs/data/sources.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Redownload already archived sources")
    parser.add_argument("--index-only", action="store_true", help="Regenerate only the site's bibliography, without network access")
    parser.add_argument("--verify", action="store_true", help="Verify the local archive without downloading or writing files")
    parser.add_argument("--source", action="append", default=[], metavar="ID",
                        help="Download or verify selected source IDs. Repeat for more than one.")
    options = parser.parse_args()
    selected_ids = set(options.source)
    manifest = ROOT / "manifest.json"
    if options.verify:
        entries = json.loads(manifest.read_text(encoding="utf8"))
        missing = selected_ids - {entry["id"] for entry in entries}
        if missing:
            parser.error("Source IDs missing from the manifest: " + ", ".join(sorted(missing)))
        if selected_ids:
            entries = [entry for entry in entries if entry["id"] in selected_ids]
        invalid = []
        for entry in entries:
            path = ROOT / entry.get("file", "")
            if (entry["status"] != "saved" or not path.is_file()
                    or file_record(path, entry["retrieved"])["sha256"] != entry["sha256"]):
                invalid.append(entry["id"])
        print(f"{len(entries) - len(invalid)} of {len(entries)} archived source files verified")
        if invalid:
            parser.exit(1, "Missing or changed: " + ", ".join(invalid) + "\n")
        return
    with (ROOT / "sources.tsv").open(encoding="utf8", newline="") as file:
        bibliography = list(csv.DictReader(file, delimiter="\t"))
    with (ROOT / "country-profiles.tsv").open(encoding="utf8", newline="") as file:
        sources = bibliography + list(csv.DictReader(file, delimiter="\t"))
    ids = {s["id"] for s in sources}
    if len(ids) != len(sources):
        parser.error("Source IDs must be unique")
    missing = selected_ids - ids
    if missing:
        parser.error("Unknown source IDs: " + ", ".join(sorted(missing)))
    previous = {entry["id"]: entry for entry in json.loads(manifest.read_text(encoding="utf8"))} if manifest.exists() else {}
    if options.index_only:
        write_site_bibliography(bibliography, previous)
        return
    if selected_ids:
        sources = [source for source in sources if source["id"] in selected_ids]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda source: archive_source(source, previous, options.refresh), sources))
    archived = results
    if selected_ids:
        previous.update((entry["id"], entry) for entry in results)
        archived = list(previous.values())
    manifest.write_text(json.dumps(archived, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    write_site_bibliography(bibliography, {entry["id"]: entry for entry in archived})
    for result in results:
        error = result.get("refresh_error") or result.get("error")
        if error:
            print(result["id"], error)
    count = sum(entry["status"] == "saved" for entry in results)
    print(f"{count} of {len(results)} sources archived")
    if count != len(results) or any(entry.get("refresh_error") for entry in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
