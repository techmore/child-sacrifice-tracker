#!/usr/bin/env python3
"""Build reported county counts from locally archived state reports."""
import html
import json
from pathlib import Path
import re
import subprocess

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "references" / "private"
COUNT = r"[\d,]+"


def pdf_text(source):
    return subprocess.check_output(
        ["pdftotext", "-layout", str(ARCHIVE / f"{source}.pdf"), "-"], text=True
    )


def count(value):
    return int(value.replace(",", ""))


def counties(rows, expected):
    if len(rows) != expected or len(dict(rows)) != expected:
        raise ValueError(f"Expected {expected} distinct counties, got {len(rows)} rows")
    return [{"name": name, "count": value} for name, value in sorted(rows)]


def verify_total(rows, expected):
    total = sum(value for _, value in rows)
    if total != expected:
        raise ValueError(f"Expected county counts to sum to {expected}, got {total}")


def county_series(rows, years, expected):
    return {
        year: counties([(name, values[index]) for name, values in rows], expected)
        for index, year in enumerate(years)
    }


def arizona(source):
    table = pdf_text(source).split("Table 14. Abortions, live births", 1)[1]
    named = table.split(" Unknown", 1)[0]
    rows = [(name, count(value)) for name, value in re.findall(rf"^ +([A-Za-z ]+?) +({COUNT}) +\d+\.\d+ +{COUNT} ", named, re.M)]
    verify_total(rows, 12682 - 854)
    return {2024: counties(rows, 15)}


def florida(source):
    aliases = {"Dade": "Miami-Dade", "Desoto": "DeSoto", "St Johns": "St. Johns", "St Lucie": "St. Lucie"}
    rows = [
        (aliases.get(name, name), None if value == "*" else count(value))
        for name, value in re.findall(r"^\s*([A-Za-z ]+?)\s{2,}(\d+|\*) *$", pdf_text(source), re.M)
        if name != "Out of State"
    ]
    return {2025: counties(rows, 67)}


def hawaii(source):
    text = pdf_text(source).split("By Mother's State and County of Residence", 1)[1]
    table = text.split("County data was missing", 1)[0]
    names = ("Hawaii", "Honolulu", "Kauai", "Maui")
    years = {}
    for line in table.splitlines():
        fields = line.split()
        if len(fields) == 11 and re.fullmatch(r"20\d{2}", fields[0]):
            rows = [(name, None if value == "n/r" else count(value)) for name, value in zip(names, fields[3::2])]
            years[int(fields[0])] = counties(rows, 4)
    if set(years) != set(range(2015, 2025)):
        raise ValueError("Expected Hawaiʻi reports for 2015–2024")
    return years


def illinois(source):
    records = json.loads((ARCHIVE / f"{source}.json").read_text(encoding="utf-8"))
    results = {}
    for year in range(1995, 2021):
        reported = [
            (r["CountyName"], None if r["Abortions"] == "≤ 50" else count(r["Abortions"]))
            for r in records
            if r["Report_Year"] == year and r["CountyName"] != "Unknown"
        ]
        rows = dict(reported)
        if len(rows) != len(reported):
            raise ValueError(f"Duplicate Illinois county for {year}")
        if year >= 2015:
            # Illinois defines Cook as two reporting areas in those years.
            chicago, suburban = rows.pop("Chicago"), rows["Cook"]
            rows["Cook"] = None if chicago is None or suburban is None else chicago + suburban
        results[year] = counties(list(rows.items()), 102)
    return results


def kansas(source):
    pages = [page for page in pdf_text(source).split("\f") if page.lstrip().startswith("Table D9(A)")]
    table = "\n".join(pages).split("Peer Group\nFrontier")[0]
    aliases = {"Mcpherson": "McPherson"}
    rows = [
        (aliases.get(name, name), count(value))
        for name, value in re.findall(rf"^([A-Za-z ]+?) +({COUNT})(?: +{COUNT}){{9}} *$", table, re.M)
        if name != "Kansas"
    ]
    verify_total(rows, 4763 - 47)
    return {2024: counties(rows, 105)}


def michigan(source):
    text = (ARCHIVE / f"{source}.html").read_text(encoding="latin-1")
    tbody = text.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tbody, re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", cell)) for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) != 12:
            continue
        name, *values = [" ".join(cell.split()) for cell in cells]
        if name in ("Michigan", "Detroit", "Wayne Excluding Detroit"):
            continue
        # In this source, a dash explicitly indicates zero.
        rows.append((name, [0 if value == "-" else count(value) for value in values]))
    return county_series(rows, range(2013, 2024), 83)


