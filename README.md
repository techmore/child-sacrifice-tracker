# Three in Ten

A sourced social and philosophical inquiry that sets the modern abortion debate beside the historic record of child sacrifice, family structure and resilience.

The site lives in `docs/`. Its maps, charts, tables, and citations work offline from a local static server.

```sh
python3 -m http.server --bind 127.0.0.1 --directory docs 8000
```

Open http://127.0.0.1:8000. Citation links open the original publications. The archive manifest locates local copies.

## Data

- **Country estimates:** Bearak et al. 2022, BMJ Global Health, annual averages for 2015 to 2019 (CC BY-NC 4.0).
- **U.S. historical estimates:** Guttmacher national estimates for 1973 to 2020 and selected state years from 1988 to 2020. State figures use patient residence.
- **U.S. surveillance:** CDC counts from participating jurisdictions for 1969 to 2022. Participation varies.
- **Recent U.S. estimates:** Guttmacher Monthly Abortion Provision Study estimates for 2023 to 2025, including 90% uncertainty intervals. The chart keeps these estimates separate from the historical series and CDC reports.
- **County reports:** Select United States, then a state. For states with verified public tables, the map and table show reported counts by patient county of residence. Arizona, Florida, Michigan, Nebraska, North Carolina, Ohio, Pennsylvania, and South Carolina also have procedure-location series. Dates and coverage vary by state. Each panel gives the reporting scope and source. Reported zero, source suppression, and missing data have distinct labels.

The URL keeps your map selection when you refresh or share it. For example, [Pennsylvania procedure counts for 2024](https://techmore.github.io/child-sacrifice-tracker/?state=PA&basis=occurrence&year=2024#county-panel).
- **Economic context:** World Bank GDP per capita, 2023.

Rebuild the data without a network connection after setting up the local reference archive and installing `openpyxl` and `pdftotext`.

```sh
python3 scripts/build_data.py
python3 scripts/build_us_history.py
python3 scripts/build_counties.py
python3 scripts/fetch_references.py --index-only
```

## SQLite

`python3 scripts/build_sqlite.py` generates `data/tracker.sqlite3` offline from the published JSON snapshots and reference manifest. Use `--output` to choose another file. The database holds the national, state, county, and global data, with source records and hashes for the build inputs. The source documents remain in the archive.

`county_observation` and `county_release` show the county-of-residence series. To query both geographic bases, use `county_series_observation` and `county_series_release` and join on `state_fips, year, series_id`. The `county-reported` series uses patient residence, and `county-occurrence` uses the county where the procedure was reported.

```sh
sqlite3 -header -column data/tracker.sqlite3 "
SELECT o.year, o.county_name, o.abortions, o.status, s.url
FROM county_observation AS o
JOIN county_release AS r USING (state_fips, year)
JOIN source AS s ON s.id = r.source_id
WHERE o.state_fips = '39' AND o.county_name = 'Franklin'
ORDER BY o.year DESC;"
```

## References

`references/sources.tsv` is the bibliography, `references/country-profiles.tsv` indexes the 150 country profile PDFs, and `references/manifest.json` records filenames, retrieval dates, and SHA-256 checksums. Redistributable documents are stored in `references/open/`. Other downloads are stored in the git-ignored `references/private/`. Copy that directory along with the checkout to use the complete archive on another offline machine.

Run `python3 scripts/fetch_references.py` online to fill in missing downloads. The script reuses local copies whose checksums match the manifest. If a publisher changed a file, use `--refresh` to accept a newer copy. Read the saved report or dataset version when comparing published figures.

## Conduct

This project does not list clinics, hospitals or staff, and it will not accept contributions that do. Direct disagreement to lawmakers and public argument. Never harass or threaten patients or providers.

## License

Project code and writing are for noncommercial use because the country estimates are CC BY-NC 4.0. Third-party data and documents keep their own licenses.
