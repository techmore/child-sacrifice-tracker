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

def michigan_occurrence():
    source = "mi-abortion-occurrence-2023"
    text = (ARCHIVE / f"{source}.html").read_text(encoding="latin-1")
    table = re.search(r"<caption>Table 29\b(.*?)</table>", text, re.S)[1]
    rows = []
    for line in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", line, re.S)
        if len(cells) == 3 and re.fullmatch(COUNT, cells[1].strip()):
            rows.append((html.unescape(cells[0]).strip(), count(cells[1].strip())))
    total = count(re.search(r"Total\s*</th>\s*<td[^>]*><strong>([\d,]+)</strong>", table)[1])
    verify_total(rows, total)
    return {
        "source": source,
        "scope": "Induced abortions reported in Michigan in 2023, grouped by county of the facility. Michigan DHHS, Table 29. The table lists 13 counties.",
        "years": {2023: counties(rows, 13)},
    }


def minnesota(source):
    aliases = {"Mcleod": "McLeod", "Lac qui Parle": "Lac Qui Parle", "Saint Louis": "St. Louis"}
    result = {}
    reports = {year: f"mn-abortion-counties-{year}" for year in range(2018, 2023)}
    reports.update({2023: source, 2024: source})
    pages = {report: pdf_text(report).split("\f") for report in dict.fromkeys(reports.values())}
    for year, report in reports.items():
        title = f"Table 7. County of residence for women residing in Minnesota, {year}"
        page, = (page for page in pages[report] if re.search(rf"{re.escape(title)}\s*\n", page, re.I))
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
    names = [row["name"] for row in result[2024]]
    if any([row["name"] for row in rows] != names for rows in result.values()):
        raise ValueError("Minnesota reports have inconsistent county names")
    return result


def nebraska(source):
    rows = []
    for line in pdf_text(source).splitlines():
        fields = re.split(r" {2,}", line.strip())
        if len(fields) >= 3 and fields[-2] == "Nebraska" and re.fullmatch(COUNT, fields[-1]):
            rows.append((fields[-3], count(fields[-1])))
    return {2025: counties(rows, 20)}


NYC_BOROUGHS = {
    "BRONX": "Bronx",
    "BROOKLYN": "Kings",
    "MANHATTAN": "New York",
    "QUEENS": "Queens",
    "STATEN ISLAND": "Richmond",
}
NYC_GROUP = re.compile(
    r"^\s*(NEW YORK CITY|MANHATTAN|BRONX|BROOKLYN|QUEENS|STATEN ISLAND|RICHMOND|"
    r"NON[- ]RESIDENTS|RESIDENCE UNKNOWN)(?![A-Z])"
)
NYC_INDUCED = re.compile(r"^\s*Induced Terminations[ .\t]+([\d,]+|[-—–])", re.I)


def new_york_city_rows(source, year):
    text = pdf_text(source)
    totals = {}
    for page in text.split("\f"):
        if not re.search(r"(?:Table\s*(?:26|PO[ .]*13)\b|Overall and by Borough of Residence and Age of Woman)", page, re.I):
            continue
        group = None
        values = {}
        for line in page.splitlines():
            header = NYC_GROUP.match(line)
            if header:
                group = {"NON RESIDENTS": "NON-RESIDENTS", "RICHMOND": "STATEN ISLAND"}.get(header[1], header[1])
                continue
            result = NYC_INDUCED.match(line)
            if group and result:
                value = result[1]
                if group in values:
                    raise ValueError(f"Duplicate county in {year} report")
                values[group] = int(value.replace(",", "")) if value[0].isdigit() else None
                group = None
        if all(name in values for name in NYC_BOROUGHS):
            if totals:
                raise ValueError(f"Found multiple candidate tables in {year} report")
            totals = values
    if not totals:
        raise ValueError(f"Failed to find all five boroughs in {year} report")
    citywide = totals.pop("NEW YORK CITY")
    if all(totals[borough] is not None for borough in NYC_BOROUGHS):
        computed = sum(value for value in totals.values() if value is not None)
        if computed != citywide:
            raise ValueError(f"NYC {year} county groups {computed} do not reconcile to {citywide}: {totals}")
    return counties([(county, totals[borough]) for borough, county in NYC_BOROUGHS.items()], 5)


