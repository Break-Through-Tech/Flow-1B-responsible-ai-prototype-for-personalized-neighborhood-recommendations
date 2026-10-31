"""Build Miami ZIP-level rent trend features from historical Zillow ZORI data."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
ZORI_PATH = RAW_DIR / "Zip_zori_uc_sfrcondomfr_sm_month.csv"
ZCTA_PATH = RAW_DIR / "miami_dade_zctas.txt"
HISTORY_OUTPUT_PATH = CLEANED_DIR / "zori_history.csv"
TRENDS_OUTPUT_PATH = CLEANED_DIR / "rent-trends.csv"

SOURCE_NAME = "Zillow ZORI"
DIRECTION_THRESHOLD_PCT = 1.0
TREND_COLUMNS = [
    "zip_code",
    "latest_rent_usd",
    "rent_3_month_change_pct",
    "rent_12_month_change_pct",
    "rent_24_month_change_pct",
    "rent_volatility",
    "rent_direction",
    "source",
    "source_date",
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
    """Load the Miami-Dade ZIP allowlist."""
    allowed = {
        line.strip()
        for line in ZCTA_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if not allowed:
        raise ValueError(f"ZIP allowlist is empty: {ZCTA_PATH}")
    return allowed


def load_zori_history(allowed_zips: set[str]) -> pd.DataFrame:
    """Filter the historical ZORI source and reshape it to one row per ZIP/month."""
    zori = pd.read_csv(ZORI_PATH, dtype={"RegionName": "string"})
    zori["zip_code"] = normalize_zip_codes(zori["RegionName"], "ZORI RegionName")
    zori = zori[zori["zip_code"].isin(allowed_zips)].copy()
    if zori["zip_code"].duplicated().any():
        raise ValueError("Historical ZORI contains duplicate ZIP codes.")

    month_columns = sorted(
        column
        for column in zori.columns
        if pd.notna(pd.to_datetime(column, format="%Y-%m-%d", errors="coerce"))
    )
    if not month_columns:
        raise ValueError("Historical ZORI does not contain monthly observation columns.")

    history = zori[["zip_code", *month_columns]].melt(
        id_vars="zip_code",
        var_name="observation_month",
        value_name="zori_rent_usd",
    )
    history["observation_month"] = pd.to_datetime(history["observation_month"]).dt.to_period("M")
    history["zori_rent_usd"] = pd.to_numeric(history["zori_rent_usd"], errors="coerce")
    history = history.dropna(subset=["zori_rent_usd"]).copy()
    history["source"] = SOURCE_NAME
    history["source_date"] = history["observation_month"].astype(str)
    history["observation_month"] = history["observation_month"].astype(str)
    history = history.sort_values(["zip_code", "observation_month"]).reset_index(drop=True)
    if history.duplicated(["zip_code", "observation_month"]).any():
        raise ValueError("ZORI history contains duplicate ZIP/month rows.")
    return history


def calculate_change(
    monthly_values: pd.DataFrame, latest_month: pd.Period, months_ago: int
) -> pd.Series:
    """Calculate percentage change only when both exact comparison months exist."""
    latest = monthly_values.get(latest_month)
    previous = monthly_values.get(latest_month - months_ago)
    if latest is None or previous is None:
        return pd.Series(index=monthly_values.index, dtype="float64")
    return ((latest - previous) / previous.where(previous.ne(0))) * 100


def build_trends(history: pd.DataFrame) -> pd.DataFrame:
    """Derive compact trend features from the long-format ZORI history."""
    history_with_period = history.assign(
        observation_period=pd.PeriodIndex(history["observation_month"], freq="M")
    )
    monthly_values = history_with_period.pivot(
        index="zip_code", columns="observation_period", values="zori_rent_usd"
    ).sort_index(axis=1)
    latest_month = monthly_values.columns.max()
    latest_values = monthly_values[latest_month]

    trends = pd.DataFrame(
        {
            "zip_code": monthly_values.index,
            "latest_rent_usd": latest_values,
            "rent_3_month_change_pct": calculate_change(monthly_values, latest_month, 3),
            "rent_12_month_change_pct": calculate_change(monthly_values, latest_month, 12),
            "rent_24_month_change_pct": calculate_change(monthly_values, latest_month, 24),
        }
    ).set_index("zip_code")

    monthly_change = monthly_values.pct_change(axis=1, fill_method=None) * 100
    recent_months = pd.period_range(end=latest_month, periods=12, freq="M")
    trends["rent_volatility"] = monthly_change.reindex(columns=recent_months).std(
        axis=1, skipna=False
    )
    trends["rent_direction"] = trends["rent_3_month_change_pct"].map(
        lambda value: (
            "increasing"
            if value > DIRECTION_THRESHOLD_PCT
            else "decreasing"
            if value < -DIRECTION_THRESHOLD_PCT
            else "stable"
        )
        if pd.notna(value)
        else pd.NA
    )
    trends["source"] = SOURCE_NAME
    trends["source_date"] = str(latest_month)
    return trends.reset_index()[TREND_COLUMNS]


def validate_outputs(
    history: pd.DataFrame, trends: pd.DataFrame, allowed_zips: set[str]
) -> None:
    """Validate output schemas and ZIP-level uniqueness."""
    expected_history = [
        "zip_code",
        "observation_month",
        "zori_rent_usd",
        "source",
        "source_date",
    ]
    if history.columns.tolist() != expected_history:
        raise ValueError("ZORI history columns do not match the required schema.")
    if trends.columns.tolist() != TREND_COLUMNS:
        raise ValueError("Rent-trends columns do not match the required schema.")
    if set(history["zip_code"]) - allowed_zips or set(trends["zip_code"]) - allowed_zips:
        raise ValueError("Output contains ZIP codes outside the Miami-Dade allowlist.")
    if trends["zip_code"].duplicated().any():
        raise ValueError("Rent-trends output contains duplicate ZIP codes.")


def main() -> None:
    allowed_zips = load_allowlist()
    history = load_zori_history(allowed_zips)
    trends = build_trends(history)
    validate_outputs(history, trends, allowed_zips)

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    history.to_csv(HISTORY_OUTPUT_PATH, index=False)
    trends.to_csv(TRENDS_OUTPUT_PATH, index=False)
    print(f"Saved {len(history)} ZORI history rows to {HISTORY_OUTPUT_PATH}")
    print(f"Saved {len(trends)} ZIP trend rows to {TRENDS_OUTPUT_PATH}")
    print(f"Latest observation month: {trends['source_date'].iloc[0]}")
    print(f"Missing trend values:\n{trends.isna().sum()}")


if __name__ == "__main__":
    main()