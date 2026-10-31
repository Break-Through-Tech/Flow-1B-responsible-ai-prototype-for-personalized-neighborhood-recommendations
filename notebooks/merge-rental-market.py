"""Merge Miami ZORI and HUD rent benchmarks into one ZIP-level dataset."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
HUD_PATH = RAW_DIR / "HUD-SAFMR.csv"
ZORI_PATH = CLEANED_DIR / "Miami_rental_values.csv"
ZCTA_PATH = RAW_DIR / "miami_dade_zctas.txt"
OUTPUT_PATH = CLEANED_DIR / "Rental-Market.csv"

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

    month_columns = {
        f"2026-{month:02d}-31": f"zori_2026_{month:02d}"
        for month in [1, 3, 5, 7, 8]
    }
    month_columns.update(
        {"2026-02-28": "zori_2026_02", "2026-04-30": "zori_2026_04", "2026-06-30": "zori_2026_06"}
    )
    required = list(month_columns)
    missing = [column for column in required if column not in zori.columns]
    if missing:
        raise ValueError(f"ZORI is missing required monthly columns: {missing}")

    zori = zori[["zip_code", *required]].rename(columns=month_columns)
    zori["zori_latest_rent"] = zori["zori_2026_08"]
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


def main() -> None:
    allowed_zips = load_allowlist()
    hud = prepare_hud(allowed_zips)
    zori = prepare_zori(allowed_zips)
    # Keep ZIP codes present in either source so missing benchmarks remain visible.
    rental_market = zori.merge(hud, on="zip_code", how="outer", validate="one_to_one")
    rental_market = rental_market[FINAL_COLUMNS].sort_values("zip_code").reset_index(drop=True)
    validate_output(rental_market, allowed_zips)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    rental_market.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(rental_market)} ZIP rows and {len(rental_market.columns)} columns to {OUTPUT_PATH}")
    print(f"Valid ZORI ZIPs retained: {len(zori)}")
    print(f"Valid HUD ZIPs retained: {len(hud)}")
    print(f"Missing-value counts:\n{rental_market.isna().sum()}")


if __name__ == "__main__":
    main()