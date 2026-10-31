# Miami-Dade Google Transit (GTFS) Data Dictionary

## Purpose

This document explains the seven Miami-Dade GTFS text files in
simplified terms so they can be evaluated for a ZIP-code-based
neighborhood recommendation system.

> **ZIP finding:** None of the seven uploaded GTFS files contains a
> ZIP-code column. `stops.txt` does contain `stop_lat` and `stop_lon`,
> so each stop can be spatially mapped to a ZIP/ZCTA. The dataset
> therefore **needs ZIP enrichment**.

------------------------------------------------------------------------

## 1. `stops.txt`

### Purpose

Answers: **Where can a passenger get on or off transit?**

Each row represents a transit stop, station, or related transit
location. This is the most important geographic file because it contains
coordinates.

  ------------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- -----------------------
  `stop_id`               Unique ID for a transit Connects to
                          stop.                   `stop_times.txt`.

  `stop_code`             Public-facing stop      Stop identification.
                          code.                   

  `stop_name`             Name of the stop or     Explain nearby transit
                          station.                to users.

  `stop_desc`             Additional              Extra location context.
                          stop/location           
                          description.            

  `stop_lat`              Latitude of the stop.   **Very important:**
                                                  derive ZIP/ZCTA.

  `stop_lon`              Longitude of the stop.  **Very important:**
                                                  derive ZIP/ZCTA.

  `zone_id`               Fare zone, when         Potential fare
                          supplied.               analysis.

  `stop_url`              Stop webpage, when      Rider information.
                          supplied.               

  `location_type`         Type of transit         Distinguish kinds of
                          location.               transit locations.

  `parent_station`        Larger station          Group related
                          containing the          stops/platforms.
                          stop/platform.          

  `stop_timezone`         Stop-specific timezone, Scheduling support.
                          when supplied.          

  `wheelchair_boarding`   Wheelchair boarding     Accessibility feature.
                          information.            
  -----------------------------------------------------------------------

**ZIP status:** No native ZIP; coordinates allow ZIP/ZCTA enrichment.

------------------------------------------------------------------------

## 2. `routes.txt`

### Purpose

Answers: **What transit routes or services exist?**

  ------------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- ------------------------
  `route_id`              Unique internal route   Connects to `trips.txt`.
                          ID.                     

  `agency_id`             Agency operating the    Distinguish operators.
                          route.                  

  `route_short_name`      Short public route      Show routes serving a
                          name/number.            neighborhood.

  `route_long_name`       Full route              Explain route
                          name/description.       coverage/destinations.

  `route_desc`            Additional route        Extra context.
                          description.            

  `route_type`            Code describing the     **Very useful:**
                          transit mode/type.      distinguish service
                                                  types.

  `route_url`             Route webpage.          Rider information.

  `route_color`           Display color for       Map/UI visualization.
                          route.                  

  `route_text_color`      Text color used with    Map/UI visualization.
                          route.                  
  ------------------------------------------------------------------------

Possible derived features: `unique_route_count`, `bus_route_count`,
`rail_route_count`, `metromover_access`.

------------------------------------------------------------------------

## 3. `trips.txt`

### Purpose

Answers: **What individual journeys are scheduled on each route?**

A route is the overall service; a trip is one particular scheduled run.

  -------------------------------------------------------------------------
  Feature                   Simplified description  Potential project use
  ------------------------- ----------------------- -----------------------
  `route_id`                Route this trip belongs Connects to
                            to.                     `routes.txt`.

  `service_id`              Service schedule used   Connects to calendar
                            by the trip.            files.

  `trip_id`                 Unique ID for one       Connects to
                            scheduled journey.      `stop_times.txt`.

  `trip_headsign`           Destination/direction   Understand destinations
                            displayed for the trip. reachable from an area.

  `trip_short_name`         Public trip             Additional
                            name/number, when       identification.
                            supplied.               

  `direction_id`            Direction of travel.    Separate opposite route
                                                    directions.

  `block_id`                Groups consecutive      Operations; low
                            trips operated as a     priority.
                            vehicle block.          

  `shape_id`                Geographic path used by Connects to
                            the trip.               `shapes.txt`.

  `wheelchair_accessible`   Wheelchair              Accessibility analysis.
                            accessibility           
                            information.            

  `bikes_allowed`           Bicycle allowance       Bike/transit lifestyle
                            information.            analysis.
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 4. `stop_times.txt`

