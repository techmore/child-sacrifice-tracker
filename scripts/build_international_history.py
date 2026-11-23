#!/usr/bin/env python3
"""Build continent coverage and individual histories from archived publications."""

from collections import defaultdict
import json
from pathlib import Path
import re
import unicodedata

from eurostat_history import read_eurostat
from nz_history import read_nz_history
from south_africa_history import read_south_africa
from undata_history import read_undata


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "docs/data"
REFERENCES = ROOT / "references"

SERIES = {
    "un-yearbook": {
        "label": "UN Demographic Yearbook",
        "scope": "Figures submitted by national statistical offices. The latest available edition supplies each observation. Country footnotes can qualify what was counted. Observations explicitly identified as different measures, such as applications or counts including miscarriages, are omitted.",
        "documentation": "https://unstats.un.org/unsd/demographic-social/products/dyb/",
    },
    "eurostat": {
        "label": "Eurostat",
        "scope": "Reported legally induced abortions, all ages. Country reporting and status flags vary. The original snapshot includes overlapping geographic variants.",
        "documentation": "https://ec.europa.eu/eurostat/cache/metadata/en/demo_fer_esms.htm",
    },
    "new-zealand": {
        "label": "New Zealand national statistics",
        "scope": "Registered induced abortions from Stats NZ and subsequent Ministry of Health reporting. The Ministry's revised figures take precedence for overlapping years.",
    },
    "south-africa": {
        "label": "South Africa public-sector DHIS",
        "scope": "Reported terminations in the public health system. The year shown is the end of the April–March financial year. Private-sector procedures are outside this series.",
    },
    "guttmacher": {
        "label": "Guttmacher incidence data",
        "scope": "Single-year official statistics marked complete and excluding spontaneous abortions. Years with conflicting eligible counts are omitted.",
    },
    "cdc": {
        "label": "CDC surveillance",
        "scope": "Reported abortions in participating U.S. jurisdictions. Reporting coverage varies by year.",
    },
}

# Names appearing in the source that differ from the geographic metadata.
UN_ALIASES = {
    "China, Hong Kong SAR": "HKG",
    "China, Macao SAR": "MAC",
    "Netherlands (Kingdom of the)": "NLD",
    "Cabo Verde": "CPV",
    "Channel Islands: Guernsey": "GGY",
    "Channel Islands: Jersey": "JEY",
    "Czech Republic": "CZE",
    "Faeroe Islands": "FRO",
    "Republic of Moldova": "MDA",
    "Russian Federation": "RUS",
    "TFYR of Macedonia": "MKD",
    "The Former Yugoslav Rep. of Macedonia": "MKD",
    "Türkiye": "TUR",
    "Turks Caicos Islands": "TCA",
    "Saint Helena ex. dep.": "SHN",
}


def name_key(name):
    folded = unicodedata.normalize("NFKD", name.casefold())
    return re.sub(r"[^a-z0-9]", "", folded)


def continent(place):
    if place["region"] == "Americas":
        return "South America" if place["subregion"] == "South America" else "North America"
    return place["region"]


def registry():
    manifest = json.loads((REFERENCES / "manifest.json").read_bytes())

    def archived(identifier):
        entry = next(item for item in manifest if item["id"] == identifier)
        path = REFERENCES / entry.get("file", "")
        if entry["status"] != "saved" or not path.is_file():
            raise ValueError(f"Restore {identifier} before rebuilding international history")
        return path

    return manifest, archived


def build():
    manifest, archived = registry()
    countries = json.loads((SNAPSHOTS / "countries.json").read_bytes())
    us_history = json.loads((SNAPSHOTS / "us-history.json").read_bytes())
    geography = json.loads((ROOT / "data/raw/world-countries.json").read_bytes())
    by_id = {p["cca3"]: p for p in geography}
    by_iso2 = {p["cca2"]: p for p in geography}
    by_name = {
        name_key(name): place
        for place in geography
        for name in (place["name"]["common"], place["name"]["official"])
    }
    by_name.update({name_key(name): by_id[iso3] for name, iso3 in UN_ALIASES.items()})
    rows = {}

    def add(place, series, year, count, source, *, status=None, notes=None):
        geo, name, region = place
        rows[geo, series, year] = {
            "geography": geo, "name": name, "continent": region, "series": series,
            "year": year, "count": count, "source": source, "status": status, "notes": notes,
        }

    def place_info(place):
        return place["cca3"], place["name"]["common"], continent(place)

    for entry in sorted(manifest, key=lambda entry: entry["id"]):
        source = entry["id"]
        if not source.startswith("un-dyb-abortions-"):
            continue
        for row in read_undata(archived(source)):
            name = row["name"]
            place = by_name.get(name_key(name))
            if place:
                location = place_info(place)
            else:
                location = f"un-{name_key(name)}", name, row["continent"]
            add(location, "un-yearbook", row["year"], row["count"], source,
                status=row["status"], notes=" ".join(row["notes"]) or None)

    eurostat = "eurostat-legally-induced-abortions"
    for row in read_eurostat(archived(eurostat)):
        add(place_info(by_iso2[row["iso2"]]), "eurostat", row["year"], row["count"], eurostat,
            status=row["status"])

    for row in read_nz_history(archived("stats-nz-abortions-1980-2019"),
                               archived("nz-ministry-abortions-2012-2024")):
        add(place_info(by_id["NZL"]), "new-zealand", row["year"], row["count"], row["source"],
            status=row.get("status"), notes=row.get("notes"))

    for row in read_south_africa(archived):
        add(place_info(by_id["ZAF"]), "south-africa", row["year"], row["count"], row["source"],
            status=row["status"], notes=row["notes"])

    for country in countries:
        if not country["reported"]:
            continue
        for year, count in country["reported"]:
            publishers = country["reportedSources"].get(str(year), [])
            add(place_info(by_id[country["iso3"]]), "guttmacher", year, count,
                "osf-global-incidence-csv", notes="; ".join(publishers) or None)

    for year, count, coverage, source in cdc_observations(us_history):
        add(place_info(by_id["USA"]), "cdc", year, count, source, notes=coverage)

    history = sorted(
        (row for row in rows.values() if row["status"] != "different_measure"),
        key=lambda row: (row["continent"], row["name"], row["series"], row["year"]),
    )
    covered = defaultdict(set)
    for row in history:
        covered[row["continent"]].add((row["geography"], row["year"]))
    coverage = [
        {"continent": region, "geographies": len({geo for geo, _ in years}), "countryYears": len(years),
         "firstYear": min(year for _, year in years), "lastYear": max(year for _, year in years)}
        for region, years in sorted(covered.items())
    ]
    output = {"series": SERIES, "coverage": coverage, "rows": history}
    (SNAPSHOTS / "international-history.json").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8",
    )
    print(f"{len(history)} observations across {sum(row['countryYears'] for row in coverage)} unique country-years")
    for row in coverage:
        print(row)


def cdc_observations(history):
    periods = [(1972, "cdc-abortion-1972"), (2005, "cdc-abortion-2005"),
               (2012, "cdc-abortion-2014"), (2022, "cdc-abortion-2022")]
    for row in history["cdc"]["rows"]:
        source = next(identifier for end, identifier in periods if row["year"] <= end)
        yield row["year"], row["abortions"], f"{row['areas']} reporting areas" if row.get("areas") else None, source


if __name__ == "__main__":
    build()
