"""Read prepared scores and preserve original display/evidence metadata."""

import bisect
import csv
import hashlib
import math
import re
from pathlib import Path

from .contracts import ALL_FEATURES


class DataError(ValueError):
    """The source snapshot violates its schema."""


def read_rows(path: Path, required: set[str]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or required - set(columns):
            raise DataError(
                f"{path.name}: duplicate columns or missing required fields {required}."
            )
        rows = list(reader)
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise DataError(f"{path.name}: malformed CSV row.")
        if not re.fullmatch(r"[0-9]{5}", row["zip"]):
            raise DataError(f"{path.name}: invalid ZIP {row['zip']!r}.")
    return rows


def number(value: str) -> float | None:
    if not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise DataError(f"Invalid numeric value {value!r}.") from exc
    return parsed if math.isfinite(parsed) else None


def unique(rows: list[dict], key: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        if not row[key] or row[key] in result:
            raise DataError(f"Empty or duplicate {key}: {row[key]!r}.")
        result[row[key]] = row
    return result


def load_snapshot(directory: Path) -> tuple[list[dict], dict[str, list[dict]], dict]:
    paths = [
        directory / name
        for name in ("area_features_cleaned.csv", "area_features.csv", "crowd_text_snippets.csv")
    ]
    areas = read_rows(paths[0], {"zip", "median_rent_usd", *ALL_FEATURES})
    if not areas:
        raise DataError("Prepared area table is empty.")
    unique(areas, "zip")
    names = unique(read_rows(paths[1], {"zip", "area_name"}), "zip")
    for area in areas:
        area["area_name"] = names.get(area["zip"], {}).get("area_name") or area["zip"]
        for feature in ALL_FEATURES:
            value = number(area[feature])
            if value is not None and not 0 <= value <= 1:
                raise DataError(f"{area['zip']}: {feature} must be between 0 and 1.")
            area[feature] = value
        rent = number(area["median_rent_usd"])
        area["median_rent_usd"] = rent if rent is not None and rent > 0 else None
    snippets = read_rows(paths[2], {"snippet_id", "zip", "source", "theme", "text"})
    unique(snippets, "snippet_id")
    evidence = {}
    for snippet in snippets:
        if not all(snippet[field].strip() for field in ("source", "theme", "text")):
            raise DataError("Demo evidence must preserve source label, theme and text.")
        evidence.setdefault(snippet["zip"], []).append(
            {
                "evidence_id": snippet["snippet_id"],
                "theme": snippet["theme"],
                "text": snippet["text"],
                "source_label": snippet["source"],
                "is_demo": True,
                "polarity": "unknown",
            }
        )
    versions = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    return areas, evidence, versions


CENSUS_COLUMNS = {
    "zip",
    "workers",
    "transit_commuters",
    "walk_commuters",
    "food_drink_establishments",
    "noise_share_ge_55db",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator else None


def percentiles(values: dict[str, float | None]) -> dict[str, float | None]:
    """Position among known values, 0-1; equal values share a percentile."""
    known = sorted(v for v in values.values() if v is not None)
    top = max(len(known) - 1, 1)
    return {z: None if v is None else bisect.bisect_left(known, v) / top for z, v in values.items()}


def load_places(directory: Path) -> tuple[dict, dict, dict]:
    """Optional ZIP geography and neighborhood-name dictionary; empty when absent."""
    paths = [directory / "zcta_geography.csv", directory / "neighborhood_aliases.csv"]
    if not all(path.exists() for path in paths):
        return {}, {}, {}
    geography = {
        z: {
            "land_sqmi": number(row["land_sqmi"]),
            "lat": number(row["lat"]),
            "lon": number(row["lon"]),
            "usps_city": row["usps_city"].strip() or None,
        }
        for z, row in unique(
            read_rows(paths[0], {"zip", "land_sqmi", "lat", "lon", "usps_city"}), "zip"
        ).items()
    }
    aliases = {}
    for row in read_rows(paths[1], {"alias", "zip", "source"}):
        key = normalize_name(row["alias"])
        if not key:
            raise DataError("neighborhood_aliases.csv: empty alias.")
        entry = aliases.setdefault(key, {"label": row["alias"].strip(), "zips": []})
        if row["zip"] not in entry["zips"]:
            entry["zips"].append(row["zip"])
    return geography, aliases, {path.name: digest(path) for path in paths}


def apply_census(directory: Path, areas: list[dict], geography: dict) -> dict:
    """Replace the placeholder lifestyle scores with measured ones (percentiles).

    transit  = share of workers commuting by public transit      ACS 2018-22 B08301
    social   = restaurants and bars per sq mi                    ZIP Business Patterns 2021
    walkable = share of workers who walk to work                 ACS 2018-22 B08301
    quiet    = 1 - share of land at >= 55 dB road/aviation noise  BTS noise map 2020
    pet_friendly and co_living_friendly keep their provided values. Choices were
    made with experiments/feature_candidates/decisions.py.
    """
    if not geography:
        raise DataError("The census feature set needs zcta_geography.csv for land area.")
    path = directory / "census_features.csv"
    rows = unique(read_rows(path, CENSUS_COLUMNS), "zip")
    measures = {}
    for area in areas:
        row = rows.get(area["zip"], {})
        land = geography.get(area["zip"], {}).get("land_sqmi")

        def get(column, row=row):
            return number(row[column]) if row else None

        noise = get("noise_share_ge_55db")
        if noise is not None and not 0 <= noise <= 1:
            raise DataError(f"{area['zip']}: noise_share_ge_55db must be between 0 and 1.")
        measures[area["zip"]] = {
            "transit_commute_share": ratio(get("transit_commuters"), get("workers")),
            "food_drink_per_sqmi": ratio(get("food_drink_establishments"), land),
            "walk_commute_share": ratio(get("walk_commuters"), get("workers")),
            "noise_share_ge_55db": noise,
        }
    pct = {
        name: percentiles({z: m[name] for z, m in measures.items()})
        for name in next(iter(measures.values()))
    }
    for area in areas:
        z = area["zip"]
        loud = pct["noise_share_ge_55db"][z]
        area.update(
            transit=pct["transit_commute_share"][z],
            social=pct["food_drink_per_sqmi"][z],
            walkable=pct["walk_commute_share"][z],
            quiet=None if loud is None else 1 - loud,
            measures=measures[z],
        )
    return {path.name: digest(path)}