### Purpose

Answers: **When does each trip arrive at and depart from each stop?**

This is critical for measuring service frequency rather than merely
counting stops.

  -------------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- -------------------------
  `trip_id`               Trip associated with    Connects to `trips.txt`.
                          this record.            

  `arrival_time`          Scheduled arrival time. **Very useful:**
                                                  frequency/service-hour
                                                  analysis.

  `departure_time`        Scheduled departure     **Very useful:**
                          time.                   frequency analysis.

  `stop_id`               Stop visited by the     Connects to `stops.txt`.
                          trip.                   

  `stop_sequence`         Order in which stops    Reconstruct journey
                          are visited.            order.

  `stop_headsign`         Destination/headsign    Direction information.
                          from this stop.         

  `pickup_type`           Pickup/boarding rule.   Identify boarding
                                                  restrictions.

  `drop_off_type`         Drop-off rule.          Identify exiting
                                                  restrictions.

  `shape_dist_traveled`   Distance traveled along Route-position/distance
                          the route shape.        analysis.

  `timepoint`             Scheduling/timepoint    Schedule-quality context.
                          information.            
  -------------------------------------------------------------------------

Possible derived features: `weekday_departures`,
`morning_peak_departures`, `evening_peak_departures`,
`weekend_departures`, `median_headway_minutes`, `service_start_time`,
`service_end_time`.

------------------------------------------------------------------------

## 5. `calendar.txt`

### Purpose

Answers: **Which days of the week does a service operate, and during
what date range?**

  -----------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- -----------------------
  `service_id`            Unique service schedule Connects to
                          ID.                     `trips.txt`.

  `monday`                Whether service runs    Weekday analysis.
                          Monday.                 

  `tuesday`               Whether service runs    Weekday analysis.
                          Tuesday.                

  `wednesday`             Whether service runs    Weekday analysis.
                          Wednesday.              

  `thursday`              Whether service runs    Weekday analysis.
                          Thursday.               

  `friday`                Whether service runs    Weekday analysis.
                          Friday.                 

  `saturday`              Whether service runs    **Weekend
                          Saturday.               accessibility.**

  `sunday`                Whether service runs    **Weekend
                          Sunday.                 accessibility.**

  `start_date`            First date this         Determine schedule
                          schedule applies.       validity.

  `end_date`              Last date this schedule Determine schedule
                          applies.                validity.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 6. `calendar_dates.txt`

### Purpose

Answers: **Are there special dates when the normal schedule changes?**

  -----------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- -----------------------
  `service_id`            Service schedule        Connect exception to
                          affected.               service/trips.

  `date`                  Specific exception      Identify special
                          date.                   service dates.

  `exception_type`        Type of schedule        Account for
                          exception.              added/removed
                                                  special-date service.
  -----------------------------------------------------------------------

This is useful for exact date-based calculations, but lower priority for
a general neighborhood score.

------------------------------------------------------------------------

## 7. `shapes.txt`

### Purpose

Answers: **What geographic path does a transit trip follow?**

The file contains ordered latitude/longitude points that form route
lines on a map.

  -----------------------------------------------------------------------
  Feature                 Simplified description  Potential project use
  ----------------------- ----------------------- -----------------------
  `shape_id`              Unique geographic path  Connects to
                          ID.                     `trips.txt`.

  `shape_pt_lat`          Latitude of a point     Geographic route
                          along the route.        analysis.

  `shape_pt_lon`          Longitude of a point    Geographic route
                          along the route.        analysis.

  `shape_pt_sequence`     Order of route points.  Reconstruct route
                                                  geometry.

  `shape_dist_traveled`   Distance along the      Route-distance
                          route at the point.     calculations.
  -----------------------------------------------------------------------

Possible derived features: routes passing through a ZIP, route miles
within a ZIP, and geographic transit coverage.

------------------------------------------------------------------------

# How the Files Connect

``` text
routes.txt
    |
 route_id
    v
trips.txt --------------------> shapes.txt
    |                              ^
    | shape_id --------------------|
    |
    +-- service_id --> calendar.txt
    |                 calendar_dates.txt
    |
    +-- trip_id --> stop_times.txt
                       |
                    stop_id
                       |
                       v
                   stops.txt
                       |
                 lat + longitude
                       |
                       v
                   ZIP / ZCTA
```