def minnesota(source):
    pages = pdf_text(source).split("\f")
    aliases = {"Mcleod": "McLeod", "Lac qui Parle": "Lac Qui Parle", "Saint Louis": "St. Louis"}
    result = {}
    for year in (2023, 2024):
        title = f"Table 7. County of residence for women residing in Minnesota, {year}"
        page, = (page for page in pages if re.search(rf"{re.escape(title)}\s*\n", page))
        rows = []
        table = page.rsplit("Induced Abortions in Minnesota", 1)[0]
        for line in table.splitlines():
            fields = re.split(r" {2,}", line.strip())
            for name, value in zip(fields[::2], fields[1::2]):
                if name.lower() in {"state total", "unknown county"}:
                    continue
                if re.fullmatch(rf"{COUNT}|--", value):
                    rows.append((aliases.get(name, name), None if value == "--" else count(value)))
        result[year] = counties(rows, 87)
    return result


def nebraska(source):
    rows = []
    for line in pdf_text(source).splitlines():
        fields = re.split(r" {2,}", line.strip())
        if len(fields) >= 3 and fields[-2] == "Nebraska" and re.fullmatch(COUNT, fields[-1]):
            rows.append((fields[-3], count(fields[-1])))
    return {2025: counties(rows, 20)}


def north_carolina(source):
    rows = [
        (name, count(residents))
        for name, residents in re.findall(rf"^\s*\d+\s*:\s*(.+?) +{COUNT} +({COUNT}) *$", pdf_text(source), re.M)
        if name != "Unknown"
    ]
    # 27,146 resident reports, including 337 with unknown county.
    verify_total(rows, 26809)
    return {2023: counties(rows, 100)}


def ohio(source):
    title = "Table 5. Resident Induced Abortions Reported in Ohio, by County of Residence, 2016-2025"
    pages = [page for page in pdf_text(source).split("\f") if page.lstrip().startswith(title)]
    parsed = [
        (name, [count(value) for value in values.split()])
        for name, values in re.findall(rf"^ *([A-Za-z ]+?) +((?:{COUNT} +){{9}}{COUNT}) *$", "\n".join(pages), re.M)
        if name != "RESIDENCE"
    ]
    by_name = dict(parsed)
    totals = by_name.pop("OHIO")
    unknown = by_name.pop("Not reported")
    if len(parsed) != len(by_name) + 2:
        raise ValueError("Ohio contains duplicate county rows")
    years = range(2025, 2015, -1)
    # Table 5's published county rows differ from the adjusted state total by one in these two years.
    reported_differences = {2021: 1, 2020: -1}
    for index, year in enumerate(years):
        named_total = totals[index] - unknown[index] + reported_differences.get(year, 0)
        verify_total([(name, values[index]) for name, values in by_name.items()], named_total)
    return county_series(by_name.items(), years, 88)


def oregon(source):
    workbook = load_workbook(ARCHIVE / f"{source}.xlsx", read_only=True, data_only=True)
    years = {}
    for year in range(1995, 2026):
        cells = list(workbook[f"Abortion{year}"].iter_rows(max_col=2, values_only=True))
        table = cells[cells.index(("County of residence", "Total")) + 1:]
        total = table[0][1]
        data = [(name, 0 if value == "–" else value) for name, value in table[1:] if value is not None]
        # The published 2018 rows sum to one fewer than the worksheet total.
        verify_total(data, total - (year == 2018))
        rows = [(name, value) for name, value in data if name not in {"Unknown county", "Out of state"}]
        years[year] = counties(rows, 36)
    workbook.close()
    return years


def pennsylvania(source):
    pages = re.findall(r"Table 7\s+Induced Abortions Performed in Pennsylvania\s+by Residence and Age of Woman(.*?)(?:\f|$)", pdf_text(source), re.S)
    resident_rows = "\n".join(pages).split("Other States/Countries", 1)[0]
    rows = [
        (name, count(total))
        for name, total in re.findall(rf"^([A-Za-z ]+?) +({COUNT})(?: +{COUNT}){{9}} *$", resident_rows, re.M)
        if name not in {"Total Pennsylvania", "Unknown"}
    ]
    # 30,495 reports for Pennsylvania residents, including 12 with unknown county.
    verify_total(rows, 30483)
    return {2024: counties(rows, 67)}