def new_york_city():
    years = {}
    sources = {}
    for year in range(2000, 2024):
        source = f"nyc-abortion-counties-{year}"
        years[year] = new_york_city_rows(source, year)
        sources[year] = source
    return {
        "source": sources[max(years)],
        "sourceByYear": sources,
        "scope": "Reported induced terminations by borough of residence in New York City health department records. Coverage is limited to the city's five boroughs, which are equivalent to five New York counties. The city report excludes procedures outside New York City.",
        "years": years,
    }


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


def ohio_occurrence():
    source = "oh-abortion-counties-2025"
    title = "Table 2. Induced Abortions Reported in Ohio, by County of Occurrence, 2016-2025"
    page, = (page for page in pdf_text(source).split("\f") if page.lstrip().startswith(title))
    rows = [
        (name, [count(value) for value in values.split()])
        for name, values in re.findall(rf"^ *([A-Za-z/ ]+?) +((?:{COUNT} +){{9}}{COUNT}) *$", page, re.M)
        if name != "COUNTY OF OCCURRENCE"
    ]
    values_by_name = dict(rows)
    if len(rows) != len(values_by_name):
        raise ValueError("Ohio occurrence table contains duplicate rows")
    totals = values_by_name.pop("TOTAL")
    unknown = values_by_name.pop("Unknown/Not Reported")
    named_rows = [(name.removesuffix(" County"), values) for name, values in values_by_name.items()]
    years = range(2025, 2015, -1)
    # Ohio's Table 2 differs from its headline totals by two in these two years.
    published_differences = {2016: -2, 2017: 2}
    for index, year in enumerate(years):
        annual = [(name, values[index]) for name, values in named_rows]
        verify_total(annual, totals[index] - unknown[index] + published_differences.get(year, 0))
    return {
        "source": source,
        "scope": (
            "Induced abortions reported to the Ohio Department of Health, by county of occurrence, "
            "Table 2. The table publishes 22 named counties. Counts with no county reported are "
            "excluded, including telehealth prescriptions to Ohio residents. County totals differ "
            "from the report's statewide headline by two in 2016 and 2017."
        ),
        "years": county_series(named_rows, years, 22),
    }


def north_carolina_legacy_rows(text, county_names, year):
    """Read the side-by-side county columns in the 2000–2004 reports."""
    if f"North Carolina, {year}" not in text:
        raise ValueError(f"Unexpected North Carolina legacy occurrence report for {year}")
    expected_names = set(county_names) | {"Unknown"}
    name_pattern = "|".join(re.escape(name) for name in sorted(expected_names, key=lambda n: (-len(n), n)))
    row_pattern = re.compile(rf"(?<!\S)({name_pattern})(?= {{2,}})")
    parsed = {}
    for line in text.splitlines():
        matches = list(row_pattern.finditer(line))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            values = line[match.end():end].split()
            if len(values) not in (1, 2) or any(not re.fullmatch(rf"{COUNT}|-", value) for value in values):
                continue
            name = match[0]
            if name in parsed:
                raise ValueError(f"Duplicate North Carolina county for {year}: {name}")
            if len(values) == 1:
                if year != 2004 or name not in {"Burke", "Moore"}:
                    raise ValueError(f"Unexpected incomplete North Carolina county row for {year}: {name}")
                values.insert(0, "-")  # Both 2004 blanks align under occurrence.
            parsed[name] = [None if value == "-" else count(value) for value in values]
    if set(parsed) != expected_names:
        raise ValueError(f"Unexpected set of published North Carolina counties for {year}")
    occurrence_total, residence_total = re.search(rf"^Total +({COUNT}) +({COUNT}) ", text, re.M).groups()
    unknown_occurrence, unknown_residence = parsed.pop("Unknown")
    occurrence = [(name, values[0]) for name, values in parsed.items() if values[0] is not None]
    residence = [(name, values[1]) for name, values in parsed.items() if values[1] is not None]
    # In 2001 the occurrence headline equals the named subtotal even though
    # the table separately prints 785 cases with unknown county.
    unknown_in_total = 0 if year == 2001 else (unknown_occurrence or 0)
    verify_total(occurrence, count(occurrence_total) - unknown_in_total)
    verify_total(residence, count(residence_total) - (unknown_residence or 0))
    return occurrence, residence