## Main join keys

  From               Key            To
  ------------------ -------------- ----------------------
  `routes.txt`       `route_id`     `trips.txt`
  `trips.txt`        `trip_id`      `stop_times.txt`
  `stop_times.txt`   `stop_id`      `stops.txt`
  `trips.txt`        `service_id`   `calendar.txt`
  `trips.txt`        `service_id`   `calendar_dates.txt`
  `trips.txt`        `shape_id`     `shapes.txt`

------------------------------------------------------------------------

# ZIP-Code Assessment

  Requirement                    Result
  ------------------------------ -------------
  Native ZIP column              **No**
  Latitude/longitude available   **Yes**
  Best geographic source         `stops.txt`
  Can map stops to ZIP/ZCTA      **Yes**
  Dataset usable for project     **Yes**
  Enrichment required            **Yes**

Recommended pipeline:

``` text
Miami-Dade GTFS
       ↓
stops.txt
       ↓
stop_lat + stop_lon
       ↓
Census ZCTA boundaries
       ↓
Assign ZIP/ZCTA
       ↓
Join routes + trips + schedules
       ↓
Aggregate by ZIP
       ↓
MCP transit feature table
```

------------------------------------------------------------------------

# Raw GTFS Features vs. Neighborhood Features

GTFS supplies raw operational data such as:

``` text
stop_lat
stop_lon
route_id
route_type
trip_id
arrival_time
departure_time
service_id
saturday
sunday
```

For the MCP, these can later be transformed into neighborhood-level
features such as:

  -----------------------------------------------------------------------
  Derived feature                     Meaning
  ----------------------------------- -----------------------------------
  `zip_code`                          Neighborhood geographic key.

  `transit_stop_count`                Number of transit stops in the ZIP.

  `unique_route_count`                Number of distinct routes serving
                                      the ZIP.

  `bus_route_count`                   Number of bus routes serving the
                                      ZIP.

  `rail_station_count`                Number of rail stations in the ZIP.

  `metromover_access`                 Whether Metromover service is
                                      accessible.

  `weekday_departures`                Scheduled weekday departures.

  `morning_peak_departures`           Departures during morning commuting
                                      hours.

  `evening_peak_departures`           Departures during evening commuting
                                      hours.

  `saturday_departures`               Saturday service availability.

  `sunday_departures`                 Sunday service availability.

  `median_headway_minutes`            Typical scheduled time between
                                      vehicles.

  `wheelchair_accessible_ratio`       Accessibility-related service
                                      measure.

  `bike_allowed_ratio`                Bike allowance-related service
                                      measure.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# Summary

  -----------------------------------------------------------------------
  File                    Main question answered  Relative importance
  ----------------------- ----------------------- -----------------------
  `stops.txt`             Where are the transit   ⭐⭐⭐⭐⭐
                          stops?                  

  `routes.txt`            What transit routes     ⭐⭐⭐⭐⭐
                          exist?                  

  `trips.txt`             What individual         ⭐⭐⭐⭐⭐
                          journeys operate?       

  `stop_times.txt`        When does transit       ⭐⭐⭐⭐⭐
                          arrive/depart?          

  `calendar.txt`          What days does transit  ⭐⭐⭐⭐
                          operate?                

  `calendar_dates.txt`    What special schedule   ⭐⭐
                          exceptions exist?       

  `shapes.txt`            Where does the route    ⭐⭐⭐
                          physically travel?      
  -----------------------------------------------------------------------

## Final ZIP-level feature definitions

The final builder joins the GTFS tables through `stop_id`, `trip_id`,
`route_id`, and `service_id`, spatially assigns each stop to a Census
ZCTA, filters to the ZIP codes in `miami_dade_zctas.txt`, and produces
one row per ZIP.

