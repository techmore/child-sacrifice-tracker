# Three in Ten

A sourced social and philosophical inquiry that sets the modern abortion debate beside the historic record of child sacrifice, family structure and resilience.

The site lives in `docs/` and is a static page with no build step.

## Data

- **Country estimates:** Bearak et al. 2022, BMJ Global Health, annual averages for 2015 to 2019 (CC BY-NC 4.0).
- **US series:** Guttmacher Institute national and state estimates, 1973 to 2020.
- **Economic context:** World Bank GDP per capita, 2023.

Rebuild the data with `python3 scripts/build_data.py`. It needs `openpyxl`, `pdftotext` and the local reference archive.

## References

`references/sources.tsv` lists every source. `references/manifest.json` records retrieval dates and checksums.
Open-licensed copies are committed in `references/open/`. Copyrighted copies stay in the git-ignored `references/private/`. Run `python3 scripts/fetch_references.py` to rebuild the archive.

## Conduct

This project does not list clinics, hospitals or staff, and it will not accept contributions that do. Direct disagreement to lawmakers and public argument. Never harass or threaten patients or providers.

## License

Project code and writing are for noncommercial use because the country estimates are CC BY-NC 4.0. Third-party data and documents keep their own licenses.
