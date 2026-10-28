"""Build the external data files the engine reads, from downloaded Census files.

Run from the repo root:
    python experiments/feature_candidates/build_data.py <gazetteer.txt> <census_dir>

Inputs (see docs/HANDOFF.md for download URLs):
- 2023 Census Gazetteer ZCTA file (land area, internal point)
- ACS 2018-2022 5-year B08301 (commute mode) and B08201 (vehicles), filtered to Miami-Dade
- ZIP Code Business Patterns 2021 detail, filtered to Miami-Dade (zbp_miami.csv)

Outputs raw counts only; the engine does all scaling so it stays reviewable.
"""

import csv
import sys
from pathlib import Path

gazetteer, census = Path(sys.argv[1]), Path(sys.argv[2])
data = Path("data")
zips = [z.strip() for z in (data / "miami_dade_zctas.txt").read_text().splitlines() if z.strip()]


def acs(table):
    with (census / f"{table}.dat").open() as f:
        return {r["GEO_ID"][-5:]: r for r in csv.DictReader(f, delimiter="|")}


geo = {}
with gazetteer.open() as f:
    for row in csv.DictReader(f, delimiter="\t"):
        row = {k.strip(): v.strip() for k, v in row.items()}
        geo[row["GEOID"]] = row
commute, vehicles = acs("b08301"), acs("b08201")
estab, city = {}, {}
with (census / "zbp_miami.csv").open() as f:
    for row in csv.DictReader(f):
        estab.setdefault(row["zip"], {})[row["naics"]] = int(row["est"])
        city[row["zip"]] = row["city"].title()
population = {
    r["zip"]: r["population"] for r in csv.DictReader(open(data / "public_features_cleaned.csv"))
}

with open(data / "zcta_geography.csv", "w", newline="", encoding="utf-8") as out:
    w = csv.writer(out)
    w.writerow(["zip", "land_sqmi", "lat", "lon", "usps_city"])
    for z in zips:
        if z in geo:
            g = geo[z]
            w.writerow([z, g["ALAND_SQMI"], g["INTPTLAT"], g["INTPTLONG"], city.get(z, "")])

with open(data / "census_features.csv", "w", newline="", encoding="utf-8") as out:
    w = csv.writer(out)
    w.writerow([
        "zip", "population", "workers", "transit_commuters", "walk_commuters",
        "households", "households_no_vehicle", "food_drink_establishments", "bar_establishments",
    ])
    for z in zips:
        if z not in commute:
            continue
        c, v, e = commute[z], vehicles[z], estab.get(z, {})
        w.writerow([
            z, population.get(z, ""), c["B08301_E001"], c["B08301_E010"], c["B08301_E019"],
            v["B08201_E001"], v["B08201_E002"], e.get("722///", 0), e.get("7224//", 0),
        ])

aliases = {}
for r in csv.DictReader(open(data / "area_features.csv")):
    if not r["area_name"].startswith("ZCTA5"):
        aliases.setdefault((r["area_name"], r["zip"]), "area_features.csv area_name")
for z in zips:
    if city.get(z):
        aliases.setdefault((city[z], z), "USPS city, ZIP Code Business Patterns 2021")
with open(data / "neighborhood_aliases.csv", "w", newline="", encoding="utf-8") as out:
    w = csv.writer(out)
    w.writerow(["alias", "zip", "source"])
    for (alias, z), source in sorted(aliases.items()):
        w.writerow([alias, z, source])
print("wrote zcta_geography.csv, census_features.csv, neighborhood_aliases.csv")
