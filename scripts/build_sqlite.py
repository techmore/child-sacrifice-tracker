#!/usr/bin/env python3
"""Build the local SQLite database from the published data and archive manifest."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parent.parent
SCHEMA = Path("scripts/tracker_schema.sql")
MANIFEST = Path("references/manifest.json")
SNAPSHOTS = {
    name: Path(f"docs/data/{name}.json")
    for name in ("countries", "us", "us-history", "states", "counties")
}
INPUTS = (SCHEMA, MANIFEST, *SNAPSHOTS.values())
CDC_SOURCE_YEARS = {
    "cdc-abortion-1972": (1969, 1972),
    "cdc-abortion-2005": (1973, 2005),
    "cdc-abortion-2014": (2006, 2012),
    "cdc-abortion-2022": (2013, 2022),
}
SERIES = [
    ("country-modeled", "Bearak et al. country estimates",
     "Annual averages for 2015 to 2019. Rates per 1,000 women aged 15 to 49. "
     "Bounds are 80% uncertainty intervals.", "country"),
    ("country-reported", "Official reported country counts",
     "Single-year official statistics marked complete in the incidence dataset. "
     "Definitions and coverage can vary across countries and years.", "country"),
    ("country-gdp", "World Bank GDP per capita",
     "GDP per capita in current U.S. dollars, rounded to a whole dollar.", "country"),
    ("us-historical", "Guttmacher historical national estimates",
     "National estimates. Rates per 1,000 women aged 15 to 44.", "us"),
    ("state-historical", "Guttmacher historical state estimates",
     "Estimates by state of residence. Rates per 1,000 women aged 15 to 44. "
     "Counts are available in selected years before 2005.", "state"),
    ("county-reported", "Reported county counts by residence",
     "Public aggregate counts by patient county of residence. See each release for "
     "coverage. A suppressed value has a NULL count. A missing county has no row.", "county"),
]


def insert_sources(db, manifest):
    db.executemany(
        """INSERT INTO source (
                id, title, url, access, retrieved, archive_status, archive_path,
                archive_sha256, archive_bytes, archive_error
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            (r["id"], r["title"], r["url"], r["access"], r["retrieved"], r["status"],
             r.get("file"), r.get("sha256"), r.get("bytes"), r.get("error"))
            for r in manifest
        ),
    )