def north_carolina_modern_rows(text, year):
    title = f"{year} North Carolina Reported Induced Abortions by County of Occurrence and Residence"
    if not text.lstrip().startswith(title):
        raise ValueError(f"Unexpected North Carolina county report for {year}")
    totals = re.search(rf"^ *NC TOTAL +({COUNT}) +({COUNT}) *$", text, re.M)
    rows = [
        (name, count(occurrence), count(residence))
        for name, occurrence, residence in re.findall(rf"^ *\d+ *: *(.+?) +({COUNT}) +({COUNT}) *$", text, re.M)
    ]
    unknown, = (values for values in rows if values[0] == "Unknown")
    by_basis = []
    for column in (1, 2):
        county_values = [(row[0], row[column]) for row in rows if row[0] != "Unknown"]
        verify_total(county_values, count(totals[column]) - unknown[column])
        by_basis.append(county_values)
    return tuple(by_basis)


def north_carolina():
    sources = {year: f"nc-abortion-counties-{year}" for year in (*range(2000, 2005), *range(2006, 2024))}
    modern = north_carolina_modern_rows(pdf_text(sources[2023]), 2023)
    county_names = {name for name, _ in modern[0]}
    occurrence, residence = {}, {}
    legacy_counts = {2000: 18, 2001: 16, 2002: 17, 2003: 17, 2004: 15}
    for year, source in sources.items():
        if year in legacy_counts:
            procedures, residents = north_carolina_legacy_rows(pdf_text(source), county_names, year)
        else:
            procedures, residents = modern if year == 2023 else north_carolina_modern_rows(pdf_text(source), year)
        occurrence[year] = counties(procedures, legacy_counts.get(year, 100))
        residence[year] = counties(residents, 99 if year == 2000 else 100)
    metadata = {
        "source": sources[2023],
        "sourceByYear": sources,
        "scopeSource": "nc-abortion-coverage-notes",
    }
    underreporting = " North Carolina reports that abortion forms were underreported from 2011 to 2014."
    return {
        **metadata,
        "scope": "Reports by county of patient residence in North Carolina. Dashes and blanks in the early source tables have no numeric counts." + underreporting,
        "years": residence,
        "occurrence": {
            **metadata,
            "scope": "Reports by county of procedure in North Carolina. Dashes and blanks in the 2000 to 2004 tables have no numeric counts. The 2001 state headline equals the named county total, with 785 additional reports printed under unknown county." + underreporting,
            "years": occurrence,
        },
    }


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


def pennsylvania_statewide(reports):
    observations = {}
    sources = []
    for report_year, first, last in ((2000, 1975, 1979), (2024, 1980, 2024)):
        heading = r"^ *Table D-1 *\n +Induced Abortions, Number and Rate, Pennsylvania Residents"
        page, = (p for p in reports[report_year] if re.search(heading, p, re.I | re.M))
        pattern = rf"^ *([12]\d{{3}}) +({COUNT}) +(\d+\.\d+) +({COUNT}) *$"
        rows = {
            int(year): {"year": int(year), "residence": count(resident),
                        "rate": float(rate), "occurrence": count(occurrence)}
            for year, resident, rate, occurrence in re.findall(pattern, page, re.M)
            if first <= int(year) <= last
        }
        if set(rows) != set(range(first, last + 1)):
            raise ValueError(f"Missing years in Pennsylvania {report_year} Table D-1")
        observations.update(rows)
        sources.append({"id": f"pa-abortion-occurrence-{report_year}", "first": first, "last": last})
    return {"rows": [observations[year] for year in sorted(observations)], "sources": sources}


