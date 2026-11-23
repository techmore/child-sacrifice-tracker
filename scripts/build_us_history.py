#!/usr/bin/env python3
"""Build the supplemental US history from archived CDC and Guttmacher tables."""

import json
from pathlib import Path
import re
import subprocess

import openpyxl


ROOT = Path(__file__).resolve().parent.parent
OPEN = ROOT / "references/open"
PRIVATE = ROOT / "references/private"

CDC_SOURCES = [
    {
        "id": "cdc-abortion-1972",
        "label": "CDC 1972 surveillance summary, table 1 (1969–1972)",
        "url": "https://stacks.cdc.gov/view/cdc/59311/cdc_59311_DS1.pdf",
    },
    {
        "id": "cdc-abortion-2005",
        "label": "CDC 2005 surveillance report, table 2 (1973–2005)",
        "url": "https://www.cdc.gov/mmwr/preview/mmwrhtml/ss5713a1.htm#tab2",
    },
    {
        "id": "cdc-abortion-2014",
        "label": "CDC 2014 surveillance report, table 1 (2006–2012)",
        "url": "https://www.cdc.gov/mmwr/volumes/66/ss/ss6625a1.htm#T1_down",
    },
    {
        "id": "cdc-abortion-2022",
        "label": "CDC 2022 surveillance report, table 1 (2013–2022)",
        "url": "https://www.cdc.gov/mmwr/volumes/73/ss/ss7307a1.htm#T1_down",
    },
]
RECENT_SOURCES = [
    {
        "id": "guttmacher-full-year-2025",
        "label": "Guttmacher Monthly Abortion Provision Study, full-year 2025 report",
        "url": "https://www.guttmacher.org/report/full-year-estimates-show-overall-stability-abortion-incidence-decreased-travel-increased-telehealth-provision",
    },
    {
        "id": "guttmacher-full-year-2025-appendix",
        "label": "Guttmacher appendix, 2023–2025 values and 90% uncertainty intervals (XLSX)",
        "url": "https://www.guttmacher.org/sites/default/files/report_downloads/Abortions%20and%20travel%20for%20care%20in%20US%20states%2C%202023%2C%202024%20and%202025.xlsx",
    },
]


def number(value):
    return int(value.replace(",", ""))


def early_cdc():
    text = subprocess.run(
        ["pdftotext", "-layout", OPEN / "cdc-abortion-1972.pdf", "-"],
        check=True, capture_output=True, text=True,
    ).stdout
    # Table 1 groups four annual values on each line.
    areas = re.search(r"Complete Abortion Data\s+are Reported\*\s+([0-9 \t]+)", text)[1]
    counts = re.search(r"Reported to CDC[ \t]+([0-9, \t]+)", text)[1]
    return [
        {"year": year, "abortions": number(count), "areas": int(area)}
        for year, count, area in zip(range(1969, 1973), counts.split(), areas.split(), strict=True)
    ]


def cdc_2005():
    html = (OPEN / "cdc-abortion-2005.html").read_text(encoding="windows-1252")
    # CDC embeds this historical table as an image with a text transcript in its alt text.
    transcript = html.split('name = "tab2"', 1)[1].split("All reporting areas\n", 1)[1]
    transcript = transcript.split("46 Reporting areas", 1)[0]
    rows = re.findall(r"^(\d{4})[^\n]*\n([\d,]+)\n[^\n]+\n[^\n]+\n(\d+)\n(\d+)$", transcript, re.M)
    return [
        {"year": int(year), "abortions": number(count), "areas": int(agency) + int(facilities)}
        for year, count, agency, facilities in rows
    ]


def cdc_table_1(report, years, area_counts):
    html = (OPEN / f"cdc-abortion-{report}.html").read_text(encoding="utf8")
    table = html.split('id="T1_down"', 1)[1].split("</table>", 1)[0]
    rows = re.findall(
        r'<td\b[^>]*>\s*(\d{4})\s*</td>\s*<td\b[^>]*>\s*([\d,]+)',
        table,
    )
    return [
        {"year": int(year), "abortions": number(count), "areas": area_counts.get(int(year), 49)}
        for year, count in rows if int(year) in years
    ]


def guttmacher_recent():
    path = PRIVATE / "guttmacher-full-year-2025-appendix.xlsx"
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Change_2023_2024_2025"]
        records = sheet.iter_rows(min_row=3, max_col=7, values_only=True)
        header = next(records)
        if header[1:7:2] != (2023, 2024, 2025):
            raise ValueError("Unexpected year headers in Guttmacher appendix")
        results = {}
        for abbr, *values in records:
            if not isinstance(abbr, str) or not re.fullmatch(r"[A-Z]{2}", abbr):
                continue
            if abbr in results:
                raise ValueError(f"Duplicate Guttmacher appendix row for {abbr}")
            rows = []
            for index in (0, 2, 4):
                year, count = header[index + 1], values[index]
                low, high = map(number, re.findall(r"[\d,]+", values[index + 1]))
                if not isinstance(count, int) or not 0 <= low <= count <= high:
                    raise ValueError(f"Invalid uncertainty interval for {abbr} {year}")
                rows.append({"year": year, "abortions": count, "low": low, "high": high})
            results[abbr] = rows
        national = results.pop("US")
        expected = {row["abbr"] for row in json.loads((ROOT / "docs/data/states.json").read_text())}
        if results.keys() != expected:
            raise ValueError("Expected exactly 50 states and D.C. in Guttmacher appendix")
        return national, results
    finally:
        workbook.close()


def main():
    national, states = guttmacher_recent()
    # The table 1 footnotes identify non-reporting areas out of 52: the states,
    # DC and NYC. In 2006 only CA and NH did not report in the revised figures.
    cdc = early_cdc() + [row for row in cdc_2005() if row["year"] >= 1973]
    cdc += cdc_table_1(2014, range(2006, 2013), {2006: 50})
    cdc += cdc_table_1(2022, range(2013, 2023), {2016: 48, 2021: 48, 2022: 48})
    if [row["year"] for row in cdc] != list(range(1969, 2023)):
        raise ValueError("Expected one CDC row for every year from 1969 to 2022")
    data = {
        "cdc": {
            "label": "CDC reports from participating areas",
            "scope": (
                "Counts of legal induced abortions reported to CDC. Coverage varies by year. "
                "Early counts omit places without reports and abortions outside the legal system. "
                "California, Maryland, New Hampshire and New Jersey did not report for 2022."
            ),
            "sources": CDC_SOURCES,
            "rows": cdc,
        },
        "recent": {
            "label": "Guttmacher Monthly Abortion Provision Study",
            "scope": (
                "Estimated clinician-provided abortions, including telehealth where pills were "
                "received. Excludes self-managed abortions outside the formal health care system "
                "and abortions provided under exceptions in states with total bans. "
                "Ranges are 90% uncertainty intervals."
            ),
            "sources": RECENT_SOURCES,
            "rows": national,
            "states": states,
        },
    }
    output = ROOT / "docs/data/us-history.json"
    output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8")


if __name__ == "__main__":
    main()