def country_key(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub("[^a-z]", "", ascii_name.lower())


def insert_countries(db, countries, manifest):
    prefix = "osf-country-profile-"
    profiles = {
        country_key(source["id"].removeprefix(prefix)): source["id"]
        for source in manifest if source["id"].startswith(prefix)
    }
    db.executemany(
        "INSERT INTO country (id, iso3, name, region) VALUES (?, ?, ?, ?)",
        ((r["id"], r["iso3"], r["name"], r["region"]) for r in countries),
    )
    db.executemany(
        """INSERT INTO country_estimate (
                country_id, series_id, profile_source_id, first_year, last_year,
                abortions, abortions_low, abortions_high, rate, rate_low, rate_high,
                births, share_of_births_plus_abortions, share_unintended_aborted
           ) VALUES (?, 'country-modeled', ?, 2015, 2019, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            (r["id"], profiles.get(country_key(r["name"])), r["abortions"],
             r["abortionsLow"], r["abortionsHigh"], r["rate"], r["rateLow"],
             r["rateHigh"], r["births"], r["shareOfBirthsPlusAbortions"],
             r["shareUnintendedAborted"])
            for r in countries
        ),
    )
    db.executemany(
        """INSERT INTO country_reported (country_id, series_id, year, abortions)
           VALUES (?, 'country-reported', ?, ?)""",
        ((r["id"], year, count) for r in countries for year, count in r["reported"]),
    )
    db.executemany(
        """INSERT INTO country_gdp (country_id, series_id, year, gdp_per_capita_usd)
           VALUES (?, 'country-gdp', 2023, ?)""",
        ((r["id"], r["gdpPerCapita2023"]) for r in countries if r["gdpPerCapita2023"] is not None),
    )


def insert_us(db, historical, supplemental):
    db.executemany(
        """INSERT INTO us_observation (series_id, year, abortions, rate)
           VALUES ('us-historical', ?, ?, ?)""",
        ((r["year"], r["abortions"], r["rate"]) for r in historical),
    )
    for key, data in supplemental.items():
        series_id = f"us-{key}"
        db.execute(
            "INSERT INTO series (id, label, scope, geography) VALUES (?, ?, ?, 'us')",
            (series_id, data["label"], data["scope"]),
        )
        db.executemany(
            """INSERT INTO series_source (
                    series_id, source_id, first_year, last_year, citation_label, citation_url
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                (series_id, source["id"], *CDC_SOURCE_YEARS.get(source["id"], (None, None)),
                 source["label"], source["url"])
                for source in data["sources"]
            ),
        )
        db.executemany(
            """INSERT INTO us_observation (
                    series_id, year, abortions, reporting_areas, abortions_low, abortions_high
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                (series_id, r["year"], r["abortions"], r.get("areas"), r.get("low"), r.get("high"))
                for r in data["rows"]
            ),
        )


def insert_states(db, states):
    db.executemany(
        "INSERT INTO state (fips, abbr, name) VALUES (?, ?, ?)",
        ((r["id"], r["abbr"], r["name"]) for r in states),
    )
    for state in states:
        observations = dict(state["reported"])
        if observations.get(state["year"]) != state["abortions"]:
            raise ValueError(f"State summary for {state['name']} disagrees with its annual series")
        total = sum(count for year, count in observations.items() if 2005 <= year <= 2020)
        if total != state["total2005to2020"]:
            raise ValueError(f"State total for {state['name']} disagrees with its annual series")
        db.executemany(
            """INSERT INTO state_observation (
                    state_fips, series_id, year, abortions, rate, births, share_of_births_plus_abortions
               ) VALUES (?, 'state-historical', ?, ?, ?, ?, ?)""",
            (
                (state["id"], year, count, state["rate"], state["births"], state["shareOfBirthsPlusAbortions"])
                if year == state["year"] else (state["id"], year, count, None, None, None)
                for year, count in state["reported"]
            ),
        )


def insert_counties(db, states):
    for fips, state in sorted(states.items()):
        years = state["years"]
        names = {r["name"] for rows in years.values() for r in rows}
        db.executemany(
            "INSERT INTO county (state_fips, name) VALUES (?, ?)",
            ((fips, name) for name in sorted(names)),
        )
        source_by_year = state.get("sourceByYear", {})
        for year, rows in sorted(years.items()):
            source_id = source_by_year.get(year, state.get("source"))
            db.execute(
                """INSERT INTO county_release (state_fips, year, series_id, source_id, scope)
                   VALUES (?, ?, 'county-reported', ?, ?)""",
                (fips, int(year), source_id, state["scope"]),
            )
            db.executemany(
                """INSERT INTO county_observation (state_fips, county_name, year, abortions, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    (fips, r["name"], int(year), r["count"],
                     "suppressed" if r["count"] is None else "reported")
                    for r in rows
                ),
            )


def populate(db, files):
    manifest = json.loads(files[MANIFEST])
    data = {name: json.loads(files[path]) for name, path in SNAPSHOTS.items()}
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(files[SCHEMA].decode())
    with db:
        db.executemany(
            "INSERT INTO build_input (path, sha256, byte_count) VALUES (?, ?, ?)",
            ((path.as_posix(), sha256(raw).hexdigest(), len(raw)) for path, raw in files.items()),
        )
        insert_sources(db, manifest)
        db.executemany("INSERT INTO series (id, label, scope, geography) VALUES (?, ?, ?, ?)", SERIES)
        db.executemany(
            "INSERT INTO series_source (series_id, source_id) VALUES (?, ?)",
            [
                ("country-modeled", "bearak-2022-bmj-gh"),
                ("country-modeled", "bearak-2022-supp-tables"),
                ("country-reported", "osf-global-incidence-csv"),
                ("country-reported", "osf-global-incidence-codebook"),
                ("country-gdp", "world-bank-gdp"),
                ("us-historical", "osf-us-pregnancy-csv"),
                ("state-historical", "osf-us-pregnancy-csv"),
            ],
        )
        insert_countries(db, data["countries"], manifest)
        insert_us(db, data["us"], data["us-history"])
        insert_states(db, data["states"])
        insert_counties(db, data["counties"])
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite foreign key check failed")
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")


def build(output):
    if output.resolve() in {ROOT / path for path in INPUTS}:
        raise ValueError("The output must differ from the build inputs")
    files = {path: (ROOT / path).read_bytes() for path in INPUTS}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        db = sqlite3.connect(temp_path)
        try:
            populate(db, files)
        finally:
            db.close()
        os.replace(temp_path, output)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/tracker.sqlite3")
    args = parser.parse_args()
    try:
        build(args.output)
    except (OSError, ValueError, sqlite3.Error) as err:
        parser.exit(1, f"Could not build SQLite database: {err}\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
