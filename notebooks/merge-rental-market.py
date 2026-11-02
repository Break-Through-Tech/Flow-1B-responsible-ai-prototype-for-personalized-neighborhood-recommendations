"""Merge rental data by ZIP and apply the canonical Miami rent cleaning rules."""

import csv
from pathlib import Path

import pandas as pd

from clean_miami_rents import clean_miami_rents


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "cleaned" / "new"
RENTAL_MARKET_PATH = DATA_DIR / "Rental-Market.csv"
RENT_TRENDS_PATH = DATA_DIR / "rent-trends.csv"
OUTPUT_PATH = DATA_DIR / "miami-rents.csv"


def load_by_zip(file_path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Read CSV values unchanged, normalizing and validating unique ZIP keys."""
    with file_path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        if not columns or "zip_code" not in columns:
            raise ValueError(f"{file_path.name} is missing the zip_code column.")

        rows_by_zip = {}
        for row in reader:
            zip_code = (row["zip_code"] or "").strip()
            if not zip_code.isascii() or not zip_code.isdigit() or len(zip_code) > 5:
                raise ValueError(f"{file_path.name} contains an invalid ZIP: {zip_code!r}")
            zip_code = zip_code.zfill(5)
            if zip_code in rows_by_zip:
                raise ValueError(f"{file_path.name} contains duplicate ZIP: {zip_code}")
            row["zip_code"] = zip_code
            rows_by_zip[zip_code] = row

    return columns, rows_by_zip


def main() -> None:
    market_columns, market_rows = load_by_zip(RENTAL_MARKET_PATH)
    trend_columns, trend_rows = load_by_zip(RENT_TRENDS_PATH)
    overlapping = (set(market_columns) & set(trend_columns)) - {"zip_code"}
    if overlapping:
        raise ValueError(f"Inputs share non-key columns: {sorted(overlapping)}")

    columns = market_columns + [column for column in trend_columns if column != "zip_code"]
    zip_codes = sorted(set(market_rows) | set(trend_rows))
    rows = [
        {**market_rows.get(zip_code, {}), **trend_rows.get(zip_code, {})}
        for zip_code in zip_codes
    ]
    rental_market = pd.DataFrame(rows, columns=columns).replace("", pd.NA)
    rental_market = clean_miami_rents(rental_market)
    rental_market.to_csv(OUTPUT_PATH, index=False, na_rep="", lineterminator="\n")

    matched = len(set(market_rows) & set(trend_rows))
    print(
        f"Saved {len(zip_codes)} ZIP rows and {len(rental_market.columns)} columns to {OUTPUT_PATH}"
    )
    print(f"ZIPs with data from both inputs: {matched}")
    print(f"ZIPs without trend data: {len(set(market_rows) - set(trend_rows))}")
    print(f"ZIPs without rental-market data: {len(set(trend_rows) - set(market_rows))}")


if __name__ == "__main__":
    main()
