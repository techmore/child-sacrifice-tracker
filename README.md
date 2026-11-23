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
- **Historical records by continent:** The explorer combines dated observations from the UN Demographic Yearbook, Eurostat, Stats NZ, the New Zealand Ministry of Health, the South African Health Review, CDC, and Guttmacher. The coverage table counts each country or territory and year once. The series retain their individual counts, source links and reporting notes. Overlapping measurements can differ. The UN series uses the latest archived edition with a numeric observation and excludes explicit alternative measures, such as applications or counts including miscarriages. South African public-sector totals use financial years. Four older UN scans are archived for verification and transcription. The 2015 and 2016 editions have PDF tables in the archive.
- **U.S. historical estimates:** Guttmacher national estimates for 1973 to 2020 and selected state years from 1988 to 2020. State figures use patient residence.
- **U.S. surveillance:** CDC counts from participating jurisdictions for 1969 to 2022. Participation varies.
- **Recent U.S. estimates:** Guttmacher Monthly Abortion Provision Study estimates for 2023 to 2025 for the U.S., all 50 states and D.C., including 90% uncertainty intervals. These count clinician-provided abortions by state of procedure or pill receipt and appear separately from historical residence estimates and CDC reports.
- **County reports:** Select United States, then a state. Click a county on the map or in the table to zoom in and see its annual history with links to the reports. The U.S. county data coverage table lists the available years and reporting basis for all 50 states and D.C. Each panel gives the reporting scope and source. Reported zero, source suppression, and missing data have distinct labels.

