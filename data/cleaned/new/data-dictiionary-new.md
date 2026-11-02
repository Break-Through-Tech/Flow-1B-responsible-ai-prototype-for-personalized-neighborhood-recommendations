# Cleaned New Data Dictionary

This document describes the cleaned rent feature table under
`data/cleaned/new/`. Raw source schemas, including transit and geography
inputs, are documented in
[`raw-new-data-dictionary.md`](../../raw/new/raw-new-data-dictionary.md).

## Miami-rents-cleaned.csv

This model-ready export combines the latest ZORI rent, HUD benchmarks, and
derived rent-trend features. ZIP codes are five-character strings.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit Miami-Dade ZIP/ZCTA join key |
| `zori_latest_rent` | numeric | August 2026 ZORI rent estimate used as the latest-rent feature |
| `hud_efficiency` | numeric | HUD monthly benchmark for an efficiency/studio |
| `hud_1_bedroom` | numeric | HUD monthly benchmark for a one-bedroom |
| `hud_2_bedroom` | numeric | HUD monthly benchmark for a two-bedroom |
| `hud_3_bedroom` | numeric | HUD monthly benchmark for a three-bedroom |
| `hud_4_bedroom` | numeric | HUD monthly benchmark for a four-bedroom |
| `rent_3_month_change_pct` | numeric | Percentage rent change over the latest three-month window |
| `rent_12_month_change_pct` | numeric | Percentage rent change over the latest twelve-month window |
| `rent_24_month_change_pct` | numeric | Percentage rent change over the latest twenty-four-month window |
| `rent_volatility` | numeric | Rent variability measure calculated by the source pipeline |
| `rent_direction` | categorical | `increasing`, `decreasing`, or `stable` trend label |

### Rent cleaning rules

- ZIP codes are normalized and duplicate ZIP rows are rejected.
- Zero placeholders in rent and percentage-change fields are treated as
  missing; negative observed Zillow rents are rejected.
- `zori_latest_rent` comes from August 2026 ZORI.
- Median imputation is applied to `zori_latest_rent`, the three percentage
  change fields, and `rent_volatility`. For evaluation, medians should be fit
  on training data only.
- Missing trend labels are derived from the three-month change: above 1% is
  `increasing`, below -1% is `decreasing`, and values between them are
  `stable`.
- Outliers are retained; they are not winsorized or removed.

## Intended use and limitations

This table is intended for ZIP-level descriptive analysis, model features,
explanations, and trend visualization. A ZIP-level statistic does not describe
every property or resident. Values are snapshots rather than live market data,
and must not be used for protected-class inference, demographic steering,
eligibility decisions, or denying housing access.
