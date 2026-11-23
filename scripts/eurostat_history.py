"""Read Eurostat demo_fabort totals from an archived Statistics API response."""
import json
from pathlib import Path


EUROSTAT_COUNTRY_CODES = {"EL": "GR", "UK": "GB"}
# These overlap the DE and FR reporting areas and must not become separate countries.
ALTERNATE_REPORTING_AREAS = {"DE_TOT", "FX"}


def read_eurostat(path):
    """Return national country-year counts with the original geography and status."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    expected_dimensions = ["freq", "unit", "age", "geo", "time"]
    if data["id"] != expected_dimensions:
        raise ValueError("Unexpected Eurostat demo_fabort dimensions")

    indexes = {
        key: data["dimension"][key]["category"]["index"] for key in expected_dimensions
    }
    for dimension, code in (("freq", "A"), ("unit", "NR"), ("age", "TOTAL")):
        if indexes[dimension] != {code: 0}:
            raise ValueError(f"Expected only {dimension}={code} in Eurostat demo_fabort")

    geo_at_index = {index: code for code, index in indexes["geo"].items()}
    year_at_index = {index: int(year) for year, index in indexes["time"].items()}
    period_count = len(year_at_index)
    statuses = data.get("status", {})
    observations = []
    for flat_index, count in data["value"].items():
        geo_index, year_index = divmod(int(flat_index), period_count)
        raw_geo = geo_at_index[geo_index]
        if raw_geo in ALTERNATE_REPORTING_AREAS:
            continue
        iso2 = EUROSTAT_COUNTRY_CODES.get(raw_geo, raw_geo)
        if len(iso2) != 2 or not iso2.isascii() or not iso2.isalpha() or not iso2.isupper():
            raise ValueError(f"Unexpected Eurostat reporting geography {raw_geo}")
        if type(count) is float and count.is_integer():
            # Eurostat encodes some provisional whole counts as decimal JSON numbers.
            count = int(count)
        if type(count) is not int or count < 0:
            raise ValueError(f"Expected a nonnegative abortion count at index {flat_index}")
        observations.append({
            "iso2": iso2,
            "year": year_at_index[year_index],
            "count": count,
            "status": statuses.get(flat_index),
            "raw_geo": raw_geo,
        })
    return sorted(observations, key=lambda row: (row["iso2"], row["year"]))