The URL keeps your map selection when you refresh or share it. For example, [Pennsylvania procedure counts for 2024](https://techmore.github.io/child-sacrifice-tracker/?state=PA&basis=occurrence&year=2024#county-panel).

Pennsylvania's official reports cover all 67 counties for 1995–2024 and statewide totals for 1975–2024. County views show the reporting basis and cite the selected year's report. Statewide reported counts also appear in SQLite under `pa-state-reported` and `pa-state-occurrence`.

Zooming into a Pennsylvania county shows its township, borough, and city boundaries from the 2025 U.S. Census cartographic files. The abortion figures remain county totals. Rebuild the boundary layer with `python3 scripts/build_pa_municipalities.py` and `pyshp` installed.

Minnesota's residence series covers all 87 counties for 2018–2024 and preserves source suppression. New York's residence series covers the five New York City boroughs. North Carolina's county reports cover 2000–2023, with 2005 missing and underreporting in 2011–2014. Washington's procedure series uses the published county totals for 2002 and 2005.

Indiana has published residence counts for all 92 counties for 1998–2013. Virginia has published county and independent-city residence counts for 1995–2020. Former independent cities remain in the historical tables. Wisconsin has published residence counts for all 72 counties for 1994–2023. These series cite each year's report and preserve suppression where applicable. States without imported county reports show county boundaries and the sourced statewide estimate.
- **Geographic detail:** Counts are reported where the procedure occurred or where the patient lived, whichever basis the source publishes, and both are labeled. The county is the smallest unit any of these agencies publish; no public dataset gives counts per municipality, township or facility. Pennsylvania's township, borough and city boundaries are drawn for navigation only, and its published figures remain county totals. Each county panel also states how concentrated the selected year is: how many counties supply half and four-fifths of the reported total. In Pennsylvania's 2024 procedure figures, half the total came from 2 counties and four-fifths from 6. The panel also lists the five counties with the largest reported counts and their share of the total.
- **Economic context:** World Bank GDP per capita, 2023.

A fresh checkout includes the static site and the snapshots used for the offline SQLite build. To rebuild the snapshots from original reports, first restore the full reference archive and install `openpyxl`, `xlrd` and `pdftotext`. Then run these commands offline.

```sh
python3 scripts/fetch_references.py --verify
python3 scripts/build_data.py
python3 scripts/build_us_history.py
python3 scripts/build_international_history.py
python3 scripts/build_counties.py
python3 scripts/fetch_references.py --index-only
```

## Public funding

The site's "Public money and public conscience" section reports how public funds reach abortion provision at the policy level. It documents funding flows and state rules, not individual providers or facilities.

- **Hyde Amendment:** Since fiscal year 1977 federal Medicaid funds have generally not paid for abortion, with exceptions for rape, incest and danger to the patient's life; Congress restored the rape and incest exceptions in 1993. States may use their own revenue for broader coverage. [Congressional Research Service, RL33467](https://www.congress.gov/crs_external_products/RL/PDF/RL33467/RL33467.53.pdf).
- **State policy:** As of July 24, 2026, KFF counts 21 states that use their own funds for broader Medicaid abortion coverage, 16 states and D.C. that follow the Hyde limits (some with narrow additional exceptions), and 13 that ban abortion subject to exceptions. [KFF state policy analysis](https://www.kff.org/medicaid/state-indicator/abortion-under-medicaid/).
- **Medical training:** Accredited OB/GYN residencies must provide clinical experience in abortion care or access to it, including out-of-state training where local law prevents it; residents may opt out. Before *Dobbs*, 140 of 286 programs (49%) offered routine abortion training. [ACGME program requirements](https://www.acgme.org/globalassets/pfassets/programrequirements/2026-prs/220_obstetricsgynecology_2026.pdf), [Vinekar and colleagues](https://institutionalrepository.aah.org/auroragme/329).

The underlying records are `kff-hyde-medicaid`, `kff-medicaid-state-table`, `kff-state-coverage` and `crs-abortion-history` in `references/sources.tsv`. Figures carry the date and publisher of the policy snapshot they came from.

## Evidence records

The world map can display jurisdiction markers for individual cases and official responses. Each record describes what the cited sources establish and what remains unverified. The [JSON snapshot](docs/data/evidence-records.json) is available offline. SQLite stores these rows in `evidence_record`. Join `evidence_source` and `source` for original URLs and archive paths.

The [payment records](docs/data/material-payments.json) track the amounts, sources and reported scope of individual payment arrangements. The SQLite tables are `material_payment` and `material_payment_source`.

## SQLite

`python3 scripts/build_sqlite.py` generates `data/tracker.sqlite3` offline from the published JSON snapshots and reference manifest. Use `--output` to choose another file. The database holds the national, state, county, and global data, with source records and hashes for the build inputs. The source documents remain in the archive.

`county_observation` and `county_release` show the county-of-residence series. To query both geographic bases, use `county_series_observation` and `county_series_release` and join on `state_fips, year, series_id`. The `county-reported` series uses patient residence, and `county-occurrence` uses the county where the procedure was reported.

Use `state_observation` with series ID `state-recent` for the 2023–2025 clinician-provided estimates and their uncertainty intervals. `country_reported_publisher` gives the publisher names for each retained country-year observation. Join `international_observation` to `international_geography` and `source` to query the continent explorer’s counts, years, status flags and citations offline. Join `world_trend` to `source` for each modeled five-year period, annual count and rate, and its uncertainty bounds.

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

The [Eurostat source](https://ec.europa.eu/eurostat/databrowser/product/view/demo_fabort) is the `demo_fabort` release for all ages, in counts. The explorer normalizes geography codes and omits overlapping geographic variants. Eurostat is not responsible for these modifications. Some countries in the snapshot are available for noncommercial reuse only under [Eurostat’s terms](https://ec.europa.eu/eurostat/help/copyright-notice). The Guttmacher originals follow its [public-use dataset terms](https://www.guttmacher.org/public-use-datasets). Stats NZ and the New Zealand Ministry of Health publish their source data under CC BY 4.0.

Run `python3 scripts/fetch_references.py` online to fill in missing downloads. The script reuses local copies whose checksums match the manifest. If a publisher changed a file, use `--refresh` to accept a newer copy. Read the saved report or dataset version when comparing published figures. Restoring the 2017 fetal-tissue judgment excerpt from its source filing requires `qpdf`. To download a case file or a specific source, pass its ID from `references/sources.tsv` as `--source ID`. Repeat the flag for multiple records. The same flag limits `--verify` to those IDs.

## Research roadmap

The [global trend](docs/data/world-trend.json) transcribes Tables 4 and 5 of the [2020 paper’s supplement](references/open/bearak-2020-lancet-appendix.pdf). The two charts use the same six five-year periods and 80% uncertainty intervals. The [2025 conference abstract](https://ipc2025.popconf.org/abstracts/251016) gives a separate 2020–2024 estimate. The related 2025 peer-reviewed study tabulates undesired births and ratios of abortions to undesired births. Its appendix does not report a replacement series of total abortions with uncertainty bounds. The research page also records what the education, cost, health and grant sources can currently establish.

1. **Update the global series.** Check for a peer-reviewed successor to the conference abstract and obtain the new historical tables, definitions and uncertainty intervals. Compare estimates within one model version. Record annual averages and population rates together. Audit the coverage and missing years of each continent’s reported series before calculating regional totals.
2. **Measure campus use and outreach.** Start with California’s UC and CSU reports, request aggregate counts of eligible students and referrals, and document coverage and reporting periods. Look for student health procurement, public ad archives, and academic surveys that ask enrollment directly. Record sponsor, audience, spending, referrals and measured effects as separate fields.
3. **Trace costs, jobs and taxes.** Start with a defined policy and jurisdiction. Collect household expenses, insurer and program reimbursements, time away from work and public administrative costs. For employment, tax and long-run spending estimates, name the comparison group, time horizon and assumptions about subsequent births. Document transfers so costs are counted once.
4. **Extend the health follow-up.** Compare primary studies by method, number of previous procedures, prior health, comparison group and length of follow-up. Track complications, mental health, later fertility and later pregnancy intentions separately. For coercion, record whether each source measures an allegation, a case outcome or a population prevalence estimate.
5. **Reconstruct the grant and payment trail.** Download NIH RePORTER project and publication exports and check federal award and subaward records. Join documented award IDs to publications. Keep award, procurement, tissue transfer and commercial revenue in separate fields. Record a transaction only when a source identifies the parties and what changed hands. The University of Washington repository trail now includes the archived NIH award export and a USAspending subaward record. Next, look for the subaward agreement, scope of work and any public procurement records before classifying the downstream expenses.

For each addition, register the original URL in `references/sources.tsv` and run `python3 scripts/fetch_references.py --source ID`. Record the table, page or case record, the date range and what the source counts. Use `--verify --source ID` to check the local copy, then run the checks below. Save distributable copies under `references/open` and restricted copies in the local archive. The manifest records the download status and checksum so another researcher can resume from the same record.

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
