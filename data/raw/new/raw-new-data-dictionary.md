# Raw New Data Dictionary

This document describes the source files stored in `data/raw/new/`. These are
ZIP-level public or provider extracts used to build the project's cleaned
features. They are not individual-level records or real-time listings.

All ZIP codes should be normalized as five-character strings. Provider files
use `RegionName` for the ZIP field. The project geography is defined by
`data/raw/miami_dade_zctas.txt`.

## HUD-SAFMR.csv

HUD Small Area Fair Market Rent reference benchmarks. These are not observed
asking rents or guaranteed prices.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit ZIP/ZCTA identifier |
| `efficiency` | numeric | Monthly HUD benchmark for an efficiency/studio |
| `one_bedroom` | numeric | Monthly HUD benchmark for a one-bedroom |
| `two_bedroom` | numeric | Monthly HUD benchmark for a two-bedroom |
| `three_bedroom` | numeric | Monthly HUD benchmark for a three-bedroom |
| `four_bedroom` | numeric | Monthly HUD benchmark for a four-bedroom |

## Miami_home_values.csv and Miami_rental_values.csv

Wide ZIP-level monthly extracts containing provider geography metadata and
January-August 2026 measurements.

| Column | Type | Description |
|--------|------|-------------|
| `RegionID` | integer | Provider geographic identifier |
| `SizeRank` | integer | Provider region ranking |
| `RegionName` | string/integer | ZIP/ZCTA identifier |
| `RegionType` | string | Provider region type |
| `StateName` | string | Full state name |
| `State` | string | State abbreviation |
| `City` | string | Provider city label |
| `Metro` | string | Provider metropolitan-area label |
| `CountyName` | string | Provider county label |
| `YYYY-MM-DD` | numeric | Monthly measurement for the date in the column name |

The monthly values in `Miami_home_values.csv` are home-value estimates. The
monthly values in `Miami_rental_values.csv` are rental-value estimates.

## Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv

Wide ZIP-level Zillow Home Value Index history. It contains the same provider
metadata as the files above, followed by monthly home-value estimates from
January 2000 through August 2026.

## Zip_zori_uc_sfrcondomfr_sm_month.csv

Wide ZIP-level Zillow Observed Rent Index history. It contains the same
provider metadata followed by monthly observed-rent estimates from January
2015 through August 2026.

For both history files, date-formatted column names are measurement periods.
Reshape them to long format for trend analysis.

## zori_history.csv

Normalized ZORI history with one row per ZIP and observation month.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit ZIP/ZCTA identifier |
| `observation_month` | date/string | Month represented by the observation |
| `zori_rent_usd` | numeric | ZORI observed-rent estimate in USD per month |
| `source` | string | Source label for the observation |
| `source_date` | string/date | Source release or observation date |

## miami_transit.csv

ZIP-level transit features built from Miami-Dade GTFS files. Stops are assigned
to ZIPs by spatially joining stop coordinates to Census ZCTA boundaries.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit ZIP/ZCTA identifier |
| `transit_stop_count` | integer | Number of transit stops in the ZIP |
| `unique_route_count` | integer | Number of distinct routes serving the ZIP |
| `transit_types` | string | Comma-separated transit modes represented |
| `bus_route_count` | integer | Number of bus routes |
| `metrorail_route_count` | integer | Number of Metrorail routes |
| `metromover_route_count` | integer | Number of Metromover routes |
| `weekday_departures` | integer | Scheduled weekday departure events |
| `saturday_departures` | integer | Scheduled Saturday departure events |
| `sunday_departures` | integer | Scheduled Sunday departure events |
| `weekday_median_headway_minutes` | numeric | Median weekday gap between departures |
| `weekend_median_headway_minutes` | numeric | Median weekend gap between departures |
| `morning_peak_departures` | integer | Scheduled morning-peak departures |
| `evening_peak_departures` | integer | Scheduled evening-peak departures |
| `accessible_stop_share` | numeric | Share of known stops marked wheelchair accessible |
| `wheelchair_accessible_trip_share` | numeric | Share of known trips marked wheelchair accessible |
| `bike_allowed_trip_share` | numeric | Share of known trips marked bike allowed |
| `gtfs_agency` | string | Transit agency represented in the feed |
| `service_start_date` | date/string | Start date of the GTFS service calendar |
| `service_end_date` | date/string | End date of the GTFS service calendar |
| `data_as_of` | date/string | Date the transit feature table was produced |

Unknown accessibility values are excluded from share denominators. Headways
are calculated within each ZIP, stop, and route before ZIP-level medians are
taken.

## city-name.csv

ZIP geography and display-name lookup used to interpret model results.

| Column | Type | Description |
|--------|------|-------------|
| `zip_code` | string | Five-digit ZIP/ZCTA identifier |
| `city_name` | string | City associated with the ZIP |
| `area_name` | string | Human-readable area or neighborhood label |
| `area_name_type` | string | Type or origin of the area label |
| `county_name` | string | County name |
| `state_code` | string | Two-letter state abbreviation |
| `latitude` | numeric | Representative latitude |
| `longitude` | numeric | Representative longitude |
| `source` | string | Source of the geography record |

## Source-data limitations

- Values are historical snapshots, not live market data.
- Zillow-style indices and HUD benchmarks have different definitions.
- ZIP-level estimates describe areas and do not represent every property.
- Source dates and provenance should be retained when features are used.