| Column | Type | Description |
|---|---|---|
| `zip_code` | string | Miami-Dade project ZIP/ZCTA assigned from stop coordinates. |
| `transit_stop_count` | int | Number of distinct GTFS stops in the ZIP. |
| `unique_route_count` | int | Number of distinct routes serving the ZIP. |
| `transit_types` | string | Sorted pipe-separated modes, such as `bus|metrorail`. |
| `bus_route_count` | int | Distinct routes with GTFS `route_type = 3`. |
| `metrorail_route_count` | int | Distinct routes with GTFS `route_type = 2`. |
| `metromover_route_count` | int | Distinct routes with GTFS `route_type = 0`, interpreted as Metromover for this feed. |
| `weekday_departures` | int | Distinct scheduled stop departures attached to a Monday-Friday service. |
| `saturday_departures` | int | Distinct scheduled stop departures attached to a Saturday service. |
| `sunday_departures` | int | Distinct scheduled stop departures attached to a Sunday service. |
| `weekday_median_headway_minutes` | float | ZIP median of stop-route median gaps between consecutive weekday departures. |
| `weekend_median_headway_minutes` | float | ZIP median of stop-route median gaps between consecutive Saturday or Sunday departures. |
| `morning_peak_departures` | int | Weekday scheduled departures from 07:00 through 08:59. |
| `evening_peak_departures` | int | Weekday scheduled departures from 16:00 through 18:59. |
| `accessible_stop_share` | float | Share of stops marked wheelchair accessible among stops with known stop accessibility. |
| `wheelchair_accessible_trip_share` | float | Share of trips marked wheelchair accessible among trips with known vehicle accessibility. |
| `bike_allowed_trip_share` | float | Share of trips marked as allowing bicycles among trips with known bike status. |
| `gtfs_agency` | string | Source agency label: Miami-Dade Transit. |
| `service_start_date` | string | Earliest `start_date` in `calendar.txt`. |
| `service_end_date` | string | Latest `end_date` in `calendar.txt`. |
| `data_as_of` | date | Date on which the builder generated the output. |

### Derived-feature formulas and processing

- Departure counts deduplicate `zip_code`, `stop_id`, `trip_id`, and
  `departure_time` before counting.
- Weekday, Saturday, and Sunday categories come from the corresponding
  flags in `calendar.txt` through each trip's `service_id`.
- Headways are calculated separately within each ZIP, stop, and route. GTFS
  times are converted with `hour * 60 + minute + seconds / 60`, preserving
  valid times beyond `24:00:00`. Positive consecutive gaps are summarized
  first per stop-route pair and then by ZIP.
- GTFS accessibility and bike values of `0` or missing are unknown and are
  excluded from the relevant share denominator; `1` means yes and `2` means
  no for these fields.

### Source-data observations

- Almost every current `wheelchair_boarding` value is `2` and only one stop
  has value `1`; therefore `accessible_stop_share` is generally `0.0` and
  has limited source coverage.
- `wheelchair_accessible` and `bikes_allowed` are identical for every
  current trip record. Their output shares are therefore identical in this
  snapshot, although the builder calculates them from separate source
  columns.




-- a/dev/null


------------------------------------------------------------------------

# Current unified housing and transit dictionary

# Miami Housing and Transit Data Dictionary

This dictionary documents the five CSV datasets used by the Miami
neighborhood recommendation project. The datasets are ZIP/ZCTA-level
snapshots covering Miami-Dade County and are intended for descriptive
neighborhood comparison, not for leasing, lending, pricing, or
demographic-steering decisions.

## Geographic scope and common key

`zip_code` is the project geographic key. The authoritative project
allowlist is [miami_dade_zctas.txt](../miami_dade_zctas.txt). ZIP codes
are stored as strings so leading zeroes, if present, are preserved.

- `Rental-Market.csv` uses a validated union of valid HUD and ZORI ZIPs.
- `Miami_rental_values.csv` and `Miami_home_values.csv` use Zillow
  Research ZIP-level records filtered to the project geography.
- `miami_transit.csv` contains one row per project ZIP with at least one
  assigned transit stop.
- `HUD-SAFMR.csv` is the raw HUD source and can contain ZIPs outside the
  project allowlist; those rows must be filtered before project use.

## Dataset inventory

| Dataset | Location | Granularity | Main purpose |
|---|---|---|---|
| `Rental-Market.csv` | `data/cleaned/` | One row per valid project ZIP | Combined ZORI rent and HUD rent benchmarks |
| `Miami_rental_values.csv` | `data/cleaned/` | One row per Zillow ZIP | Monthly Zillow Observed Rent Index values |
| `Miami_home_values.csv` | `data/cleaned/` | One row per Zillow ZIP | Monthly Zillow Home Value Index values |
| `miami_transit.csv` | `data/raw/google_transit/` | One row per transit-served project ZIP | Aggregated Miami-Dade transit access and service |
| `HUD-SAFMR.csv` | `data/raw/` | One row per HUD ZIP | HUD Small Area Fair Market Rents by bedroom size |

