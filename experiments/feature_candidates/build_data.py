"""Build the external data files the engine reads, from downloaded Census files.

Run from the repo root:
    python experiments/feature_candidates/build_data.py <gazetteer.txt> <census_dir> [out_dir]
out_dir defaults to data/; tests rebuild into a temporary folder and compare.

Inputs (see docs/HANDOFF.md for download URLs):
- 2023 Census Gazetteer ZCTA file (land area, internal point)
- ACS 2018-2022 5-year B08301 (commute mode), filtered to Miami-Dade
- ZIP Code Business Patterns 2021 detail, filtered to Miami-Dade (zbp_miami.csv)
- noise/noise_by_zip.csv from noise.py (BTS 2020 road + aviation noise per ZCTA)
- joana/HUD-SAFMR.csv: HUD Small Area Fair Market Rents by unit size (budget filter)
- joana/area-name.csv and joana/miami_transit.csv: Joana's sourced ZIP names (USPS City
  State Product + Census 2020 ZCTA-to-Place) and GTFS transit service per ZIP, copied from
  origin/joana data/raw/new/ until her data restructure merges

Outputs raw counts only; the engine does all scaling so it stays reviewable.
"""

import csv
import sys
from pathlib import Path

gazetteer, census = Path(sys.argv[1]), Path(sys.argv[2])
data = Path("data")  # inputs
out = Path(sys.argv[3]) if len(sys.argv) > 3 else data  # outputs
out.mkdir(parents=True, exist_ok=True)
zips = [z.strip() for z in (data / "miami_dade_zctas.txt").read_text().splitlines() if z.strip()]


def acs(table):
    with (census / f"{table}.dat").open() as f:
        return {r["GEO_ID"][-5:]: r for r in csv.DictReader(f, delimiter="|")}


geo = {}
with gazetteer.open() as f:
    for row in csv.DictReader(f, delimiter="\t"):
        row = {k.strip(): v.strip() for k, v in row.items()}
        geo[row["GEOID"]] = row
commute = acs("b08301")
noise = {
    r["zip"]: r["share_ge_55"]
    for r in csv.DictReader(open(Path(__file__).parent / "noise" / "noise_by_zip.csv"))
}
estab, city = {}, {}
with (census / "zbp_miami.csv").open() as f:
    for row in csv.DictReader(f):
        estab.setdefault(row["zip"], {})[row["naics"]] = int(row["est"])
        city[row["zip"]] = row["city"].title()

with open(out / "zcta_geography.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow(["zip", "land_sqmi", "lat", "lon", "usps_city"])
    for z in zips:
        if z in geo:
            g = geo[z]
            w.writerow([z, g["ALAND_SQMI"], g["INTPTLAT"], g["INTPTLONG"], city.get(z, "")])

with open(out / "census_features.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow([
        "zip", "workers", "transit_commuters", "walk_commuters",
        "food_drink_establishments", "noise_share_ge_55db",
    ])
    for z in zips:
        if z not in commute:
            continue
        c, e = commute[z], estab.get(z, {})
        w.writerow([
            z, c["B08301_E001"], c["B08301_E010"], c["B08301_E019"],
            e.get("722///", 0), noise.get(z, ""),
        ])

joana = Path(__file__).parent / "joana"
names = {r["zip_code"]: r for r in csv.DictReader(open(joana / "area-name.csv"))}
NAME_SOURCE = "Joana area-name.csv (USPS City State Product; Census 2020 ZCTA-to-Place)"
with open(out / "zip_area_names.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow(["zip", "neighborhood", "other_areas", "area_name_type", "source"])
    for z in zips:
        if z in names:
            r = names[z]
            w.writerow([z, r["primary_area_name"], r["secondary_area_names"], r["area_name_type"], NAME_SOURCE])

hud = {r["zip_code"]: r for r in csv.DictReader(open(joana / "HUD-SAFMR.csv"))}
UNITS = ["efficiency", "one_bedroom", "two_bedroom", "three_bedroom", "four_bedroom"]
with open(out / "rents_hud.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow(["zip", *UNITS, "source"])
    for z in zips:
        if z in hud:
            w.writerow([z, *(hud[z][u] for u in UNITS), "HUD Small Area Fair Market Rents (Joana HUD-SAFMR.csv)"])

service = {r["zip_code"]: r for r in csv.DictReader(open(joana / "miami_transit.csv"))}
with open(out / "transit_service.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow([
        "zip", "transit_stops", "routes", "metrorail_routes", "metromover_routes",
        "weekday_departures", "weekday_median_headway_minutes", "data_as_of",
    ])
    for z in zips:
        if z in service:
            r = service[z]
            w.writerow([
                z, r["transit_stop_count"], r["unique_route_count"], r["metrorail_route_count"],
                r["metromover_route_count"], r["weekday_departures"],
                r["weekday_median_headway_minutes"], r["data_as_of"],
            ])

# match: primary names define where a place is; secondary names (areas a ZIP also
# touches) are used only when no primary name matches.
aliases = {}
for r in csv.DictReader(open(data / "area_features.csv")):
    if not r["area_name"].startswith("ZCTA5"):
        aliases.setdefault((r["area_name"], r["zip"]), ("primary", "area_features.csv area_name"))
for z in zips:
    if city.get(z):
        aliases.setdefault((city[z], z), ("primary", "USPS city, ZIP Code Business Patterns 2021"))
for z, r in names.items():
    if z in zips:
        aliases.setdefault((r["primary_area_name"], z), ("primary", NAME_SOURCE))
for z, r in names.items():
    if z in zips:
        for other in filter(None, (n.strip() for n in r["secondary_area_names"].split("|"))):
            aliases.setdefault((other, z), ("secondary", NAME_SOURCE))
with open(out / "neighborhood_aliases.csv", "w", newline="", encoding="utf-8") as target:
    w = csv.writer(target)
    w.writerow(["alias", "zip", "match", "source"])
    for (alias, z), (match, source) in sorted(aliases.items()):
        w.writerow([alias, z, match, source])
print("wrote zcta_geography.csv, census_features.csv, rents_hud.csv, zip_area_names.csv, transit_service.csv, neighborhood_aliases.csv")