def pennsylvania_occurrence_rows(pages, year):
    heading = rf"Table D-7\s+Induced Abortions by County of Procedure\s+Pennsylvania Occurrences, {year}"
    page, = (p for p in pages if re.search(heading, p, re.I))
    table = re.split(r"Pennsylvania Department of Health", page, maxsplit=1, flags=re.I)[0]
    rows = []
    for line in table.splitlines():
        # The report presents two side-by-side pairs of county and count columns.
        cells = re.split(r" {2,}", line.strip())
        rows.extend(
            (name, count(value))
            for name, value in zip(cells[::2], cells[1::2])
            if re.fullmatch(COUNT, value) and name.casefold() not in {"pennsylvania", "all counties"}
        )
    return rows


def pennsylvania_residence_rows(pages, year, names):
    heading = rf"Induced Abortions by Age of Woman and County\s+Number and Rate\*: Pennsylvania Residents, {year}"
    table = "\n".join(page for page in pages if re.search(heading, page, re.I))
    pattern = rf"^ *([A-Za-z ]+?) {{2,}}({COUNT})(?=\s|\*|$)"
    rows = [(names[name.casefold()], count(value)) for name, value in re.findall(pattern, table, re.M) if name.casefold() in names]
    return rows, table


def pennsylvania():
    source_by_year = {year: f"pa-abortion-occurrence-{year}" for year in range(1995, 2025)}
    reports = {year: pdf_text(source).split("\f") for year, source in source_by_year.items()}
    statewide = pennsylvania_statewide(reports)
    totals = {row["year"]: row for row in statewide["rows"]}
    names = {name.casefold(): name for name, _ in pennsylvania_occurrence_rows(reports[2024], 2024)}
    residence, occurrence = {}, {}
    for year, pages in reports.items():
        occurred = [(names[name.casefold()], value) for name, value in pennsylvania_occurrence_rows(pages, year)]
        verify_total(occurred, totals[year]["occurrence"])
        occurrence[year] = counties(occurred, 67)
        residents, table = pennsylvania_residence_rows(pages, year, names)
        unknown = totals[year]["residence"] - sum(value for _, value in residents)
        # These two reports leave a residual without an unknown-county note in Table D-6.
        documented = re.search(r"unknown county", table, re.I) or {1995: 1, 2006: 4}.get(year) == unknown
        if unknown < 0 or (unknown and not documented):
            raise ValueError(f"Unexplained difference in Pennsylvania {year} residence counts")
        residence[year] = counties(residents, 67)
    return {
        "source": source_by_year[2024],
        "sourceByYear": source_by_year,
        "scope": "Reported induced abortions among Pennsylvania residents by county of residence, Table D-6. Reports with an unknown county are excluded from the county figures. The published county sums fall short of the statewide totals by one in 1995 and four in 2006.",
        "years": residence,
        "occurrence": {
            "source": source_by_year[2024],
            "sourceByYear": source_by_year,
            "scope": "Induced abortions reported in Pennsylvania, grouped by county where the procedure occurred, including patients who lived outside Pennsylvania. Pennsylvania Vital Statistics, Table D-7.",
            "years": occurrence,
        },
        "statewide": statewide,
    }