------------------------------------------------------------------------

# 1. `Rental-Market.csv`

## Purpose

The final ZIP-level rental-market table combines Zillow rent estimates
with HUD Small Area Fair Market Rent benchmarks. It is designed to give
the recommender both a market-observed rent signal and a standardized
affordability reference.

The table was created by normalizing each source ZIP, filtering against
`miami_dade_zctas.txt`, and performing a one-to-one **outer merge** on
`zip_code`. Therefore, a valid ZIP can have HUD values without ZORI
values. Missing ZORI values mean that the Zillow source did not provide a
value for that ZIP/month; they do not mean that rent is zero.

## Columns

| Column | Type | Description |
|---|---|---|
| `zip_code` | string | Five-character Miami-Dade project ZIP/ZCTA and primary join key. |
| `zori_2026_01` | float | Zillow Observed Rent Index for January 2026. |
| `zori_2026_02` | float | Zillow Observed Rent Index for February 2026. |
| `zori_2026_03` | float | Zillow Observed Rent Index for March 2026. |
| `zori_2026_04` | float | Zillow Observed Rent Index for April 2026. |
| `zori_2026_05` | float | Zillow Observed Rent Index for May 2026. |
| `zori_2026_06` | float | Zillow Observed Rent Index for June 2026. |
| `zori_2026_07` | float | Zillow Observed Rent Index for July 2026. |
| `zori_2026_08` | float | Zillow Observed Rent Index for August 2026. |
| `zori_latest_rent` | float | Latest available ZORI value in this snapshot; equal to `zori_2026_08`. |
| `hud_efficiency` | float | HUD monthly Fair Market Rent benchmark for an efficiency unit. |
| `hud_1_bedroom` | float | HUD monthly Fair Market Rent benchmark for a one-bedroom unit. |
| `hud_2_bedroom` | float | HUD monthly Fair Market Rent benchmark for a two-bedroom unit. |
| `hud_3_bedroom` | float | HUD monthly Fair Market Rent benchmark for a three-bedroom unit. |
| `hud_4_bedroom` | float | HUD monthly Fair Market Rent benchmark for a four-bedroom unit. |
| `zori_source` | string | Provenance label for ZORI fields: `Zillow ZORI`. |
| `hud_source` | string | Provenance label for HUD fields: `HUD Small Area Fair Market Rents`. |

## Processing and formulas

1. Normalize source ZIPs by stripping whitespace, removing a trailing
   `.0` introduced by numeric CSV parsing, and left-padding to five
   characters.
2. Reject missing or malformed ZIPs.
3. Keep only ZIPs in `miami_dade_zctas.txt`.
4. Rename ZORI monthly columns from date names such as `2026-08-31` to
   names such as `zori_2026_08`.
5. Set:

   ```text
   zori_latest_rent = zori_2026_08
   ```

6. Rename HUD bedroom fields to the `hud_` names shown above.
7. Merge the two validated sources with an outer join on `zip_code`.

## Interpretation

ZORI is a modeled market rent index and is not an individual listing or
guaranteed asking rent. HUD SAFMR is a policy benchmark and is not a
prediction of the rent for every property. The two measures should be
presented as complementary signals rather than interchangeable values.

------------------------------------------------------------------------

# 2. `Miami_rental_values.csv`

## Purpose

This is the cleaned Zillow ZIP-level rental source used to create the
ZORI fields in `Rental-Market.csv`. Each monthly value represents a
Zillow Observed Rent Index estimate for the ZIP.

## Columns

| Column | Type | Description |
|---|---|---|
| `RegionID` | int | Zillow geographic identifier. |
| `SizeRank` | int | Zillow geographic size/ranking field. |
| `RegionName` | string | ZIP code supplied by Zillow; renamed to `zip_code` during the merge. |
| `RegionType` | string | Geographic level, expected to be `zip`. |
| `StateName` | string | State label, expected to be `FL`. |
| `State` | string | State abbreviation, expected to be `FL`. |
| `City` | string | City label associated with the ZIP. |
| `Metro` | string | Metropolitan-area label. |
| `CountyName` | string | County label, expected to be Miami-Dade County for project rows. |
| `2026-01-31` | float | January 2026 ZORI value. |
| `2026-02-28` | float | February 2026 ZORI value. |
| `2026-03-31` | float | March 2026 ZORI value. |
| `2026-04-30` | float | April 2026 ZORI value. |
| `2026-05-31` | float | May 2026 ZORI value. |
| `2026-06-30` | float | June 2026 ZORI value. |
| `2026-07-31` | float | July 2026 ZORI value. |
| `2026-08-31` | float | August 2026 ZORI value. |

