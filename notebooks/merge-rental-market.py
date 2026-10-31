"""Merge Miami ZORI and HUD rent benchmarks into one ZIP-level dataset."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
NEW_DATA_DIR = CLEANED_DIR / "new"
HUD_PATH = RAW_DIR / "HUD-SAFMR.csv"
ZORI_PATH = NEW_DATA_DIR / "Miami_rental_values.csv"
ZCTA_PATH = RAW_DIR / "miami_dade_zctas.txt"
OUTPUT_PATH = NEW_DATA_DIR / "Rental-Market.csv"

FINAL_COLUMNS = [
    "zip_code",
    "zori_2026_01",
    "zori_2026_02",
    "zori_2026_03",
    "zori_2026_04",
    "zori_2026_05",
    "zori_2026_06",
    "zori_2026_07",
    "zori_2026_08",
    "zori_latest_rent",
    "hud_efficiency",
    "hud_1_bedroom",
    "hud_2_bedroom",
    "hud_3_bedroom",
    "hud_4_bedroom",
    "zori_source",
    "hud_source",
]


def normalize_zip_codes(values: pd.Series, field_name: str) -> pd.Series:
    """Return five-character ZIP strings and reject missing or malformed values."""
    normalized = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    normalized = normalized.str.zfill(5)
    invalid = normalized.isna() | ~normalized.str.fullmatch(r"\d{5}", na=False)
    if invalid.any():
        examples = values[invalid].head(5).tolist()
        raise ValueError(f"{field_name} contains invalid ZIP codes: {examples}")
    return normalized


def load_allowlist() -> set[str]:
    allowed = {
        line.strip()
        for line in ZCTA_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if not allowed:
        raise ValueError(f"ZIP allowlist is empty: {ZCTA_PATH}")
    return allowed


def prepare_hud(allowed_zips: set[str]) -> pd.DataFrame:
    hud = pd.read_csv(HUD_PATH, dtype={"zip_code": "string"})
    hud["zip_code"] = normalize_zip_codes(hud["zip_code"], "HUD zip_code")
    if hud["zip_code"].duplicated().any():
        raise ValueError("HUD-SAFMR.csv contains duplicate ZIP codes.")
    hud = hud[hud["zip_code"].isin(allowed_zips)].copy()
    hud = hud.rename(
        columns={
            "efficiency": "hud_efficiency",
            "one_bedroom": "hud_1_bedroom",
            "two_bedroom": "hud_2_bedroom",
            "three_bedroom": "hud_3_bedroom",
            "four_bedroom": "hud_4_bedroom",
        }
    )
    hud["hud_source"] = "HUD Small Area Fair Market Rents"
    return hud[
        [
            "zip_code",
            "hud_efficiency",
            "hud_1_bedroom",
            "hud_2_bedroom",
            "hud_3_bedroom",
            "hud_4_bedroom",
            "hud_source",
        ]
    ]


def prepare_zori(allowed_zips: set[str]) -> pd.DataFrame:
    zori = pd.read_csv(ZORI_PATH, dtype={"RegionName": "string"})
    zori["zip_code"] = normalize_zip_codes(zori["RegionName"], "ZORI RegionName")
    if zori["zip_code"].duplicated().any():
        raise ValueError("Miami_rental_values.csv contains duplicate ZIP codes.")
    zori = zori[zori["zip_code"].isin(allowed_zips)].copy()

    source_date_columns = [
        column
        for column in zori.columns
        if pd.Series([column]).str.fullmatch(r"\d{4}-\d{2}-\d{2}").iloc[0]
    ]
    month_columns = {
        column: f"zori_{column[:7].replace('-', '_')}"
        for column in source_date_columns
    }
    required = list(month_columns)
    missing = [column for column in required if column not in zori.columns]
    if missing:
        raise ValueError(f"ZORI is missing required monthly columns: {missing}")

    zori = zori[["zip_code", *required]].rename(columns=month_columns)
    target_month_columns = list(month_columns.values())
    zori["zori_latest_rent"] = zori[target_month_columns[-1]]
    zori["zori_source"] = "Zillow ZORI"
    return zori


def validate_output(rental_market: pd.DataFrame, allowed_zips: set[str]) -> None:
    if rental_market.columns.tolist() != FINAL_COLUMNS:
        raise ValueError("Final rental-market columns do not match the required schema.")
    if rental_market["zip_code"].duplicated().any():
        raise ValueError("Final rental-market output contains duplicate ZIP codes.")
    invalid = set(rental_market["zip_code"]) - allowed_zips
    if invalid:
        raise ValueError(f"Final output contains ZIP codes outside the allowlist: {sorted(invalid)}")


def fill_missing_zori_values(
    rental_market: pd.DataFrame,
    zori: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Fill target ZORI fields from matching ZIP/date values in the source."""
    zori_columns = [column for column in FINAL_COLUMNS if column.startswith("zori_")]
    source = zori.set_index("zip_code")[zori_columns]
    result = rental_market.set_index("zip_code").copy()
    before = result[zori_columns].isna().sum()
    result[zori_columns] = result[zori_columns].combine_first(source)
    return result.reset_index(), before


def main() -> None:
    allowed_zips = load_allowlist()
    hud = prepare_hud(allowed_zips)
    zori = prepare_zori(allowed_zips)
    # Start with every allowed HUD ZIP, then fill matching ZORI fields by ZIP.
    # This preserves ZIPs that have HUD benchmarks but no Zillow estimate.
    rental_market = hud.copy()
    for column in [column for column in FINAL_COLUMNS if column.startswith("zori_")]:
        rental_market[column] = pd.NA
    rental_market = rental_market[FINAL_COLUMNS].sort_values("zip_code").reset_index(drop=True)
    rental_market, missing_before_fill = fill_missing_zori_values(rental_market, zori)
    validate_output(rental_market, allowed_zips)
    NEW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rental_market.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(rental_market)} ZIP rows and {len(rental_market.columns)} columns to {OUTPUT_PATH}")
    print(f"Valid ZORI ZIPs retained: {len(zori)}")
    print(f"Valid HUD ZIPs retained: {len(hud)}")
    print(f"ZORI missing before source merge:\n{missing_before_fill}")
    print(
        "ZORI values filled from Miami_rental_values.csv:\n"
        f"{missing_before_fill - rental_market[[column for column in FINAL_COLUMNS if column.startswith('zori_')]].isna().sum()}"
    )
    print(f"Missing-value counts:\n{rental_market.isna().sum()}")


if __name__ == "__main__":
    main()