SC_COUNTIES = (
    "Abbeville", "Aiken", "Allendale", "Anderson", "Bamberg", "Barnwell", "Beaufort",
    "Berkeley", "Calhoun", "Charleston", "Cherokee", "Chester", "Chesterfield",
    "Clarendon", "Colleton", "Darlington", "Dillon", "Dorchester", "Edgefield",
    "Fairfield", "Florence", "Georgetown", "Greenville", "Greenwood", "Hampton",
    "Horry", "Jasper", "Kershaw", "Lancaster", "Laurens", "Lee", "Lexington",
    "McCormick", "Marion", "Marlboro", "Newberry", "Oconee", "Orangeburg",
    "Pickens", "Richland", "Saluda", "Spartanburg", "Sumter", "Union",
    "Williamsburg", "York",
)
SC_OCCURRENCE_SCOPE = (
    "Reported abortions in South Carolina by county of occurrence, including patients who lived "
    "elsewhere. Vital and Morbidity Statistics, Table 48 (2000) and Table E-3 (2001–2014). "
    "The reports explain that counties omitted from the occurrence table had no occurrences."
)


def sc_county_rows(table, labels):
    names = {name.casefold(): name for name in labels}
    result = {}
    for label, raw_count in re.findall(
        rf"^[ \t]*(?:\d+ +)?([A-Za-z ]+?) +({COUNT}|-)(?=\s|\*)", table, re.M,
    ):
        name = names.get(label.casefold())
        if name is None:
            continue
        if name in result:
            raise ValueError(f"Duplicate South Carolina row: {name}")
        result[name] = 0 if raw_count == "-" else int(raw_count.replace(",", ""))
    return result


def sc_occurrence_year(text, year):
    table_label = "Table 48." if year == 2000 else "Table E-3."
    table, = (
        page for page in text.split("\f")
        if page.lstrip().startswith(table_label) and "(Occurrence Data)" in page
    )
    # The first block gives all ages and races. Later blocks are race breakdowns.
    total_block = re.split(r"^\s*White\s*$", table, maxsplit=1, flags=re.M)[0]
    rows = sc_county_rows(total_block, (*SC_COUNTIES, "South Carolina", "S Carolina"))
    statewide = rows.pop("South Carolina" if "South Carolina" in rows else "S Carolina")
    if sum(rows.values()) != statewide:
        raise ValueError(f"South Carolina occurrence counts do not sum to the {year} total")
    if len(rows) != len(SC_COUNTIES) and "Counties not listed had no occurrences" not in table:
        raise ValueError(f"South Carolina {year} occurrence table has unexplained omissions")
    return counties([(name, rows.get(name, 0)) for name in SC_COUNTIES], len(SC_COUNTIES))


def south_carolina_occurrence():
    years = {}
    source_by_year = {}
    for year in range(2000, 2015):
        source = f"sc-vital-statistics-{year}"
        years[year] = sc_occurrence_year(pdf_text(source), year)
        source_by_year[year] = source
    return {
        "source": source_by_year[max(years)],
        "sourceByYear": source_by_year,
        "scope": SC_OCCURRENCE_SCOPE,
        "years": years,
    }


def south_carolina(source):
    table, = (
        page for page in pdf_text(source).split("\f")
        if page.lstrip().startswith("Table E-2.") and "(Residence Data)" in page
    )
    rows = sc_county_rows(table, (*SC_COUNTIES, "South Carolina", "Unknown"))
    statewide, unknown = rows.pop("South Carolina"), rows.pop("Unknown")
    if set(rows) != set(SC_COUNTIES) or sum(rows.values()) + unknown != statewide:
        raise ValueError("South Carolina residence counts do not reconcile to the 2024 total")
    return {2024: counties(list(rows.items()), len(SC_COUNTIES))}

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


def washington_occurrence():
    columns = {
        2002: (("King", "Pierce", "Spokane", "Thurston", "Yakima", "Snohomish", "Whatcom", "Clark"), 25148),
        2005: (("King", "Pierce", "Spokane", "Thurston", "Yakima", "Snohomish", "Clark"), 24108),
    }
    years, sources = {}, {}
    for year, (names, statewide) in columns.items():
        source = f"wa-abortion-counties-{year}"
        page, = (p for p in pdf_text(source).split("\f") if p.lstrip().startswith("Table 26a."))
        line, = re.findall(rf"^Total +({COUNT}(?: +{COUNT})+) *$", page, re.M)
        totals = [count(value) for value in line.split()]
        # The final columns are "Other Counties" and occurrences outside Washington.
        if len(totals) != len(names) + 2:
            raise ValueError(f"Unexpected Washington occurrence columns for {year}")
        verify_total(list(zip((*names, "Other Counties"), totals[:-1])), statewide)
        years[year] = counties(list(zip(names, totals[:-2], strict=True)), len(names))
        sources[year] = source
    return {
        "source": sources[max(sources)],
        "sourceByYear": sources,
        "scope": "Reported procedures within Washington, Table 26a occurrence totals. The tracker shows counties with separately published totals. The source combines other counties.",
        "years": years,
    }