## Cleaning notes

`RegionName` is normalized as the ZIP join key. Zillow metadata columns
are retained in this source file for traceability but are not included
in the final `Rental-Market.csv`. Missing monthly observations are
preserved as missing values.

------------------------------------------------------------------------

# 3. `Miami_home_values.csv`

## Purpose

This is the cleaned Zillow ZIP-level home-value source. It contains
monthly Zillow Home Value Index estimates and is separate from the rental
market table.

## Columns

| Column | Type | Description |
|---|---|---|
| `RegionID` | int | Zillow geographic identifier. |
| `SizeRank` | int | Zillow geographic size/ranking field. |
| `RegionName` | string | ZIP code supplied by Zillow and usable as the project ZIP key after normalization. |
| `RegionType` | string | Geographic level, expected to be `zip`. |
| `StateName` | string | State label, expected to be `FL`. |
| `State` | string | State abbreviation, expected to be `FL`. |
| `City` | string | City label associated with the ZIP. |
| `Metro` | string | Metropolitan-area label. |
| `CountyName` | string | County label, expected to be Miami-Dade County for project rows. |
| `2026-01-31` | float | January 2026 Zillow Home Value Index estimate. |
| `2026-02-28` | float | February 2026 Zillow Home Value Index estimate. |
| `2026-03-31` | float | March 2026 Zillow Home Value Index estimate. |
| `2026-04-30` | float | April 2026 Zillow Home Value Index estimate. |
| `2026-05-31` | float | May 2026 Zillow Home Value Index estimate. |
| `2026-06-30` | float | June 2026 Zillow Home Value Index estimate. |
| `2026-07-31` | float | July 2026 Zillow Home Value Index estimate. |
| `2026-08-31` | float | August 2026 Zillow Home Value Index estimate. |

## Cleaning and intended use

`RegionName` is the geographic identifier, not a neighborhood name.
Monthly values are modeled index estimates and should not be interpreted
as a specific property's sale price or appraisal. Use the same
allowlist and ZIP normalization rules as the rental data before joining
this file to other project tables.

------------------------------------------------------------------------

# 4. `HUD-SAFMR.csv`

## Purpose

This raw file contains HUD Small Area Fair Market Rent benchmarks by ZIP
and bedroom size. It provides a standardized reference for comparing
housing costs across ZIP codes.

## Columns

| Column | Type | Description |
|---|---|---|
| `zip_code` | string | HUD ZIP code and potential project join key. |
| `efficiency` | float | Monthly HUD benchmark for an efficiency unit. |
| `one_bedroom` | float | Monthly HUD benchmark for a one-bedroom unit. |
| `two_bedroom` | float | Monthly HUD benchmark for a two-bedroom unit. |
| `three_bedroom` | float | Monthly HUD benchmark for a three-bedroom unit. |
| `four_bedroom` | float | Monthly HUD benchmark for a four-bedroom unit. |

## Cleaning and transformation

The merge script validates that `zip_code` is present, five digits, and
unique within the source. It filters out HUD ZIPs not present in
`miami_dade_zctas.txt`, then renames the bedroom columns with a `hud_`
prefix for `Rental-Market.csv`.

HUD values are monthly benchmark rents. They are not unit-level listings,
rent ceilings for every property, or evidence that a particular unit is
available.

------------------------------------------------------------------------

# 5. `miami_transit.csv`

## Purpose

This is a ZIP-level aggregation of Miami-Dade GTFS data. It measures
transit presence, route diversity, scheduled service, headways, and
selected accessibility indicators for ZIPs with at least one assigned
transit stop.

The raw GTFS feed does not contain ZIP codes. Stops are assigned to
Census ZCTAs using `stop_lat` and `stop_lon`, then filtered to the
project allowlist before aggregation.

## Columns

