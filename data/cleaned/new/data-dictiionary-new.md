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

## Miami-transit-cleaned.csv

This model-ready export contains ZIP-level Miami-Dade transit service
features. `zip_code` is retained as the label and join key. Transit mode
values were expanded into one-hot indicator columns. Service dates, agency,
source date, transit type text, and `accessible_stop_share` were removed.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit Miami-Dade ZIP/ZCTA label and join key |
| `transit_stop_count` | integer | Number of transit stops in the ZIP |
| `unique_route_count` | integer | Number of distinct routes serving the ZIP |
| `bus_route_count` | integer | Number of bus routes serving the ZIP |
| `metrorail_route_count` | integer | Number of Metrorail routes serving the ZIP |
| `metromover_route_count` | integer | Number of Metromover routes serving the ZIP |
| `weekday_departures` | integer | Scheduled weekday departure events |
| `saturday_departures` | integer | Scheduled Saturday departure events |
| `sunday_departures` | integer | Scheduled Sunday departure events |
| `weekday_median_headway_minutes` | numeric | Median scheduled gap between weekday departures |
| `weekend_median_headway_minutes` | numeric | Median scheduled gap between weekend departures |
| `morning_peak_departures` | integer | Scheduled departures during the morning peak |
| `evening_peak_departures` | integer | Scheduled departures during the evening peak |
| `wheelchair_accessible_trip_share` | numeric | Share of known trips marked wheelchair accessible |
| `bike_allowed_trip_share` | numeric | Share of known trips marked bike allowed |
| `transit_type_bus` | integer | One-hot indicator that bus service is represented in the ZIP |
| `transit_type_metromover` | integer | One-hot indicator that Metromover service is represented in the ZIP |
| `transit_type_metrorail` | integer | One-hot indicator that Metrorail service is represented in the ZIP |

### Transit cleaning rules

- `zip_code` is preserved as a five-character string label and join key.
- The multi-label `transit_types` field was one-hot encoded using the `|`
  separator.
- Valid zero values were preserved; for example, zero Metrorail routes can
  indicate that a ZIP is not served by Metrorail.
- Headway outliers were retained because unusually long scheduled gaps can be
  important to newcomer-facing transit explanations.

## Intended use and limitations

This table is intended for ZIP-level descriptive analysis, model features,
explanations, and trend visualization. A ZIP-level statistic does not describe
every property or resident. Values are snapshots rather than live market data,
and must not be used for protected-class inference, demographic steering,
eligibility decisions, or denying housing access.
