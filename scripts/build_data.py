#!/usr/bin/env python3
"""Build docs/data/countries.json from the archived sources."""
import csv, json, pathlib, re, subprocess, unicodedata
import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF = ROOT / "references" / "private"
RAW = ROOT / "data" / "raw"

def key(name):
    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", n)

# The input table spells these differently from the published estimates (ISO 3166-1 numeric).
ISO_OVERRIDES = {"Bolivia": 68, "Côte d'Ivoire": 384, "DR Congo": 180, "Hong Kong": 344, "Laos": 418,
                 "Moldova": 498, "Russia": 643, "Réunion": 638, "South Korea": 410, "Tanzania": 834,
                 "United Kingdom": 826, "United States": 840}

def table(sheet):
    """Read name, estimate, 80% interval triplets from side-by-side regional blocks."""
    out = {}
    for raw in sheet.iter_rows(values_only=True):
        row = [c for c in raw if c is not None]
        for i in range(len(row) - 2):
            name, val, ui = row[i], row[i + 1], row[i + 2]
            if isinstance(name, str) and isinstance(val, (int, float)) and isinstance(ui, str):
                m = re.match(r"\((\d+) to (\d+)\)", ui)
                if m:
                    out[name.strip()] = (val, int(m[1]), int(m[2]))
    return out

wb = openpyxl.load_workbook(ROOT / "references/open/bearak-2022-supp-tables.xlsx", read_only=True, data_only=True)
rates = table(wb["A5. Abortion rates"])
share = table(wb["A4. Pct aborted"])

iso = {}
for row in wb["C1. Data"].iter_rows(min_row=3, values_only=True):
    if row[0] and row[1]:
        iso[key(row[0])] = int(row[1])

def covariates(pdf):
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    get = lambda label: next(([float(v) for v in l.split(label)[1].split()[-6:]]
                              for l in text.splitlines() if label in l), None)
    return get("Number of women 15-49 in 1000s"), get("Annual number of births in 1000s")

profiles = {key(p.stem): p for p in (REF / "country-profiles").glob("*.pdf")}
meta = {int(c["ccn3"]): c for c in json.load(open(RAW / "world-countries.json", encoding="utf8")) if c.get("ccn3")}
gdp = {r["countryiso3code"]: r["value"] for r in json.load(open(RAW / "wb-gdp-per-capita-2023.json"))[1] if r["value"]}

reported = {}
for r in csv.DictReader(open(ROOT / "references/private/osf-global-incidence-csv.csv", encoding="latin-1")):
    if r["yearstart"] != r["yearend"] or r["datatype"] != "Official Statistics" or r["complete"] != "Complete":
        continue
    if r["numberofabortions"] and r["marriedonly"] in ("", "No"):
        try:
            reported.setdefault(int(r["iso"]), {})[int(r["yearstart"])] = int(float(r["numberofabortions"]))
        except ValueError:
            pass

countries, unmatched = [], []
SUMMARY_ROWS = {"first quartile", "median country", "population average", "third quartile"}
for name, (rate, lo, hi) in sorted(rates.items()):
    if name in SUMMARY_ROWS:
        continue
    k = key(name)
    code = ISO_OVERRIDES.get(name) or iso.get(k)
    prof = profiles.get(k)
    if code is None or prof is None:
        unmatched.append(name)
        continue
    women, births = covariates(prof)
    if not women or not births:
        unmatched.append(name)
        continue
    w, b = round(women[-1] * 1000), round(births[-1] * 1000)
    n = rate * w / 1000
    m = meta.get(code, {})
    g = gdp.get(m.get("cca3"))
    countries.append({
        "id": code, "name": name, "iso3": m.get("cca3"), "region": m.get("region"),
        "rate": round(rate, 1), "rateLow": min(lo, round(rate, 1)), "rateHigh": max(hi, round(rate, 1)),
        "abortions": int(round(n, -2)), "abortionsLow": int(round(min(lo, rate) * w / 1000, -2)), "abortionsHigh": int(round(max(hi, rate) * w / 1000, -2)),
        "births": b, "shareOfBirthsPlusAbortions": round(100 * n / (n + b), 1),
        "shareUnintendedAborted": round(share[name][0], 1) if name in share else None,
        "gdpPerCapita2023": round(g) if g else None,
        "reported": sorted(reported.get(code, {}).items()),
    })

