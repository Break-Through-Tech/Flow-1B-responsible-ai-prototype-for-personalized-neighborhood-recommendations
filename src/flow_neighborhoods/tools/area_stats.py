"""area_stats tool: public statistics for one ZIP, or a short list of all ZIPs."""

import csv
import re
from pathlib import Path
from typing import Literal, TypedDict

from ..contracts import ALL_FEATURES, ValidationError
from ..data import DataError
from ..engine import Recommender

PUBLIC_FILE = "public_features_cleaned.csv"

# Friendly name -> column in public_features_cleaned.csv.
PUBLIC_COLUMNS = {
    "population": "population",
    "households": "B11016_001E",
    "owner_occupied_units": "B25003_002E",
    "renter_occupied_units": "B25003_003E",
    "median_rent_usd": "median_rent_usd",
    "median_home_value_usd": "winsorized_B25077_001E",
    "moved_different_house_pct": "winsorized_moved_different_house_pct",
}


class AreaSummary(TypedDict):
    zip: str
    area_name: str
    population: float | None
    median_rent_usd: float | None


class AreaStats(TypedDict):
    zip: str
    status: Literal["ok", "no_public_stats", "unknown_area", "all_areas"]
    area_name: str | None
    public_stats: dict[str, float | None]
    lifestyle_scores: dict[str, float | None]
    constant_scores: list[str]
    areas: list[AreaSummary]
    area_count: int
    warning: str
    guidance: str
    data_version: dict[str, str]


GUIDANCE = (
    "public_stats are public Census/Zillow-style numbers and are the only figures to quote "
    "as facts about the ZIP. lifestyle_scores are 0-to-1 placeholder proxies, not "
    "measurements: never present them as facts, and say any score listed in "
    "constant_scores is identical in every ZIP. A null means unknown, not zero. Home value "
    "and moved-house share are capped to limit outliers. If status is no_public_stats or "
    "unknown_area, say there are no public stats for this ZIP; do not estimate them."
)

WARNING = (
    "Public stats come from the cleaned file: missing values were filled in and outliers "
    "capped, so figures are approximate."
)


def _number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return round(float(value), 4)
    except ValueError:
        return None


def _read_public(data_dir: Path) -> dict[str, dict[str, float | None]]:
    path = Path(data_dir) / PUBLIC_FILE
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = [
                c for c in ("zip", *PUBLIC_COLUMNS.values()) if c not in (reader.fieldnames or [])
            ]
            if missing:
                raise DataError(f"{PUBLIC_FILE} is missing columns: {', '.join(missing)}")
            return {
                row["zip"].strip(): {
                    name: _number(row[column]) for name, column in PUBLIC_COLUMNS.items()
                }
                for row in reader
            }
    except FileNotFoundError as exc:
        raise DataError(f"{PUBLIC_FILE} is missing from the data folder") from exc
    except UnicodeDecodeError as exc:
        raise DataError(f"{PUBLIC_FILE} is not valid UTF-8 text") from exc


def area_stats(engine: Recommender, data_dir: Path, zip_code: str = "") -> AreaStats:
    """Public stats for one ZIP, or a short summary of every ZIP when zip_code is blank.

    status: ok, no_public_stats (known ZIP with no public row), unknown_area (ZIP not in
    the snapshot) or all_areas (blank input). Malformed input raises ValidationError.
    """
    if not isinstance(zip_code, str):
        raise ValidationError(f"zip_code must be text, got {zip_code!r}")
    zip_code = zip_code.strip()
    if zip_code and not re.fullmatch(r"[0-9]{5}", zip_code):
        raise ValidationError(
            f"zip_code must be a five-digit ZIP such as '33130', got {zip_code!r}. "
            "Look up the ZIP for a neighborhood name first, or leave it blank for all ZIPs."
        )
    public = _read_public(data_dir)
    areas = {area["zip"]: area for area in engine.areas}
    result: AreaStats = {
        "zip": zip_code,
        "status": "all_areas",
        "area_name": None,
        "public_stats": {},
        "lifestyle_scores": {},
        "constant_scores": [],
        "areas": [],
        "area_count": 0,
        "warning": WARNING,
        "guidance": GUIDANCE,
        "data_version": dict(engine.data_version),
    }
    if not zip_code:
        result["areas"] = [
            {
                "zip": code,
                "area_name": area["area_name"],
                "population": public.get(code, {}).get("population"),
                "median_rent_usd": area["median_rent_usd"],
            }
            for code, area in sorted(areas.items())
        ]
        result["area_count"] = len(result["areas"])
        return result
    area = areas.get(zip_code)
    if area is None:
        result["status"] = "unknown_area"
        return result
    result["area_name"] = area["area_name"]
    result["lifestyle_scores"] = {name: area.get(name) for name in ALL_FEATURES}
    result["constant_scores"] = sorted(engine.constant_features)
    if zip_code in public:
        result["status"] = "ok"
        result["public_stats"] = public[zip_code]
    else:
        result["status"] = "no_public_stats"
    return result
