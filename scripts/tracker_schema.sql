PRAGMA user_version = 5;

CREATE TABLE build_input (
    path TEXT PRIMARY KEY NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0)
) WITHOUT ROWID;

CREATE TABLE source (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    access TEXT NOT NULL CHECK (access IN ('open', 'private')),
    retrieved TEXT NOT NULL,
    archive_status TEXT NOT NULL CHECK (archive_status IN ('saved', 'failed')),
    archive_path TEXT,
    archive_sha256 TEXT CHECK (length(archive_sha256) = 64),
    archive_bytes INTEGER CHECK (archive_bytes > 0),
    archive_error TEXT,
    CHECK (
        (archive_status = 'saved' AND archive_path IS NOT NULL
            AND archive_sha256 IS NOT NULL AND archive_bytes IS NOT NULL)
        OR
        (archive_status = 'failed' AND archive_path IS NULL
            AND archive_sha256 IS NULL AND archive_bytes IS NULL)
    )
) WITHOUT ROWID;

CREATE TABLE world_trend (
    source_id TEXT NOT NULL REFERENCES source (id),
    first_year INTEGER NOT NULL CHECK (first_year > 0),
    last_year INTEGER NOT NULL CHECK (last_year >= first_year),
    published INTEGER NOT NULL CHECK (published >= last_year),
    interval_percent INTEGER NOT NULL CHECK (interval_percent BETWEEN 1 AND 99),
    annual_millions REAL NOT NULL,
    annual_millions_low REAL NOT NULL CHECK (annual_millions_low >= 0),
    annual_millions_high REAL NOT NULL,
    rate_per_1000 REAL NOT NULL,
    rate_low REAL NOT NULL CHECK (rate_low >= 0),
    rate_high REAL NOT NULL,
    CHECK (annual_millions BETWEEN annual_millions_low AND annual_millions_high),
    CHECK (rate_per_1000 BETWEEN rate_low AND rate_high),
    PRIMARY KEY (source_id, first_year, last_year)
) WITHOUT ROWID;

CREATE TABLE evidence_record (
    id TEXT PRIMARY KEY NOT NULL,
    place TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year > 0),
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    limits TEXT NOT NULL,
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90)
) WITHOUT ROWID;

CREATE TABLE evidence_source (
    record_id TEXT NOT NULL REFERENCES evidence_record (id),
    source_id TEXT NOT NULL REFERENCES source (id),
    PRIMARY KEY (record_id, source_id)
) WITHOUT ROWID;

