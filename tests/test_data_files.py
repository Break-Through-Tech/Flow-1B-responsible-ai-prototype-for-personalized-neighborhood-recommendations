"""Checks on the committed data files: coverage, ranges, provenance and reproducibility."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / "experiments" / "feature_candidates"
UNITS = ["efficiency", "one_bedroom", "two_bedroom", "three_bedroom", "four_bedroom"]
BUILT = [
    "zcta_geography.csv",
    "census_features.csv",
    "rents_hud.csv",
    "zip_area_names.csv",
    "transit_service.csv",
    "neighborhood_aliases.csv",
]


def rows(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def by_zip(name):
    table = {}
    for row in rows(name):
        assert row["zip"] not in table, f"{name}: duplicate ZIP {row['zip']}"
        table[row["zip"]] = row
    return table


SNAPSHOT = by_zip("area_features_cleaned.csv")
COUNTY = {z.strip() for z in (DATA / "miami_dade_zctas.txt").read_text().splitlines() if z.strip()}


def test_snapshot_zips_are_county_zctas():
    assert set(SNAPSHOT) <= COUNTY
    assert len(SNAPSHOT) == 80


def test_hud_rents_cover_snapshot_and_rise_with_unit_size():
    hud = by_zip("rents_hud.csv")
    assert set(SNAPSHOT) <= set(hud)
    for z, row in hud.items():
        values = [float(row[u]) for u in UNITS]
        assert all(v > 0 for v in values), z
        assert values == sorted(values), f"{z}: HUD rent should not fall as units grow"
        assert row["source"].startswith("HUD Small Area Fair Market Rents")


def test_census_measures_are_complete_and_consistent():
    census = by_zip("census_features.csv")
    assert set(census) == set(SNAPSHOT)
    for z, row in census.items():
        workers = float(row["workers"])
        assert 0 <= float(row["transit_commuters"]) + float(row["walk_commuters"]) <= workers, z
        assert float(row["food_drink_establishments"]) >= 0, z
        assert 0 <= float(row["noise_share_ge_55db"]) <= 1, z


def test_geography_is_inside_miami_dade():
    geography = by_zip("zcta_geography.csv")
    assert set(SNAPSHOT) <= set(geography)
    for z, row in geography.items():
        assert float(row["land_sqmi"]) > 0, z
        assert 25.1 <= float(row["lat"]) <= 26.1 and -81.0 <= float(row["lon"]) <= -80.0, z


def test_names_aliases_and_transit_reference_known_zips():
    names = by_zip("zip_area_names.csv")
    assert set(SNAPSHOT) <= set(names)
    assert all(row["neighborhood"].strip() and row["source"].strip() for row in names.values())
    aliases = rows("neighborhood_aliases.csv")
    assert {row["zip"] for row in aliases} <= COUNTY
    assert {row["match"] for row in aliases} == {"primary", "secondary"}
    assert all(row["alias"].strip() and row["source"].strip() for row in aliases)
    for z, row in by_zip("transit_service.csv").items():
        assert z in COUNTY
        assert all(float(row[c]) >= 0 for c in ("transit_stops", "routes", "weekday_departures"))


def test_co_living_listings_are_unique_sourced_and_priced():
    listings = rows("co_living_listings.csv")
    names = [row["property"].strip().lower() for row in listings]
    assert len(names) == len(set(names)), "each property is counted once"
    for row in listings:
        assert row["zip"] in COUNTY
        low, high = float(row["per_bedroom_rent_from"]), float(row["per_bedroom_rent_to"])
        assert 0 < low <= high, row["property"]
        assert row["sources"].strip() and row["observed"].strip()


INPUTS = [
    CACHE / "census" / "2023_Gaz_zcta_national.txt",
    CACHE / "census" / "b08301.dat",
    CACHE / "census" / "zbp_miami.csv",
    CACHE / "noise" / "noise_by_zip.csv",
    CACHE / "joana" / "HUD-SAFMR.csv",
    CACHE / "joana" / "area-name.csv",
    CACHE / "joana" / "miami_transit.csv",
]


def test_build_script_reproduces_committed_files(tmp_path):
    missing = [str(p.relative_to(ROOT)) for p in INPUTS if not p.exists()]
    if missing:
        pytest.skip(
            "raw downloads are not committed; see docs/HANDOFF.md to fetch: " + ", ".join(missing)
        )
    subprocess.run(
        [
            sys.executable,
            str(CACHE / "build_data.py"),
            str(INPUTS[0]),
            str(CACHE / "census"),
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for name in BUILT:
        assert (tmp_path / name).read_bytes() == (DATA / name).read_bytes(), name
