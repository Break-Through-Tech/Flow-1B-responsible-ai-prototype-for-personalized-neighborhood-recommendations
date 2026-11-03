# Project Data

The `data/` folder contains the ZIP-code-level data used to build and explain
the Miami neighborhood recommender. It combines public demographic and housing
statistics, rental-market estimates, transit access measurements, area names,
and small demonstration datasets for recommendation cards and text themes.

The data is organized into two main stages:

- **`raw/`** contains source extracts and starter files. These files preserve
  the original values and schemas as much as possible.
- **`cleaned/`** contains model-ready exports produced by the cleaning
  notebooks. Cleaning includes steps such as ZIP validation, missing-value
  handling, feature extraction, and categorical one-hot encoding.

Most tables use a five-digit Miami-Dade ZIP/ZCTA as their join key. ZIP-level
statistics describe an area in aggregate; they do not describe every property
or resident and are not live listings.

## Folder structure

```text
data/
├── README.md
├── data_dictionary.md
├── expanded_data_dictioonary.md
├── raw/
│   ├── area_features.csv
│   ├── area_options.csv
│   ├── crowd_text_snippets.csv
│   ├── miami-rents.csv
│   ├── miami_dade_public_features.csv
│   ├── miami_dade_zctas.txt
│   └── new/
│       ├── HUD-SAFMR.csv
│       ├── Miami_home_values.csv
│       ├── Miami_rental_values.csv
│       ├── area-name.csv
│       ├── miami_dade_zip_area_names.csv
│       ├── miami_transit.csv
│       ├── zori_history.csv
│       ├── raw-new-data-dictionary.md
│       └── transit-data/       # Miami-Dade GTFS source tables
└── cleaned/
    ├── area_features_cleaned.csv
    ├── area_options_cleaned.csv
    ├── crowd_text_snippets_cleaned.csv
    ├── public_features_cleaned.csv
    ├── cleaned_data.md
    └── new/
        ├── Miami-rents-cleaned.csv
        ├── area-name-cleaned.csv
        ├── miami-transit-cleaned.csv
        └── data-dictiionary-new.md
```

## How the data is used

The recommender is designed for newcomers to Miami who are comparing
neighborhoods for an apartment. A user can provide a household type
(`alone` or `with_co_leaser`), a housing preference (`own_apartment` or
`co_living`), a budget, and lifestyle priorities such as transit, walkability,
quiet, social activity, or pet-friendliness.

The recommender uses neighborhood features to rank areas. The `area_options`
files are synthetic recommendation-card examples, not real apartments or
housing availability. Co-living is an optional path for people who are alone
and specifically want shared housing; it should not be confused with having a
co-leaser on a private lease.

## `raw/`: source and starter data

The raw files are inputs to the cleaning and feature-building workflows. They
should not be overwritten when creating derived data.

### Starter recommender tables

| File | Description |
|---|---|
| [`area_features.csv`](raw/area_features.csv) | ZIP-level neighborhood features used for ranking, including rent bands, transit, social activity, quietness, pet-friendliness, walkability, migration, and housing-preference proxies. |
| [`area_options.csv`](raw/area_options.csv) | Synthetic recommendation cards. Each row connects a ZIP to a rent band, household type, housing preference, tags, and a short summary. These are demo records, not real listings. |
| [`crowd_text_snippets.csv`](raw/crowd_text_snippets.csv) | Small demonstration text snippets associated with a ZIP and a theme such as transit, social activity, quietness, or co-living. |
| [`miami_dade_public_features.csv`](raw/miami_dade_public_features.csv) | Public ZIP-level housing, population, migration, rent, and home-value features from Census-style and Zillow-style sources. |
| [`miami-rents.csv`](raw/miami-rents.csv) | Combined ZIP-level rent table containing monthly ZORI estimates, HUD bedroom benchmarks, rent changes, volatility, trend labels, and source-date fields. |
| [`miami_dade_zctas.txt`](raw/miami_dade_zctas.txt) | Plain-text list of Miami-Dade ZIP/ZCTA codes used to scope the project geography. |

