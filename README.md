# Three in Ten

A sourced social and philosophical inquiry that sets the modern abortion debate beside the historic record of child sacrifice, family structure and resilience.

The site lives in `docs/`. Its maps, charts, tables, and citations work offline from a local static server.

```sh
python3 -m http.server --bind 127.0.0.1 --directory docs 8000
```

Open http://127.0.0.1:8000. Citation links open the original publications. The archive manifest locates local copies.

## Data

- **Country estimates:** Bearak et al. 2022, BMJ Global Health, annual averages for 2015 to 2019 (CC BY-NC 4.0).
- **Reported country history:** Official single-year counts marked complete and explicitly excluding spontaneous abortions. Years with conflicting eligible counts are omitted. Each retained observation records the contributing publishers named in the archived dataset.
- **U.S. historical estimates:** Guttmacher national estimates for 1973 to 2020 and selected state years from 1988 to 2020. State figures use patient residence.
- **U.S. surveillance:** CDC counts from participating jurisdictions for 1969 to 2022. Participation varies.
- **Recent U.S. estimates:** Guttmacher Monthly Abortion Provision Study estimates for 2023 to 2025 for the U.S., all 50 states and D.C., including 90% uncertainty intervals. These count clinician-provided abortions by state of procedure or pill receipt and appear separately from historical residence estimates and CDC reports.
- **County reports:** Select United States, then a state. Click a county on the map or in the table to zoom in and see its annual history with links to the reports. The U.S. county data coverage table lists the available years and reporting basis for all 50 states and D.C. Each panel gives the reporting scope and source. Reported zero, source suppression, and missing data have distinct labels.

The URL keeps your map selection when you refresh or share it. For example, [Pennsylvania procedure counts for 2024](https://techmore.github.io/child-sacrifice-tracker/?state=PA&basis=occurrence&year=2024#county-panel).

Pennsylvania's official reports cover all 67 counties for 1995–2024 and statewide totals for 1975–2024. County views show the reporting basis and cite the selected year's report. Statewide reported counts also appear in SQLite under `pa-state-reported` and `pa-state-occurrence`.

Zooming into a Pennsylvania county shows its township, borough, and city boundaries from the 2025 U.S. Census cartographic files. The abortion figures remain county totals. Rebuild the boundary layer with `python3 scripts/build_pa_municipalities.py` and `pyshp` installed.

Minnesota's residence series covers all 87 counties for 2018–2024 and preserves source suppression. New York's residence series covers the five New York City boroughs. North Carolina's county reports cover 2000–2023, with 2005 missing and underreporting in 2011–2014. Washington's procedure series uses the published county totals for 2002 and 2005.
- **Economic context:** World Bank GDP per capita, 2023.

A fresh checkout includes the static site and the snapshots used for the offline SQLite build. To rebuild the snapshots from original reports, first restore the full reference archive and install `openpyxl` and `pdftotext`. Then run these commands offline.

```sh
python3 scripts/fetch_references.py --verify
python3 scripts/build_data.py
python3 scripts/build_us_history.py
python3 scripts/build_counties.py
python3 scripts/fetch_references.py --index-only
```

## SQLite

`python3 scripts/build_sqlite.py` generates `data/tracker.sqlite3` offline from the published JSON snapshots and reference manifest. Use `--output` to choose another file. The database holds the national, state, county, and global data, with source records and hashes for the build inputs. The source documents remain in the archive.

`county_observation` and `county_release` show the county-of-residence series. To query both geographic bases, use `county_series_observation` and `county_series_release` and join on `state_fips, year, series_id`. The `county-reported` series uses patient residence, and `county-occurrence` uses the county where the procedure was reported.

Use `state_observation` with series ID `state-recent` for the 2023–2025 clinician-provided estimates and their uncertainty intervals. `country_reported_publisher` gives the publisher names for each retained country-year observation.

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

## Checks

GitHub Actions runs the archive restore test, builds SQLite from the checked-in snapshots, and exercises state selection, county numbers, and refresh in Chromium at desktop and mobile widths. To run the same checks locally:

```sh
python3 -m unittest discover -s tests
python3 scripts/build_sqlite.py
npm install --no-save playwright@1.58.2
npx playwright install chromium
node --test tests/map.cjs
```

## Conduct

Direct disagreement to lawmakers and public argument. Never harass or threaten patients or providers.

## License

Project code and writing are for noncommercial use because the country estimates are CC BY-NC 4.0. Third-party data and documents keep their own licenses.
