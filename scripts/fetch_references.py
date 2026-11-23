#!/usr/bin/env python3
"""Download every source in references/sources.tsv and record its checksum.

Open sources go to references/open (committed).
Copyrighted sources go to references/private (git-ignored).
"""
import csv, datetime, hashlib, io, json, mimetypes, pathlib, urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent / "references"
UA = "Mozilla/5.0 (reference-archiver)"
EXT = {"application/pdf": ".pdf", "text/html": ".html", "text/csv": ".csv",
       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"}

results = []
for row in csv.DictReader(open(ROOT / "sources.tsv", encoding="utf8"), delimiter="\t"):
    entry = {**row, "retrieved": datetime.date.today().isoformat()}
    try:
        with urllib.request.urlopen(urllib.request.Request(row["url"], headers={"User-Agent": UA}), timeout=60) as r:
            body = r.read()
            ctype = r.headers.get_content_type()
        if row["id"] == "bearak-2022-supp-tables":
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                body = z.read("bmjgh-2021-007151supp001.xlsx")
        if body[:4] == b"%PDF":
            ext = ".pdf"
        elif body[:2] == b"PK":
            ext = ".xlsx"
        elif row["id"].endswith("-csv"):
            ext = ".csv"
        else:
            ext = EXT.get(ctype) or mimetypes.guess_extension(ctype) or ".bin"
        folder = ROOT / row["access"]
        folder.mkdir(exist_ok=True)
        path = folder / f'{row["id"]}{ext}'
        path.write_bytes(body)
        entry.update(status="saved", file=str(path.relative_to(ROOT)), bytes=len(body),
                     sha256=hashlib.sha256(body).hexdigest())
    except Exception as e:
        entry.update(status="failed", error=str(e))
    results.append(entry)
    print(entry["status"], entry["id"], entry.get("bytes", entry.get("error")))

(ROOT / "manifest.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
print(sum(e["status"] == "saved" for e in results), "of", len(results), "saved")