| Column | Type | Description |
|---|---|---|
| `zip_code` | string | Miami-Dade project ZIP/ZCTA assigned from transit-stop coordinates. |
| `transit_stop_count` | int | Number of distinct GTFS stops in the ZIP. |
| `unique_route_count` | int | Number of distinct routes serving the ZIP. |
| `transit_types` | string | Sorted pipe-separated modes, such as `bus|metrorail`. |
| `bus_route_count` | int | Number of distinct routes with GTFS `route_type = 3`. |
| `metrorail_route_count` | int | Number of distinct routes with GTFS `route_type = 2`. |
| `metromover_route_count` | int | Number of distinct routes with GTFS `route_type = 0`, interpreted as Metromover for this Miami-Dade feed. |
| `weekday_departures` | int | Distinct scheduled stop departures associated with Monday-Friday service. |
| `saturday_departures` | int | Distinct scheduled stop departures associated with Saturday service. |
| `sunday_departures` | int | Distinct scheduled stop departures associated with Sunday service. |
| `weekday_median_headway_minutes` | float | ZIP median of stop-route median gaps between consecutive weekday departures. |
| `weekend_median_headway_minutes` | float | ZIP median of stop-route median gaps between consecutive Saturday or Sunday departures. |
| `morning_peak_departures` | int | Weekday scheduled departures from 07:00 through 08:59. |
| `evening_peak_departures` | int | Weekday scheduled departures from 16:00 through 18:59. |
| `accessible_stop_share` | float | Share of stops marked wheelchair accessible among stops with known stop accessibility. |
| `wheelchair_accessible_trip_share` | float | Share of trips marked wheelchair accessible among trips with known vehicle accessibility. |
| `bike_allowed_trip_share` | float | Share of trips marked as allowing bicycles among trips with known bike status. |
| `gtfs_agency` | string | Source agency label, currently `Miami-Dade Transit`. |
| `service_start_date` | string | Earliest service `start_date` in the GTFS calendar. |
| `service_end_date` | string | Latest service `end_date` in the GTFS calendar. |
| `data_as_of` | date | Date the ZIP-level output was generated. |

## GTFS relationships used

```text
stops.stop_id
       ^
       |
stop_times.stop_id -- stop_times.trip_id --> trips.trip_id
                                               |
                                               +-- trips.route_id --> routes.route_id
                                               |
                                               +-- trips.service_id --> calendar.service_id
```

## Derived-feature formulas and processing

- Stops are spatially joined to Census ZCTA polygons using latitude and
  longitude.
- Transit stops outside the project ZIP allowlist are removed.
- Route counts use distinct `route_id` values; they are not summed across
  stops, which avoids double-counting a route serving multiple stops.
- Departure counts deduplicate `zip_code`, `stop_id`, `trip_id`, and
  `departure_time` before counting.
- Weekday, Saturday, and Sunday classifications come from the matching
  flags in `calendar.txt` through each trip's `service_id`.
- GTFS times are converted with:

  ```text
  minutes = hours * 60 + minutes + seconds / 60
  ```

  Times beyond `24:00:00` are preserved as next-day schedule times.
- Headways use positive consecutive departure gaps within ZIP, stop, and
  route. Pair-level medians are then aggregated to the ZIP median.
- `route_type` is mapped for this feed as `3 = bus`, `2 = metrorail`,
  and `0 = metromover`.
- Accessibility and bike shares use known source values only. In the
  current feed, `1` means yes, `2` means no, and `0` or missing is treated
  as unknown and excluded from the denominator.

## Source-data limitations

The current stop accessibility field is overwhelmingly coded as `2`, so
`accessible_stop_share` has limited coverage and should not be interpreted
as proof that all unmarked stops are inaccessible. The current
`wheelchair_accessible` and `bikes_allowed` trip fields are identical in
the source snapshot, so their output shares are also identical here.
`calendar_dates.txt` exceptions are not applied to the regular schedule
aggregates; the output represents the regular `calendar.txt` schedule.

------------------------------------------------------------------------

# Cross-dataset joins

The common project join is:

```text
Rental-Market.zip_code
Miami_rental_values.RegionName
Miami_home_values.RegionName
HUD-SAFMR.zip_code
miami_transit.zip_code
```

Before joining, normalize `RegionName` to `zip_code` and preserve it as
a string. Validate that every retained ZIP is in
`miami_dade_zctas.txt`. Do not join on `City`, `Metro`, or free-text
neighborhood labels because those fields are not the project geographic
key.

# Missing values and responsible use

- Missing ZORI values represent unavailable Zillow observations and must
  remain missing rather than being replaced with zero.
