# Data Dictionary

## miami_dade_public_features.csv

**Real public aggregate data** for Miami-Dade ZIP codes (ZCTAs). Pulled from Census ACS, migration tables, and Zillow Research-style indices.

| Column | Type | Description |
|--------|------|-------------|
| NAME | string | Census ZCTA label |
| B01003_001E | int | Total population (ACS) |
| B25064_001E | int | Median gross rent (ACS); `-666666666` = missing/suppressed |
| B25077_001E | int | Median home value (ACS) |
| B07003_001E | int | Total population 1 year and over (migration universe) |
| B07003_004E | int | Same house 1 year ago |
| B07003_008E | int | Moved within same county |
| B07003_010E | int | Moved from different county |
| B11016_001E | int | Total households |
| B25003_002E | int | Owner-occupied units |
| B25003_003E | int | Renter-occupied units |
| zip | string | 5-digit ZIP code |
| moved_different_house_pct | float | Share who moved to a different house (derived) |
| median_rent_usd | int | Median rent (ACS or derived) |
| population | int | Population count |
| zillow_home_value_index | float | Zillow Research-style home value index |
| zillow_rent_index | float | Zillow Research-style rent index |

## miami_dade_zctas.txt

Plain-text list of Miami-Dade ZIP codes used to scope the project.

## zcta_geography.csv

One row per Miami-Dade ZCTA (80 rows; the 5 PO-box ZIPs in `miami_dade_zctas.txt` have no ZCTA). Built by `experiments/feature_candidates/build_data.py`. Used for land area (census feature set), distance for `near` requests, and the USPS city shown next to `area_name` (which is never overwritten).

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| zip | string | 5-digit ZCTA | |
| land_sqmi | float | Land area, square miles | 2023 Census Gazetteer `ALAND_SQMI` (public domain) |
| lat, lon | float | ZCTA internal point | Gazetteer `INTPTLAT`, `INTPTLONG` |
| usps_city | string | USPS city name for the ZIP | ZIP Code Business Patterns 2021 |

## census_features.csv

Raw counts per ZCTA for the proposed `census` feature set; the engine converts them to percentiles. Built by `experiments/feature_candidates/build_data.py`. Business counts are by mailing ZIP, which does not exactly match ZCTA boundaries.

| Column | Description | Source |
|--------|-------------|--------|
| population | Total population | `public_features_cleaned.csv` (ACS 2018-22) |
| workers, transit_commuters, walk_commuters | Workers 16+ by means of transportation to work | ACS 2018-22 B08301 (E001, E010, E019) |
| households, households_no_vehicle | Households and those with no vehicle | ACS 2018-22 B08201 (E001, E002) |
| food_drink_establishments | Restaurants and bars (NAICS 722) | ZIP Code Business Patterns 2021 |
| bar_establishments | Drinking places, incl. bars and nightclubs (NAICS 7224) | ZIP Code Business Patterns 2021 |

## neighborhood_aliases.csv

Name-to-ZIP dictionary for `near` requests. One row per (alias, zip); a name can map to several ZIPs (e.g. Doral). Names covering more than 10 ZIPs (e.g. "Miami") are rejected as too broad.

| Column | Description |
|--------|-------------|
| alias | Neighborhood or city name as a user might type it |
| zip | 5-digit ZCTA |
| source | `area_features.csv area_name` (advisor's starter labels) or `USPS city, ZIP Code Business Patterns 2021` |

## area_features.csv

**Blended starter file** for the recommender. Joins public rent/migration fields with normalized preference proxies (transit, social, quiet, pet-friendly, walkable). Some `area_name` labels are illustrative neighborhood names.

| Column | Type | Description |
|--------|------|-------------|
| zip | string | Miami ZIP code |
| area_name | string | Neighborhood or ZCTA label |
| rent_band | string | Illustrative rent range bucket |
| transit | float 0-1 | Transit access proxy |
| social | float 0-1 | Social activity proxy |
| quiet | float 0-1 | Quiet environment proxy |
| pet_friendly | float 0-1 | Pet-friendly proxy |
| walkable | float 0-1 | Walkability proxy |
| migration_score | float 0-1 | In-migration activity proxy (derived) |
| median_rent_usd | int | Rent index from public sources |
| co_living_friendly | float 0-1 | How suitable the ZIP is for co-living (only used when user selects co_living) |

**Primary demo ZIPs:** Wynwood `33127`, Downtown `33128`, Brickell `33130`.

## area_options.csv

**Synthetic** demo cards. **NOT REAL LISTINGS.**

| Column | Type | Description |
|--------|------|-------------|
| option_id | string | Synthetic ID (SYN-*) |
| zip | string | Join key to area_features |
| rent_band | string | Illustrative band |
| housing_preference | string | `own_apartment` or `co_living` |
| household | string | `alone` or `with_co_leaser` (someone on the same private lease — not co-living) |
| tags | string | Comma-separated preference tags |
| summary | string | Short description (e.g. couple + own apartment in Wynwood) |
| disclaimer | string | Must display NOT A REAL LISTING |

## crowd_text_snippets.csv

Demo snippets mimicking public review/forum text for NLP themes. Replace with real filtered corpora during model development.

| Column | Type | Description |
|--------|------|-------------|
| snippet_id | string | Row ID |
| zip | string | Associated ZIP |
| source | string | e.g. kaggle_reviews (document real source when replaced) |
| theme | string | transit, social, quiet, co_living, etc. |
| text | string | Snippet text (aggregate use only) |

## Limitations

- Snapshot data only — not live market feeds.
- Census suppression codes must be handled explicitly in preprocessing.
- Synthetic options are for UI demonstration; never present them as real listings.
- Do not use outputs for leasing decisions or demographic steering.
- English-only text bias may apply when using real review corpora.