def florida_occurrence():
    years = {}
    source_by_year = {}
    aliases = {"Dade": "Miami-Dade", "Desoto": "DeSoto", "St Johns": "St. Johns", "St Lucie": "St. Lucie", "Holme": "Holmes"}
    heading = r"TABLE T-1: REPORTED INDUCED TERMINATIONS OF PREGNANCY,"
    for year in range(2001, 2008):
        source = f"fl-abortion-occurrence-{year}"
        text = pdf_text(source)
        page, = (p for p in text.split("\f") if heading in p and "BY COUNTY WHERE TERMINATIONS OCCURRED" in p)
        parsed = re.findall(rf"^ *([A-Z .-]+?) +({COUNT})(?: +{COUNT}){{4}} *$", page, re.M)
        values = {aliases.get(name.title(), name.title()): count(value) for name, value in parsed}
        expected = values.pop("Florida")
        verify_total(list(values.items()), expected)
        years[year] = counties(list(values.items()), 67)
        if len(parsed) != 68:
            raise ValueError(f"Duplicate Florida county or statewide row for {year}")
        source_by_year[year] = source
    return {
        "source": source_by_year[max(years)],
        "sourceByYear": source_by_year,
        "scope": "Induced terminations reported in Florida by county where the procedure occurred, Table T-1. The source reports zeros explicitly.",
        "years": years,
    }


def arizona_occurrence():
    years = {}
    source_by_year = {}
    heading = "ABORTIONS BY COUNTY OF RESIDENCE AND COUNTY OF OCCURRENCE, ARIZONA,"
    for year in range(2008, 2012):
        source = f"az-abortion-occurrence-{year}"
        text = pdf_text(source)
        table, = (p for p in text.split("\f") if f"{heading} {year}" in p and "Coconino" in p and "Maricopa" in p)
        labels = next(line.split() for line in table.splitlines() if re.search(r"\bCoconino +Maricopa\b", line) and "Pima" in line)
        entry, = re.findall(rf"^ *ARIZONA +({COUNT}(?: +{COUNT})+) *$", table, re.M)
        group_size = 3 if year == 2008 else 4
        fields = [count(value) for value in entry.split()]
        totals = fields[::group_size]
        if len(totals) != len(labels) + 1 or sum(totals[1:]) != totals[0]:
            raise ValueError(f"Arizona {year} county totals do not reconcile")
        values = {name: value for name, value in zip(labels, totals[1:]) if name not in {"Out-of-State", "Unknown"}}
        years[year] = counties(list(values.items()), len(values))
        source_by_year[year] = source
    return {
        "source": source_by_year[max(years)],
        "sourceByYear": source_by_year,
        "scope": "Reported abortions to Arizona residents by Arizona county where the procedure occurred, Table 5D-3. The source excludes nonresidents and does not give separate counts for unlisted counties.",
        "years": years,
    }


NEBRASKA_NAMES = ("Douglas", "Lancaster", "Sarpy")
NEBRASKA_TOTALS = {2018: 2078, 2019: 2068, 2020: 2378, 2021: 2360, 2022: 2547, 2023: 2325, 2024: 2501, 2025: 2698}