CREATE TABLE material_payment (
    id TEXT PRIMARY KEY NOT NULL,
    period TEXT NOT NULL,
    payer TEXT NOT NULL,
    recipient TEXT NOT NULL,
    purpose TEXT NOT NULL,
    amount TEXT NOT NULL,
    scope TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE material_payment_source (
    payment_id TEXT NOT NULL REFERENCES material_payment (id),
    source_id TEXT NOT NULL REFERENCES source (id),
    PRIMARY KEY (payment_id, source_id)
) WITHOUT ROWID;

CREATE TABLE series (
    id TEXT PRIMARY KEY NOT NULL,
    label TEXT NOT NULL,
    scope TEXT NOT NULL,
    geography TEXT NOT NULL CHECK (geography IN ('country', 'us', 'state', 'county'))
) WITHOUT ROWID;

CREATE TABLE series_source (
    series_id TEXT NOT NULL REFERENCES series(id),
    source_id TEXT NOT NULL REFERENCES source(id),
    first_year INTEGER,
    last_year INTEGER,
    citation_label TEXT,
    citation_url TEXT,
    PRIMARY KEY (series_id, source_id),
    CHECK (first_year IS NULL AND last_year IS NULL OR
           first_year IS NOT NULL AND last_year IS NOT NULL AND first_year <= last_year)
) WITHOUT ROWID;

CREATE TABLE country (
    id INTEGER PRIMARY KEY,
    iso3 TEXT CHECK (length(iso3) = 3) UNIQUE,
    name TEXT NOT NULL,
    region TEXT
);

CREATE TABLE country_estimate (
    country_id INTEGER NOT NULL REFERENCES country(id),
    series_id TEXT NOT NULL REFERENCES series(id),
    profile_source_id TEXT REFERENCES source(id),
    first_year INTEGER NOT NULL,
    last_year INTEGER NOT NULL CHECK (last_year >= first_year),
    abortions INTEGER NOT NULL CHECK (abortions >= 0),
    abortions_low INTEGER NOT NULL CHECK (abortions_low BETWEEN 0 AND abortions),
    abortions_high INTEGER NOT NULL CHECK (abortions_high >= abortions),
    rate REAL NOT NULL CHECK (rate >= 0),
    rate_low REAL NOT NULL CHECK (rate_low BETWEEN 0 AND rate),
    rate_high REAL NOT NULL CHECK (rate_high >= rate),
    births INTEGER NOT NULL CHECK (births >= 0),
    share_of_births_plus_abortions REAL NOT NULL CHECK (share_of_births_plus_abortions BETWEEN 0 AND 100),
    share_unintended_aborted REAL CHECK (share_unintended_aborted BETWEEN 0 AND 100),
    PRIMARY KEY (country_id, series_id, first_year, last_year)
) WITHOUT ROWID;

CREATE TABLE country_gdp (
    country_id INTEGER NOT NULL REFERENCES country(id),
    series_id TEXT NOT NULL REFERENCES series(id),
    year INTEGER NOT NULL,
    gdp_per_capita_usd INTEGER NOT NULL CHECK (gdp_per_capita_usd >= 0),
    PRIMARY KEY (country_id, series_id, year)
) WITHOUT ROWID;

CREATE TABLE country_reported (
    country_id INTEGER NOT NULL REFERENCES country(id),
    series_id TEXT NOT NULL REFERENCES series(id),
    year INTEGER NOT NULL,
    abortions INTEGER NOT NULL CHECK (abortions >= 0),
    PRIMARY KEY (country_id, series_id, year)
) WITHOUT ROWID;

CREATE TABLE country_reported_publisher (
    country_id INTEGER NOT NULL,
    series_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    publisher TEXT NOT NULL,
    PRIMARY KEY (country_id, series_id, year, publisher),
    FOREIGN KEY (country_id, series_id, year) REFERENCES country_reported(country_id, series_id, year)
) WITHOUT ROWID;

CREATE TABLE international_geography (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    continent TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE international_observation (
    geography_id TEXT NOT NULL REFERENCES international_geography(id),
    series_id TEXT NOT NULL REFERENCES series(id),
    year INTEGER NOT NULL,
    abortions INTEGER NOT NULL CHECK (abortions >= 0),
    status TEXT,
    notes TEXT,
    source_id TEXT NOT NULL REFERENCES source(id),
    PRIMARY KEY (geography_id, series_id, year)
) WITHOUT ROWID;

CREATE TABLE us_observation (
    series_id TEXT NOT NULL REFERENCES series(id),
    year INTEGER NOT NULL,
    abortions INTEGER NOT NULL CHECK (abortions >= 0),
    rate REAL CHECK (rate >= 0),
    reporting_areas INTEGER CHECK (reporting_areas > 0),
    abortions_low INTEGER CHECK (abortions_low BETWEEN 0 AND abortions),
    abortions_high INTEGER CHECK (abortions_high >= abortions),
    PRIMARY KEY (series_id, year),
    CHECK ((abortions_low IS NULL) = (abortions_high IS NULL))
) WITHOUT ROWID;

CREATE TABLE state (
    fips TEXT PRIMARY KEY NOT NULL CHECK (fips GLOB '[0-9][0-9]'),
    abbr TEXT NOT NULL UNIQUE CHECK (abbr GLOB '[A-Z][A-Z]'),
    name TEXT NOT NULL UNIQUE
) WITHOUT ROWID;

CREATE TABLE state_observation (
    state_fips TEXT NOT NULL REFERENCES state(fips),
    series_id TEXT NOT NULL REFERENCES series(id),
    year INTEGER NOT NULL,
    abortions INTEGER NOT NULL CHECK (abortions >= 0),
    abortions_low INTEGER,
    abortions_high INTEGER,
    rate REAL CHECK (rate >= 0),
    births INTEGER CHECK (births >= 0),
    share_of_births_plus_abortions REAL CHECK (share_of_births_plus_abortions BETWEEN 0 AND 100),
    PRIMARY KEY (state_fips, series_id, year),
    CHECK ((abortions_low IS NULL AND abortions_high IS NULL) OR
           (abortions_low IS NOT NULL AND abortions_high IS NOT NULL
            AND abortions_low BETWEEN 0 AND abortions AND abortions_high >= abortions))
) WITHOUT ROWID;

CREATE TABLE county (
    state_fips TEXT NOT NULL REFERENCES state(fips),
    name TEXT NOT NULL,
    PRIMARY KEY (state_fips, name)
) WITHOUT ROWID;

CREATE TABLE county_series_release (
    state_fips TEXT NOT NULL REFERENCES state(fips),
    year INTEGER NOT NULL,
    series_id TEXT NOT NULL REFERENCES series(id),
    source_id TEXT NOT NULL REFERENCES source(id),
    scope TEXT NOT NULL,
    PRIMARY KEY (state_fips, year, series_id)
) WITHOUT ROWID;

CREATE TABLE county_series_observation (
    state_fips TEXT NOT NULL,
    county_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    series_id TEXT NOT NULL,
    abortions INTEGER CHECK (abortions >= 0),
    status TEXT NOT NULL CHECK (status IN ('reported', 'suppressed')),
    PRIMARY KEY (state_fips, county_name, year, series_id),
    FOREIGN KEY (state_fips, county_name) REFERENCES county(state_fips, name),
    FOREIGN KEY (state_fips, year, series_id) REFERENCES county_series_release(state_fips, year, series_id),
    CHECK ((status = 'suppressed') = (abortions IS NULL))
) WITHOUT ROWID;

CREATE INDEX county_observation_by_release ON county_series_observation (state_fips, year, series_id);

CREATE VIEW county_release AS
SELECT state_fips, year, series_id, source_id, scope
FROM county_series_release
WHERE series_id = 'county-reported';

CREATE VIEW county_observation AS
SELECT state_fips, county_name, year, abortions, status
FROM county_series_observation
WHERE series_id = 'county-reported';
