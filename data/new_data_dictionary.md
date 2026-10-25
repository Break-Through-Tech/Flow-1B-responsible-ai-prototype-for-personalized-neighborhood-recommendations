# Miami Filtered Data Dictionary

This document describes the two Miami-only datasets created from the Zillow
home-value and rental source files.

## Files

| File | Description |
|------|-------------|
| `Miami_home_values.csv` | Home-value estimates for ZIP-code regions in Miami, Florida |
| `Miami_rental_values.csv` | Rental-value estimates for ZIP-code regions in Miami, Florida |

Both files use the same geographic columns. The source rows were filtered with
`State == "FL"` and `City == "Miami"`. Monthly price columns dated from 2000
through 2024, inclusive, were removed. The remaining monthly values cover the
available 2025 and 2026 dates.

## Shared geographic columns

| Column | Type | Description |
|--------|------|-------------|
| `RegionID` | integer | Zillow region identifier |
| `SizeRank` | integer | Zillow region size rank ( population of people in that zip area) |
| `RegionName` | string | ZIP code represented by the row |
| `RegionType` | string | Geographic region type; expected to be `zip` |
| `StateName` | string | State name |
| `State` | string | Two-letter state abbreviation; filtered to `FL` |
| `City` | string | City name; filtered to `Miami` |
| `Metro` | string | Metropolitan statistical area name |
| `CountyName` | string | County name |

## Monthly value columns

| Column pattern | Type | Description |
|----------------|------|-------------|
| `YYYY-MM-DD` | float | Monthly estimated dollar value for the ZIP-code region |

The date columns represent month-end observations. The exact set of columns
depends on the source file's available dates and currently includes dates in
2025 and 2026.

### `Miami_home_values.csv`

The monthly columns are Zillow Home Value Index estimates for single-family
homes and condominiums in the ZIP-code region.

### `Miami_rental_values.csv`

The monthly columns are Zillow Observed Rental Index estimates for
single-family residences and condominiums in the ZIP-code region.

## Data-processing notes

- These are geographic aggregate estimates, not individual property listings.
- `RegionName` is a ZIP-code identifier stored by the source as a numeric
  value; preserve it as a ZIP code rather than treating it as a measurement.
- Missing monthly observations may be represented as empty values after CSV
  loading and should be handled explicitly.
- Values are historical snapshots and should not be interpreted as live prices
  or guaranteed market quotes.
- The datasets are limited to rows labeled `Miami`, which may not include all
  Miami-Dade ZIP codes whose source city label differs.

## Limitations and responsible use

- Do not use these aggregate estimates for automated leasing, lending, or
  housing-access decisions.
- Do not infer individual household characteristics from ZIP-code-level data.
- Treat the data as exploratory inputs for neighborhood analysis and
  recommendation prototyping only.


## Next step

1. explore census dta 
2. find review for Miami household data
3. look up if transportation is a compulsory data 
4. merge census and zillow dataste to gether , like miami_dade_public_features.csv
5. for transit feature , should we expand further that include how close we can reach in that area based on zip codeor keep it as a scale of 0-1 
6. include flood risk of that area?


## possible feature to add on 
or every recommended ZIP, show:
1. Typical rent
2. Difference from the user’s budget
3. Estimated commute
4. Nearby transit options
5. Rent trend
6. Flood-risk information
7. Explanation of why it was recommended

| Information | Why it matters |
|---|---|
| Current apartment listings | Zillow indexes estimate typical rent but do not show which units are currently available |
| Unit size and bedrooms | A $2,300 studio and a $2,300 two-bedroom are not equivalent |
| Workplace coordinates | Needed to calculate realistic commuting time |
| Transit stops and schedules | Important for newcomers without cars |
| Flood zones | Particularly important in Miami |
| Grocery stores and essential services | Helps measure daily convenience |
| Upfront fees | Deposits, parking, application fees and HOA charges affect affordability |

flood zone data 
https://www.miamidade.gov/global/economy/building/flood-protection/flood-zone-maps.page?utm_source=chatgpt.com 

transit data 
https://www.miamidade.gov/global/transportation/open-data-feeds.page?utm_source=chatgpt.com


