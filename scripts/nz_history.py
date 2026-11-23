"""Read New Zealand's official annual induced-abortion counts from archived data."""

import csv
import io
import zipfile

import openpyxl


STATS_NZ_SOURCE = "stats-nz-abortions-1980-2019"
MINISTRY_SOURCE = "nz-ministry-abortions-2012-2024"


def _read_stats_nz(path):
    with zipfile.ZipFile(path) as archive:
        with archive.open("as-dec-19-induced-abortions.csv") as member:
            data = csv.DictReader(io.TextIOWrapper(member, encoding="utf-8-sig"))
            if data.fieldnames != ["Period", "Induced_abortions"]:
                raise ValueError("Unexpected columns in the Stats NZ induced abortions CSV")
            rows = [(int(row["Period"]), int(row["Induced_abortions"])) for row in data]
    return _validate_counts(rows, 1980, 2019, "Stats NZ")


def _read_ministry(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Figure 1-1,1-2,1-3"]
        rows = sheet.iter_rows(min_row=3, min_col=1, max_col=2, values_only=True)
        if next(rows) != ("Year", "Number"):
            raise ValueError("Unexpected columns in the NZ Ministry annual totals worksheet")
        counts = [(year, count) for year, count in rows if year is not None]
    finally:
        workbook.close()
    return _validate_counts(counts, 2012, 2024, "NZ Ministry of Health")


def _validate_counts(rows, first_year, last_year, publisher):
    if [year for year, _ in rows] != list(range(first_year, last_year + 1)):
        raise ValueError(f"Expected continuous annual counts for {first_year}–{last_year} from {publisher}")
    if any(type(count) is not int or count < 0 for _, count in rows):
        raise ValueError(f"Expected nonnegative integer counts from {publisher}")
    return dict(rows)


def read_nz_history(stats_nz_zip, ministry_workbook):
    """Return 1980–2024 national counts, favoring the revised Ministry count in 2019."""
    stats = _read_stats_nz(stats_nz_zip)
    ministry = _read_ministry(ministry_workbook)
    for year in range(2012, 2019):
        if stats[year] != ministry[year]:
            raise ValueError(f"NZ annual counts differ between sources for {year}")

    records = [
        {"year": year, "count": count, "status": "reported", "notes": "", "source": STATS_NZ_SOURCE}
        for year, count in stats.items() if year < 2019
    ]
    ministry_notes = {
        2019: f"Revised Ministry total. The earlier Stats NZ release reported {stats[2019]:,}.",
        2020: "The Ministry combined Stats NZ and Ministry records to cover the entire calendar year.",
    }
    records.extend(
        {"year": year, "count": count, "status": "reported", "notes": ministry_notes.get(year, ""),
         "source": MINISTRY_SOURCE}
        for year, count in ministry.items() if year >= 2019
    )
    return records
