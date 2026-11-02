"""Clean Miami rents and define separate model, metadata, and explanation fields."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RENT_PATH = PROJECT_ROOT / "data" / "cleaned" / "new" / "miami-rents.csv"
CLEANED_RENT_PATH = RENT_PATH.with_name("Miami-rents-cleaned.csv")
ZORI_MONTH_COLUMNS = [f"zori_2026_{month:02d}" for month in range(1, 9)]
ZORI_RENT_COLUMNS = [*ZORI_MONTH_COLUMNS, "zori_latest_rent"]
EXCLUDED_MONTH_COLUMNS = ZORI_MONTH_COLUMNS
DROP_COLUMNS = [
    *ZORI_MONTH_COLUMNS, "zori_source", "hud_source", "source", "zori_source_date", "source_date",
]
MEDIAN_IMPUTE_COLUMNS = [
    "zori_latest_rent", "rent_3_month_change_pct", "rent_12_month_change_pct",
    "rent_24_month_change_pct", "rent_volatility",
]
METADATA_COLUMNS = [
    "zip_code", "zori_source", "hud_source", "source", "source_date", "zori_source_date",
]
EXPLANATION_COLUMNS = ["rent_direction"]
MODEL_FEATURE_COLUMNS = [
    "zori_latest_rent",
    "hud_efficiency", "hud_1_bedroom", "hud_2_bedroom", "hud_3_bedroom", "hud_4_bedroom",
    "rent_3_month_change_pct", "rent_12_month_change_pct", "rent_24_month_change_pct",
    "rent_volatility",
]


def clean_miami_rents(frame: pd.DataFrame) -> pd.DataFrame:
    """Restore missing rents and reconcile only verified August Zillow estimates.

    Zero-filled monthly percentage changes are restored to missing values.
    HUD benchmarks never supply values for the Zillow fields.
    """
    result = frame.copy()
    required = ["zip_code", *ZORI_RENT_COLUMNS, "source", "source_date"]
    missing = set(required) - set(result.columns)
    if missing:
        raise ValueError(f"Missing required rent columns: {sorted(missing)}")

    result["zip_code"] = result["zip_code"].astype("string").str.strip().str.zfill(5)
    if not result["zip_code"].str.fullmatch(r"[0-9]{5}", na=False).all():
        raise ValueError("ZIP codes must be five-character strings.")
    if result["zip_code"].duplicated().any():
        raise ValueError("Miami rents contains duplicate ZIP codes.")

    result[ZORI_RENT_COLUMNS] = result[ZORI_RENT_COLUMNS].apply(
        pd.to_numeric, errors="raise"
    ).replace(0, np.nan)
    if result[ZORI_RENT_COLUMNS].lt(0).any().any():
        raise ValueError("Observed Zillow rent values must be positive.")

    change_columns = [
        column for column in result.columns
        if column.startswith("rent_") and column.endswith("_month_change_pct")
    ]
    result[change_columns] = result[change_columns].apply(
        pd.to_numeric, errors="raise"
    ).replace(0, np.nan)

    if "latest_rent_usd" in result:
        trend_rent = pd.to_numeric(result["latest_rent_usd"], errors="raise").replace(0, np.nan)
        if trend_rent.lt(0).any():
            raise ValueError("Observed trend rent values must be positive.")
        verified_august = (
            result["source"].eq("Zillow ZORI") & result["source_date"].eq("2026-08")
        ).fillna(False)
        needs_fallback = result["zori_2026_08"].isna() & trend_rent.notna()
        if (needs_fallback & ~verified_august).any():
            raise ValueError("Fallback rents must be verified Zillow ZORI values for 2026-08.")
        overlap = result["zori_2026_08"].notna() & trend_rent.notna() & verified_august
        if not np.isclose(
            result.loc[overlap, "zori_2026_08"], trend_rent.loc[overlap], rtol=0, atol=0.01
        ).all():
            raise ValueError("August monthly and trend rents disagree by more than $0.01.")
        result["zori_2026_08"] = result["zori_2026_08"].combine_first(
            trend_rent.where(verified_august)
        )
        result = result.drop(columns="latest_rent_usd")

    result["zori_latest_rent"] = result["zori_2026_08"]
    observed = result["zori_latest_rent"].notna()
    result["zori_source"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["zori_source_date"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result.loc[observed, "zori_source"] = "Zillow ZORI"
    result.loc[observed, "zori_source_date"] = "2026-08"
    return result


def prepare_rent_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Restore numeric zero placeholders, then remove the requested export columns."""
    result = clean_miami_rents(frame)
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].replace(0, np.nan)
    return result.drop(columns=DROP_COLUMNS)


def fit_rent_imputer(training_rows: pd.DataFrame) -> SimpleImputer:
    """Fit the five field medians on training rows only for evaluation/model training."""
    values = training_rows[MEDIAN_IMPUTE_COLUMNS]
    empty_columns = values.columns[values.isna().all()].tolist()
    if empty_columns:
        raise ValueError(f"Cannot fit medians without observations: {empty_columns}")
    return SimpleImputer(strategy="median").fit(values)


def impute_rent_table(frame: pd.DataFrame, imputer: SimpleImputer) -> pd.DataFrame:
    """Apply already fitted medians, preserving observed values and all outliers."""
    result = frame.copy()
    result[MEDIAN_IMPUTE_COLUMNS] = imputer.transform(result[MEDIAN_IMPUTE_COLUMNS])
    return result


def fill_missing_rent_direction(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill missing explanation labels from the existing three-month change.

    Call after median imputation for the complete export. An unavailable change
    still produces a missing direction; existing labels are preserved.
    """
    result = frame.copy()
    change = pd.to_numeric(result["rent_3_month_change_pct"], errors="raise")
    direction = pd.Series(pd.NA, index=result.index, dtype="string")
    direction.loc[change.notna()] = "stable"
    direction.loc[change.gt(1).fillna(False)] = "increasing"
    direction.loc[change.lt(-1).fillna(False)] = "decreasing"
    existing = result["rent_direction"].astype("string")
    existing = existing.mask(existing.str.strip().eq(""), pd.NA)
    result["rent_direction"] = existing.fillna(direction)
    return result


def main() -> None:
    frame = pd.read_csv(RENT_PATH, dtype={"zip_code": "string"}, float_precision="round_trip")
    prepared = prepare_rent_table(frame)
    # This full-dataset export is a descriptive snapshot. For held-out evaluation,
    # fit a fresh imputer on the training split and reuse it on validation/test rows.
    imputer = fit_rent_imputer(prepared)
    cleaned = impute_rent_table(prepared, imputer)
    cleaned = fill_missing_rent_direction(cleaned)
    missing = cleaned.isna().sum()
    if missing.any():
        missing_counts = missing[missing.gt(0)].to_dict()
        raise ValueError(f"Cleaned export still has missing values: {missing_counts}")
    cleaned.to_csv(CLEANED_RENT_PATH, index=False, na_rep="", lineterminator="\n")
    print(f"Saved {len(cleaned)} ZIPs and {len(cleaned.columns)} columns to {CLEANED_RENT_PATH}")
    for column, median in zip(MEDIAN_IMPUTE_COLUMNS, imputer.statistics_):
        print(f"{column}: filled {prepared[column].isna().sum()} values with median {median}")
    print(f"Direction labels filled: {prepared['rent_direction'].isna().sum()}")
    print(f"Total missing values: {cleaned.isna().sum().sum()}")
    print("Outlier values retained; treatment is pending.")


if __name__ == "__main__":
    main()