### Expanded rent, geography, and transit inputs

| File | Description |
|---|---|
| [`HUD-SAFMR.csv`](raw/new/HUD-SAFMR.csv) | HUD Small Area Fair Market Rent benchmarks for efficiency/studio through four-bedroom units. These are reference benchmarks, not observed asking rents. |
| [`Miami_home_values.csv`](raw/new/Miami_home_values.csv) | Wide ZIP-level monthly home-value estimates with provider geography metadata for January-August 2026. |
| [`Miami_rental_values.csv`](raw/new/Miami_rental_values.csv) | Wide ZIP-level monthly rental-value estimates with provider geography metadata for January-August 2026. |
| [`zori_history.csv`](raw/new/zori_history.csv) | Long-format Zillow Observed Rent Index history: one ZIP/month observation with rent, source, and source-date fields. |
| [`area-name.csv`](raw/new/area-name.csv) | ZIP-to-area lookup containing postal city, primary area name, area-name type, secondary area names, and provenance fields. |
| [`miami_dade_zip_area_names.csv`](raw/new/miami_dade_zip_area_names.csv) | Additional ZIP geography and display-name lookup with area, ZIP type, and modeling-note fields. |
| [`miami_transit.csv`](raw/new/miami_transit.csv) | ZIP-level transit features derived from Miami-Dade GTFS data, including stops, routes, departures, headways, peak service, accessibility, and bike access. |

### Transit source files

[`raw/new/transit-data/`](raw/new/transit-data/) contains the original
GTFS tables used to derive [`miami_transit.csv`](raw/new/miami_transit.csv):

- `stops.txt`: stop locations and identifiers.
- `routes.txt`: route identifiers, names, and transit modes.
- `trips.txt`: trips assigned to routes and service patterns.
- `stop_times.txt`: the scheduled arrival and departure times for trips.
- `calendar.txt`: recurring service-day and date ranges.
- `calendar_dates.txt`: exceptions to the recurring service calendar.
- `shapes.txt`: geographic paths followed by transit trips.

## `cleaned/`: model-ready data

The cleaned tables are derived from raw inputs. They retain ZIP join keys while
converting fields into forms used by analysis and the recommender.

### Cleaned starter tables

| File | Description |
|---|---|
| [`public_features_cleaned.csv`](cleaned/public_features_cleaned.csv) | Cleaned public features with validated ZIPs, imputed values, and winsorized housing, rent, and migration columns. |
| [`area_features_cleaned.csv`](cleaned/area_features_cleaned.csv) | Cleaned ranking features. The illustrative rent band is one-hot encoded into `rent_band_*` columns. |
| [`area_options_cleaned.csv`](cleaned/area_options_cleaned.csv) | Cleaned synthetic cards with extracted numeric rent/migration fields and one-hot columns for housing preference, household type, rent band, and tags. |
| [`crowd_text_snippets_cleaned.csv`](cleaned/crowd_text_snippets_cleaned.csv) | Cleaned theme indicators derived from the demonstration snippet data. Raw text and identifiers are not included in this model-ready export. |

The transformation details and final schemas are documented in
[`cleaned/cleaned_data.md`](cleaned/cleaned_data.md).

### Cleaned expanded tables

| File | Description |
|---|---|
| [`Miami-rents-cleaned.csv`](cleaned/new/Miami-rents-cleaned.csv) | Model-ready rent table combining latest ZORI rent, HUD bedroom benchmarks, three-, twelve-, and twenty-four-month changes, volatility, and a trend label. |
| [`miami-transit-cleaned.csv`](cleaned/new/miami-transit-cleaned.csv) | Model-ready transit features with counts, departures, headways, accessibility shares, and one-hot transit-mode indicators. |
| [`area-name-cleaned.csv`](cleaned/new/area-name-cleaned.csv) | Model-ready ZIP geography lookup with primary area fields and one-hot secondary-area indicators. |