def nebraska_occurrence():
    years = {}
    source_by_year = {}
    heading = r"^ *Table 10: Number and Percent of Abortions *\n +by County of Occurrence *\n"
    for year in range(2018, 2024):
        source = f"ne-abortion-occurrence-{year}"
        page, = (p for p in pdf_text(source).split("\f") if re.search(heading, p, re.M))
        table = page.split("Table 11:", 1)[0]
        values = {
            name: count(value)
            for name, value in re.findall(rf"^ *(Douglas|Lancaster|Sarpy) +({COUNT}) +\d+\.\d+ *$", table, re.M)
        }
        if set(values) != set(NEBRASKA_NAMES) or sum(values.values()) != NEBRASKA_TOTALS[year]:
            raise ValueError(f"Nebraska {year} county totals do not reconcile")
        years[year] = counties(list(values.items()), len(NEBRASKA_NAMES))
        source_by_year[year] = source
    for year, source in ((2024, "ne-abortion-occurrence-dashboard-2024"), (2025, "ne-abortion-counties-2025")):
        # Values printed directly on the occurrence chart. The statewide overview independently checks the sum.
        text = pdf_text(source)
        title = f"Number of Abortions by County of Occurence, Year: {year}"
        page, = (p for p in text.split("\f") if title in p)
        lines = page.split(title, 1)[1].split("County Of Occurence", 1)[0].splitlines()
        labels, = [line for line in lines if all(re.search(rf"\b{name}\b", line) for name in NEBRASKA_NAMES)]
        columns = {name: labels.index(name) + len(name) / 2 for name in NEBRASKA_NAMES}
        values = {}
        for line in lines:
            for field in re.finditer(r"(?<![\w.])[\d,]+(?![\w.%,])", line[:140]):
                position = (field.start() + field.end()) / 2
                for name, center in columns.items():
                    if abs(position - center) <= 5:
                        if name in values:
                            raise ValueError(f"Ambiguous Nebraska chart value for {year} {name}")
                        values[name] = count(field[0])
        if set(values) != set(NEBRASKA_NAMES) or sum(values.values()) != NEBRASKA_TOTALS[year]:
            raise ValueError(f"Nebraska {year} chart totals do not reconcile")
        years[year] = counties(list(values.items()), len(NEBRASKA_NAMES))
        source_by_year[year] = source
    return {
        "source": source_by_year[max(years)],
        "sourceByYear": source_by_year,
        "scope": "Reported abortions performed in Nebraska by county of occurrence. The reports publish three named counties and aggregate or omit any other county figures.",
        "years": years,
    }


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
    "39": (
        "oh-abortion-counties-2025", ohio,
        "Ohio residents with induced abortions reported in Ohio, Table 5. In 2020 and 2021 the published county sums differ by one from the state total after excluding unknown residence.",
    ),
    "41": (
        "or-abortion-counties-1995-2025", oregon,
        "Oregon residents with abortions reported in Oregon. These are the final annual totals from the state's workbook. The published 2018 rows sum to one fewer than the worksheet total.",
    ),
    "45": (
        "sc-vital-statistics-2024", south_carolina,
        "Reported abortions among South Carolina residents by county of residence, Table E-2. The report lists 6,646 additional abortions with unknown county of residence in 2024.",
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
        if fips == "27":
            data[fips]["sourceByYear"] = {year: f"mn-abortion-counties-{year}" for year in years if year <= 2022}
        if fips == "53":
            data[fips]["sourceByYear"] = {year: f"wa-abortion-counties-{year}" for year in years}
        print(f"{source}: {min(years)}–{max(years)}, {len(years[max(years)])} counties")
    data["36"] = new_york_city()
    data["37"] = north_carolina()
    data["42"] = pennsylvania()
    occurrence_sources = {
        "04": arizona_occurrence,
        "12": florida_occurrence,
        "26": michigan_occurrence,
        "31": nebraska_occurrence,
        "39": ohio_occurrence,
        "45": south_carolina_occurrence,
        "53": washington_occurrence,
    }
    for fips, parse in occurrence_sources.items():
        data.setdefault(fips, {})["occurrence"] = parse()
    (ROOT / "docs" / "data" / "counties.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
