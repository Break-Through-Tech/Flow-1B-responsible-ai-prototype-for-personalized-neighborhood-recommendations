"""Merge rental data by ZIP, fill source labels, and zero missing ZORI/growth values."""

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "cleaned" / "new"
RENTAL_MARKET_PATH = DATA_DIR / "Rental-Market.csv"
RENT_TRENDS_PATH = DATA_DIR / "rent-trends.csv"
OUTPUT_PATH = DATA_DIR / "miami-rents.csv"
SOURCE_LABELS = {
    "zori_source": "Zillow ZORI",
    "hud_source": "HUD Small Area Fair Market Rents",
}


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
    zero_fill_columns = [
        column
        for column in columns
        if (column.startswith("zori_") and column != "zori_source")
        or (column.startswith("rent_") and column.endswith("_month_change_pct"))
    ]
    zip_codes = sorted(set(market_rows) | set(trend_rows))
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for zip_code in zip_codes:
            row = {**market_rows.get(zip_code, {}), **trend_rows.get(zip_code, {})}
            for column in zero_fill_columns:
                if not row.get(column, "").strip():
                    row[column] = "0"
            for column, label in SOURCE_LABELS.items():
                if not row.get(column, "").strip():
                    row[column] = label
            writer.writerow(row)

    matched = len(set(market_rows) & set(trend_rows))
    print(f"Saved {len(zip_codes)} ZIP rows and {len(columns)} columns to {OUTPUT_PATH}")
    print(f"ZIPs with data from both inputs: {matched}")
    print(f"ZIPs without trend data: {len(set(market_rows) - set(trend_rows))}")
    print(f"ZIPs without rental-market data: {len(set(trend_rows) - set(market_rows))}")


if __name__ == "__main__":
    main()