def pennsylvania_occurrence():
    years = {}
    source_by_year = {}
    for year in range(2015, 2025):
        source = f"pa-abortion-occurrence-{year}"
        heading = rf"Table D-7\s+Induced Abortions by County of Procedure\s+Pennsylvania Occurrences, {year}"
        page, = (page for page in pdf_text(source).split("\f") if re.search(heading, page))
        table = page.split("Pennsylvania Department of Health --", 1)[0]
        rows = []
        for line in table.splitlines():
            # The report presents two side-by-side pairs of county and count columns.
            cells = re.split(r" {2,}", line.strip())
            rows.extend(
                (name, count(value))
                for name, value in zip(cells[::2], cells[1::2])
                if re.fullmatch(COUNT, value)
            )
        state_total, = (total for name, total in rows if name == "Pennsylvania")
        rows = [(name, value) for name, value in rows if name != "Pennsylvania"]
        verify_total(rows, state_total)
        years[year] = counties(rows, 67)
        source_by_year[year] = source
        print(f"{source}: {len(rows)} counties, {state_total:,} reported procedures")
    return {
        "source": source_by_year[max(source_by_year)],
        "sourceByYear": source_by_year,
        "scope": "Induced abortions reported in Pennsylvania, grouped by county where the procedure occurred, including patients who lived outside Pennsylvania. Pennsylvania Vital Statistics, Table D-7.",
        "years": years,
    }


def washington(source):
    years = {}
    for year, expected in ((2002, 25446 - 10), (2005, 24162 - 8)):
        text = pdf_text(f"wa-abortion-counties-{year}")
        table, = (page for page in text.split("\f") if re.match(r"Table (02-)?15\. Birth and Abortion Indicators", page))
        rows = [
            (name, count(value))
            for name, value in re.findall(rf"^([A-Za-z ]+?) +{COUNT} +{COUNT} +({COUNT}) +(?:{COUNT}|\*) +", table, re.M)
            if name != "State Total"
        ]
        verify_total(rows, expected)
        years[year] = counties(rows, 39)
    return years


SOURCES = {
    "04": (
        "az-abortion-counties-2024", arizona,
        "Arizona residents with abortions reported in Arizona, Table 14.",
    ),
    "12": (
        "fl-abortion-counties-2025", florida,
        "Florida reports by patient county of residence. The agency suppresses county counts of 20 or fewer.",
    ),
    "15": (
        "hi-abortion-counties-2015-2024", hawaii,
        "Reported abortions among Hawaiʻi residents. The source publishes data for four counties and excludes records with unknown county.",
    ),
    "17": (
        "il-abortion-counties-1995-2020", illinois,
        "Illinois residents with terminations reported in Illinois. The archive suppresses counts of 50 or fewer. From 2015, the Cook County figure sums the Chicago and suburban Cook reporting areas.",
    ),
    "20": (
        "ks-abortion-counties-2024", kansas,
        "Kansas resident abortions reported to the state, Table D9(A). Out-of-state reporting may lack county of residence.",
    ),
    "26": (
        "mi-abortion-counties-2013-2023", michigan,
        "Michigan residents with induced abortions reported in Michigan, Table H-1.",
    ),
    "27": (
        "mn-abortion-counties-2024", minnesota,
        "Minnesota residents with induced abortions reported in Minnesota, Table 7. The agency suppresses county counts of 0 to 5. The report includes revised 2023 data.",
    ),
    "31": (
        "ne-abortion-counties-2025", nebraska,
        "Nebraska residents with abortions reported in Nebraska. The state publishes county figures only where it recorded at least six cases.",
    ),
    "37": (
        "nc-abortion-counties-2023", north_carolina,
        "North Carolina's reported induced abortions, using the resident column of Table 6.",
    ),
    "39": (
        "oh-abortion-counties-2025", ohio,
        "Ohio residents with induced abortions reported in Ohio, Table 5. In 2020 and 2021 the published county sums differ by one from the state total after excluding unknown residence.",
    ),
    "41": (
        "or-abortion-counties-1995-2025", oregon,
        "Oregon residents with abortions reported in Oregon. These are the final annual totals from the state's workbook. The published 2018 rows sum to one fewer than the worksheet total.",
    ),
    "42": (
        "pa-abortion-counties-2024", pennsylvania,
        "Pennsylvania residents with induced abortions reported in Pennsylvania, Table 7, all ages.",
    ),
    "53": (
        "wa-abortion-counties-2002", washington,
        "Washington resident abortions in the state vital statistics reports, Table 15. The totals include reported procedures obtained out of state.",
    ),
}


def main():
    data = {}
    for fips, (source, parse, scope) in SOURCES.items():
        years = parse(source)
        data[fips] = {"source": source, "scope": scope, "years": years}
        if fips == "17":
            data[fips]["report"] = "il-abortion-county-archive"
        if fips == "53":
            data[fips]["sourceByYear"] = {year: f"wa-abortion-counties-{year}" for year in years}
        print(f"{source}: {min(years)}–{max(years)}, {len(years[max(years)])} counties")
    data["42"]["occurrence"] = pennsylvania_occurrence()
    (ROOT / "docs" / "data" / "counties.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
