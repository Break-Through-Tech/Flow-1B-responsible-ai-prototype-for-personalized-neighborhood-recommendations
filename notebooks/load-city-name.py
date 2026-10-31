"""Create a ZIP-to-city lookup for the project's Miami-Dade ZCTAs."""

from pathlib import Path

import pandas as pd
import pgeocode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ZCTA_PATH = DATA_DIR / "raw" / "miami_dade_zctas.txt"
OUTPUT_PATH = DATA_DIR / "cleaned" / "new" / "city-name.csv"


def load_allowed_zips() -> list[str]:
    """Load unique five-character ZIP codes from the project allowlist."""
    values = {
        line.strip().zfill(5)
        for line in ZCTA_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if not values:
        raise ValueError(f"ZIP allowlist is empty: {ZCTA_PATH}")
    return sorted(values)


def build_city_lookup(zip_codes: list[str]) -> pd.DataFrame:
    """Look up postal city metadata for each allowed ZIP code."""
    metadata = pgeocode.Nominatim("us").query_postal_code(zip_codes)

    result = metadata[
        [
            "postal_code",
            "place_name",
            "county_name",
            "state_code",
            "latitude",
            "longitude",
        ]
    ].rename(
        columns={
            "postal_code": "zip_code",
            "place_name": "city_name",
        }
    )
    result["zip_code"] = result["zip_code"].astype("string").str.zfill(5)
    result["area_name"] = result["city_name"]
    result["area_name_type"] = "postal_city"
    result["source"] = "pgeocode US postal metadata"

    missing = result["city_name"].isna() | result["county_name"].isna()
    if missing.any():
        missing_zips = result.loc[missing, "zip_code"].tolist()
        raise ValueError(f"ZIP metadata is missing city or county values: {missing_zips}")

    return result[
        [
            "zip_code",
            "city_name",
            "area_name",
            "area_name_type",
            "county_name",
            "state_code",
            "latitude",
            "longitude",
            "source",
        ]
    ].sort_values("zip_code").reset_index(drop=True)


def validate_output(city_lookup: pd.DataFrame, allowed_zips: list[str]) -> None:
    """Verify one complete row exists for every allowed ZIP code."""
    expected = set(allowed_zips)
    actual = set(city_lookup["zip_code"])
    if actual != expected:
        raise ValueError(
            f"Output ZIP coverage differs from allowlist. "
            f"Missing: {sorted(expected - actual)}; extra: {sorted(actual - expected)}"
        )
    if city_lookup["zip_code"].duplicated().any():
        raise ValueError("Output contains duplicate ZIP codes.")
    if not city_lookup["zip_code"].str.fullmatch(r"\d{5}").all():
        raise ValueError("Output contains malformed ZIP codes.")


def main() -> None:
    allowed_zips = load_allowed_zips()
    city_lookup = build_city_lookup(allowed_zips)
    validate_output(city_lookup, allowed_zips)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    city_lookup.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(city_lookup)} ZIP rows to {OUTPUT_PATH}")
    print(f"Unique city labels: {city_lookup['city_name'].nunique()}")
    print(f"Unique counties: {city_lookup['county_name'].nunique()}")


if __name__ == "__main__":
    main()