- A ZIP absent from `miami_transit.csv` has no assigned transit stop in
  the final transit aggregation; absence is not automatically evidence
  that no transportation exists.
- HUD benchmarks and Zillow indices measure different concepts and
  should not be treated as interchangeable prices.
- All datasets are snapshots with source-specific update schedules.
  Store the source date or output date when using them in a model.
- Do not use these aggregates to make decisions about protected groups,
  steer people away from neighborhoods, deny housing opportunities, or
  represent synthetic or modeled values as guaranteed listings.

# Rent Trends Data Dictionary

## Dataset

- **File:** `rent-trends.csv`
- **Purpose:** Provide ZIP-level rent trend features for Miami-Dade County neighborhoods.
- **Primary source:** Zillow Observed Rent Index (ZORI)
- **Raw source:** `../raw/Zip_zori_uc_sfrcondomfr_sm_month.csv`
- **History source:** `zori_history.csv`
- **Build script:** `../../notebooks/rental-trend.py`
- **Row grain:** One row per Miami-Dade ZIP code.
- **Latest source observation:** `2026-08` in the current build.

ZORI is a smoothed ZIP-level indicator of observed market-rate asking rents. It
is an area-level estimate and should not be interpreted as the price of every
available unit or as a live listing price.

## Column definitions

| Column | Type | Definition | Calculation or notes |
|---|---|---|---|
| `zip_code` | string | Five-character ZIP/ZCTA identifier. | Join key for other ZIP-level datasets. Leading zeroes are preserved. |
| `latest_rent_usd` | float | Latest available ZORI rent estimate in U.S. dollars for the ZIP code. | Uses the latest available monthly observation in the filtered ZORI history. |
| `rent_3_month_change_pct` | float | Percentage change in ZORI over the latest three months. | `(latest rent - rent 3 months earlier) / rent 3 months earlier * 100` |
| `rent_12_month_change_pct` | float | Percentage change in ZORI over the latest twelve months. | `(latest rent - rent 12 months earlier) / rent 12 months earlier * 100` |
| `rent_24_month_change_pct` | float | Percentage change in ZORI over the latest twenty-four months. | `(latest rent - rent 24 months earlier) / rent 24 months earlier * 100` |
| `rent_volatility` | float | Standard deviation of recent monthly ZORI percentage changes. | Standard deviation of the latest twelve monthly percentage changes, expressed in percentage points. This describes rent stability, not investment risk. |
| `rent_direction` | categorical string | Recent direction of the ZIP-level ZORI indicator. | Based on `rent_3_month_change_pct`: `increasing` if greater than `1%`, `decreasing` if less than `-1%`, otherwise `stable`. |
| `source` | string | Name of the data provider and index. | Always `Zillow ZORI` in this output. |
| `source_date` | string (`YYYY-MM`) | Month of the latest ZORI observation used for the row. | This is the observation month, not the date that a rental listing was published. |

## Direction heuristic

`rent_direction` is a project-defined classification rather than a Zillow
field:

```text
rent_3_month_change_pct >  1.0  → increasing
rent_3_month_change_pct < -1.0  → decreasing
otherwise                       → stable
```

The threshold prevents very small changes from being presented as meaningful
rent movement.

## Missing values

The build does not interpolate or substitute missing historical observations.
If a ZIP does not have the required comparison month, the corresponding
long-term change feature is `NaN`.

`rent_volatility` is `NaN` when the ZIP does not have all twelve recent monthly
changes needed by the calculation. `rent_direction` remains available when the
three-month change can be calculated.

## Coverage and filtering

The build:

1. Loads the full monthly ZORI file.
2. Normalizes ZIP values to five-character strings.
3. Retains ZIP codes listed in `../raw/miami_dade_zctas.txt`.
4. Removes missing ZORI rent observations from the long-format history.
5. Derives one trend row per retained ZIP code.

The current output contains 74 ZIP codes. Coverage varies by ZIP because Zillow
does not publish an observation for every ZIP and month.

## Interpretation guidance

Use the fields to describe area-level rent movement, for example:

> Zillow's rent indicator for this ZIP increased approximately 2.0% over the
> past twelve months.

Avoid claims that every apartment or household in the ZIP experienced the same
change. These features should be shown with their `source` and `source_date`
because they are historical estimates rather than live availability or quoted
unit prices.
