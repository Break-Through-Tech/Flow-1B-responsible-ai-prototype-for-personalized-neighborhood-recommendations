"""Read prepared scores and preserve original display/evidence metadata."""

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