The expanded schemas and cleaning rules are documented in
[`cleaned/new/data-dictiionary-new.md`](cleaned/new/data-dictiionary-new.md).
The raw expanded schemas are documented in
[`raw/new/raw-new-data-dictionary.md`](raw/new/raw-new-data-dictionary.md).

## What was added in the `new/` folders

The `new/` folders contain the project's expanded datasets. They were added
to improve the original starter data in three areas: more detailed rental
information, measurable transit access, and clearer ZIP-to-neighborhood
names. The new data is still ZIP-level and is intended to complement the
original recommender tables rather than replace them.

### 1. More detailed rental-market data

The new rental files separate different types of rental information that were
previously combined into broad rent features:

- **`Miami_rental_values.csv`** provides monthly ZIP-level rental estimates
  from the source provider.
- **`zori_history.csv`** reshapes rental history into one row per ZIP and
  observation month, making it easier to calculate rent changes and trends.
- **`HUD-SAFMR.csv`** adds HUD benchmark rents for studios/efficiencies and
  one- through four-bedroom units. These benchmarks provide a unit-size
  comparison point; they are not live listings.
- **`Miami-rents-cleaned.csv`** combines the latest rental estimate, HUD
  benchmarks, rent changes over multiple time windows, volatility, and a
  direction label (`increasing`, `decreasing`, or `stable`).

Together, these files allow the project to explain affordability and rent
movement instead of using only one broad rent score.

### 2. Home-value context

**`Miami_home_values.csv`** adds monthly ZIP-level home-value estimates. This
provides housing-market context alongside rental data, but it should not be
interpreted as a listing price or as the value of every property in a ZIP.

### 3. Measured transit access

The new transit data replaces a simple or opaque transit proxy with measurable
service features:

- **`transit-data/`** contains the original Miami-Dade GTFS source tables,
  including stops, routes, trips, schedules, service calendars, and route
  shapes.
- **`miami_transit.csv`** aggregates those GTFS records by ZIP, including stop
  counts, route counts, scheduled departures, headways, peak service,
  accessibility, and bike access.
- **`miami-transit-cleaned.csv`** prepares those measurements for modeling and
  converts transit modes into indicator columns.

This makes transit-related recommendations more explainable because they can
refer to actual service measurements.

### 4. Improved area and ZIP names

The new geography files make recommendations easier to interpret:

- **`area-name.csv`** maps ZIP codes to postal cities, primary area names,
  secondary area names, and area-name metadata.
- **`miami_dade_zip_area_names.csv`** provides an additional ZIP-to-area
  lookup with area types, ZIP types, and modeling notes.
- **`area-name-cleaned.csv`** provides the cleaned display-name fields and
  one-hot indicators for secondary area names.

These files help display a human-readable neighborhood name instead of only a
ZIP code. Names are labels for interpretation and should not be treated as
perfect boundaries for a neighborhood.

### 5. New cleaned model inputs

The cleaned files in `cleaned/new/` are the model-ready result of the
expansion. They normalize ZIP identifiers, handle missing or placeholder
values, preserve valid zero measurements, calculate derived rent trends, and
encode multi-valued fields where needed. The original source files remain in
`raw/new/` so that the transformations can be reviewed and reproduced.

## Learn more about the expanded data

For detailed column definitions, data types, cleaning rules, source
relationships, and intended use of the expanded datasets, refer to
[`cleaned/new/data-dictiionary-new.md`](cleaned/new/data-dictiionary-new.md).
This document is the primary reference for understanding the cleaned rental,
transit, and area-name files in `cleaned/new/`.

## Related documentation and limitations

- [`../data_dictionary.md`](../data_dictionary.md) describes the starter
  dataset columns and their intended use.
- [`expanded_data_dictioonary.md`](expanded_data_dictioonary.md) records the
  planned and completed data-expansion roadmap.
- Data is a historical snapshot, not a live rental marketplace.
- Zillow-style indices and HUD benchmarks measure different concepts and
  should not be treated as interchangeable.
- Census suppression codes and other missing-value markers must be handled
  explicitly.
- Do not use these features for tenant screening, eligibility decisions,
  demographic steering, or denying housing access.