(ROOT / "docs/data/countries.json").write_text(json.dumps(countries, ensure_ascii=False, separators=(",", ":")))
print(len(rates), "rates;", len(countries), "built; unmatched:", unmatched)
print("sum abortions (M):", round(sum(c["abortions"] for c in countries) / 1e6, 1), "with trend:", sum(bool(c["reported"]) for c in countries))
for n in ("United States", "China", "India", "Brazil", "Russia", "Nigeria"):
    c = next((c for c in countries if c["name"] == n), None)
    print(n, c and {k: c[k] for k in ("rate", "rateLow", "rateHigh", "abortions", "births", "shareOfBirthsPlusAbortions", "gdpPerCapita2023")}, c and len(c["reported"]))

us = [r for r in csv.DictReader(open(REF / "osf-us-pregnancy-csv.csv", encoding="latin-1")) if r["state"] == "US"]
series = [{"year": int(r["year"]), "abortions": int(r["abortionstotal"]), "rate": float(r["abortionratetotal"])}
          for r in us if r["abortionstotal"] and r["abortionratetotal"]]
(ROOT / "docs/data/us.json").write_text(json.dumps(series, separators=(",", ":")))
print("us years", series[0]["year"], series[-1]["year"], len(series))

FIPS = {"AL":("01","Alabama"),"AK":("02","Alaska"),"AZ":("04","Arizona"),"AR":("05","Arkansas"),"CA":("06","California"),"CO":("08","Colorado"),"CT":("09","Connecticut"),"DE":("10","Delaware"),"DC":("11","District of Columbia"),"FL":("12","Florida"),"GA":("13","Georgia"),"HI":("15","Hawaii"),"ID":("16","Idaho"),"IL":("17","Illinois"),"IN":("18","Indiana"),"IA":("19","Iowa"),"KS":("20","Kansas"),"KY":("21","Kentucky"),"LA":("22","Louisiana"),"ME":("23","Maine"),"MD":("24","Maryland"),"MA":("25","Massachusetts"),"MI":("26","Michigan"),"MN":("27","Minnesota"),"MS":("28","Mississippi"),"MO":("29","Missouri"),"MT":("30","Montana"),"NE":("31","Nebraska"),"NV":("32","Nevada"),"NH":("33","New Hampshire"),"NJ":("34","New Jersey"),"NM":("35","New Mexico"),"NY":("36","New York"),"NC":("37","North Carolina"),"ND":("38","North Dakota"),"OH":("39","Ohio"),"OK":("40","Oklahoma"),"OR":("41","Oregon"),"PA":("42","Pennsylvania"),"RI":("44","Rhode Island"),"SC":("45","South Carolina"),"SD":("46","South Dakota"),"TN":("47","Tennessee"),"TX":("48","Texas"),"UT":("49","Utah"),"VT":("50","Vermont"),"VA":("51","Virginia"),"WA":("53","Washington"),"WV":("54","West Virginia"),"WI":("55","Wisconsin"),"WY":("56","Wyoming")}
rows = [r for r in csv.DictReader(open(REF / "osf-us-pregnancy-csv.csv", encoding="latin-1")) if r["state"] in FIPS and r["abortionstotal"]]
states = []
for abbr, (fips, name) in FIPS.items():
    s = sorted((r for r in rows if r["state"] == abbr), key=lambda r: int(r["year"]))
    last = s[-1]
    a, b = int(last["abortionstotal"]), int(last["birthstotal"])
    states.append({"id": fips, "abbr": abbr, "name": name, "year": int(last["year"]), "abortions": a, "rate": float(last["abortionratetotal"]),
                   "births": b, "shareOfBirthsPlusAbortions": round(100 * a / (a + b), 1),
                   "total2005to2020": sum(int(r["abortionstotal"]) for r in s if int(r["year"]) >= 2005),
                   "reported": [[int(r["year"]), int(r["abortionstotal"])] for r in s]})
(ROOT / "docs/data/states.json").write_text(json.dumps(states, separators=(",", ":")))
print("states", len(states), "2020 sum", sum(x["abortions"] for x in states), "rate range", min(x["rate"] for x in states), max(x["rate"] for x in states), "share range", min(x["shareOfBirthsPlusAbortions"] for x in states), max(x["shareOfBirthsPlusAbortions"] for x in states), "count range", min(x["abortions"] for x in states), max(x["abortions"] for x in states))
