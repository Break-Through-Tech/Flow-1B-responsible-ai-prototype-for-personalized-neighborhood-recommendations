# Cleaned Data Dictionary

Overview of every change made from the raw CSVs to the `*_cleaned.csv` files.

- **Source notebook:** `cleaning.ipynb`
- **Raw inputs:** `../data/miami_dade_public_features.csv`, `area_features.csv`, `area_options.csv`, `crowd_text_snippets.csv`
- **Outputs:** `../data/{public_features, area_features, area_options, crowd_text_snippets}_cleaned.csv` (raw files are never overwritten)
- **NOTE**- miami_dade_public_features are written as 'public_features' in the cleaning.ipynb

---

## 1. Pipeline

```
RAW CSVs (4 datasets)
   │
   ├─ 1. Load (zip kept as string)
   ├─ 2. Sentinel values (-666666666, -6666666666) → NaN          [all 4]
   ├─ 3. Mean-impute 12 NaN columns                               [miami_dade_public_features]
   ├─ 4. Extract migration_score + median_rent from summary       [area_options]
   ├─ 5. Drop unneeded columns                                    [all 4]
   ├─ 6. Drop rows with more than 3 NaN                           [all 4]
   ├─ 7. Validate ZIP (5 digits, not empty)                       [all 4]
   ├─ 8. One-hot encode categoricals + tags                       [3 datasets, except]
   ├─ 9. Drop rows with 4 or more zeros                           [miami_dade_public_features]
   ├─ 10. Replace remaining zeros with column mean                [miami_dade_public_features]
   ├─ 11. Winsorize skewed columns (upper percentile cap)         [miami_dade_public_features]
   ├─ 12. Normalize features for the recommender                  [NOT YET APPLIED, see §5]
   └─ 13. Data-quality checks → save *_cleaned.csv
```

---

## 2. Missing-value decisions

| # | Decision | Applies to | Rule | Why |
|---|---|---|---|---|
| 1 | **Sentinel codes → `NaN`** | All 4 datasets | `-666666666` and `-6666666666` become `NaN` | These are Census "not available" codes, not real numbers |
| 2 | **Mean imputation** | `miami_dade_public_features` | `NaN` replaced by the column mean for the 12 columns listed below | Only 12 named columns are imputed. Existing values and legitimate zeros are untouched |
| 3 | **Drop rows with too many `NaN`** | All 4 datasets | Drop a row if it has **more than 3** `NaN` (3 or fewer are kept). Runs after column drops | Rows that are mostly empty carry no signal |
| 4 | **Invalid ZIP → drop row** | All 4 datasets | Keep only rows whose `zip` is present and matches exactly 5 digits | `zip` is the join key between datasets |
| 5 | **Unparseable summary values → `0`** | `area_options` | If `migration_score` or `median_rent` cannot be extracted from `summary`, the value is set to `0` | Keeps the numeric dtype. **Note:** this `0` means "missing", not "zero" |
| 6 | **Rows with 4 or more zeros → drop** | `miami_dade_public_features` | Count zeros across all numeric columns except `zip`. Drop if the count is 4 or more | A row with many zeros is a placeholder or empty area, not a real neighborhood. In the last run: zero counts were 0 (76 rows), 1 (2 rows), 9 (2 rows), so the 2 rows with 9 zeros were dropped (80 → 78 rows) |
| 7 | **Remaining zeros → column mean** | `miami_dade_public_features` | Every remaining `0` in a numeric column (except `zip`) is replaced by that column's mean, **calculated from non-zero values only** | Zeros are treated as missing data and would otherwise create fake low outliers |

---

## 3. Winsorization (percentile capping)

**Method:** one-sided (upper) percentile cap. Values above the cap are set to the cap value. Rows are never deleted, and the lower end is never changed (no left tail problem was seen).

```python
cap = column.quantile(0.95)          # or 0.99 for rent index
winsorized = column.clip(upper=cap)
```

| Original column | New column | Percentile cap | Extra check in notebook |
|---|---|---|---|
| `zillow_home_value_index` | `winsorized_zillow_home_value_index` | Upper **95th** | Prints cap, count capped, skew before/after |
| `zillow_rent_index` | `winsorized_zillow_rent_index` | Upper **99th** | `assert` exactly **1** row capped |
| `moved_different_house_pct` | `winsorized_moved_different_house_pct` | Upper **95th** | `assert` exactly **4** rows capped |
| `B25077_001E` (median home value, ACS) | `winsorized_B25077_001E` | Upper **95th** | `assert` exactly **4** rows capped |
| `B25064_001E` (median gross rent, ACS) | `winsorized_B25064_001E` | Upper **95th** | Prints cap, count capped, skew before/after |
| `B07003_008E` (moved within same county, ACS) | `winsorized_B07003_008E` | Upper **95th** | Prints cap, count capped, skew before/after |

**Why these choices**

- **Right-skewed, extreme tail only:** e.g. `zillow_home_value_index` had one value near 6.4M while most values sit between 300k and 1M.
- **95th** (about 4 of ~78 rows) tames the extreme point without flattening the whole tail. **99th** was used for the rent index because only one row was extreme.
- **Cap, don't delete:** the dataset is small (~80 rows), so every row matters.

**After winsorization**

- The **original columns are dropped** (`zillow_home_value_index`, `zillow_rent_index`, `moved_different_house_pct`, `B25077_001E`, `B25064_001E`, `B07003_008E`). Use the `winsorized_*` names downstream.
- Caps were computed on the **full cleaned dataset** (no train/test split), because the recommender scores all neighborhoods together. If you train a supervised model with a split, recompute the cap on the training set only.

---

## 4. Final schema: `public_features_cleaned.csv`

| Column | Type | Notes |
|---|---|---|
| `zip` | string | Identifier and join key. **Never scale or use as a model feature** |
| `B01003_001E` | float | Mean-imputed, zeros replaced |
| `B07003_001E` | float | Mean-imputed, zeros replaced |
| `B07003_004E` | float | Mean-imputed, zeros replaced |
| `B07003_010E` | float | Mean-imputed. **Still has upper outliers** (not winsorized) |
| `B11016_001E` | float | Mean-imputed, zeros replaced |
| `B25003_002E` | float | Mean-imputed, zeros replaced |
| `B25003_003E` | float | Mean-imputed. **Still has upper outliers** (not winsorized) |
| `median_rent_usd` | float | **Still has upper outliers** (not winsorized) |
| `population` | numeric | Zeros replaced |
| `winsorized_zillow_home_value_index` | float | Capped at 95th percentile |
| `winsorized_zillow_rent_index` | float | Capped at 99th percentile |
| `winsorized_moved_different_house_pct` | float | Capped at 95th percentile |
| `winsorized_B25077_001E` | float | Median home value, capped at 95th percentile |
| `winsorized_B25064_001E` | float | Median gross rent, capped at 95th percentile |
| `winsorized_B07003_008E` | float | Moved within same county, capped at 95th percentile |

Run `print(list(public_features))` to confirm the exact column list after any change.

### The other three datasets

| Dataset | Dropped columns | Added / transformed |
|---|---|---|
| `area_features` | `area_name` | `rent_band` one-hot encoded (`rent_band_*`, 0/1 int) |
| `area_options` | `Disclaimer`, `option_id`, `summary` | `migration_score` (float, 0 to 1) and `median_rent` (int) extracted from `summary`. `rent_band`, `housing_preference`, `household` one-hot encoded. `tags` split into one binary `tag_<name>` column per tag |
| `crowd_text_snippets` | `Source`, `snippet_id`, `text` | `theme` one-hot encoded (`theme_*`, 0/1 int) |

Extraction rules for `area_options.summary`: the notebook searches for the labels "migration score" and "median rent" (case-insensitive) and reads the number after them. Anything not found becomes `0`.

---

## 5. Normalization (features used by the recommender)

> **Status: not yet applied in `cleaning.ipynb`

**Why it is needed:** the features have very different ranges. A distance, similarity or weighted score would be dominated by the largest-scale column.

| Feature | Approx. range |
|---|---|
| `winsorized_zillow_home_value_index` | 300,000 to 1,500,000 |
| `population`, `B01003_001E` | 0 to 70,000 |
| `B25003_002E` | 0 to 16,000 |
| `winsorized_zillow_rent_index` | 2,100 to 4,900 |
| `median_rent_usd` | 1,100 to 3,500 |
| `winsorized_moved_different_house_pct` | 0.05 to 0.26 |

---

## 6. Data-quality and schema checks

Checks that run in the notebook:

| Check | Where | Rule |
|---|---|---|
| No leftover sentinels | All 4 datasets | Count of `-666666666` / `-6666666666` is 0 (`assert`) |
| Valid ZIP | All 4 datasets | Every `zip` is non-null and exactly 5 digits (`assert`) |
| No duplicate column names | All 4 datasets | `assert` |
| `migration_score` dtype and range | `area_options` | Float, between 0 and 1 (`assert`) |
| `median_rent` dtype and range | `area_options` | Integer, 0 or greater (`assert`) |
| Winsorization counts | `miami_dade_public_features` | Exactly 1 / 4 / 4 rows capped for rent index / moved pct / B25077 (`assert`) |
| Audit tables | `miami_dade_public_features` | Mean-imputation audit, zero-replacement audit, zero-count distribution, skew before/after each cap |
| Distribution review | `miami_dade_public_features` | `describe()`, column profile (missing, zero, unique, skew, min, max, negative counts), histograms + boxplots |

Extra checks worth running before training:

```python
df = public_features
assert df['zip'].is_unique                              # one row per ZIP?
assert df.drop(columns='zip').isna().sum().sum() == 0   # no NaN left
assert (df.select_dtypes('number') == 0).sum().sum() == 0  # no zeros left (public_features)
```

---

## 7. Known issues and open items
1. **Normalization is not implemented yet**.
2. **Outliers still present** in `B07003_010E`, `B25003_003E` and `median_rent_usd` (visible as boxplot dots).
3. **Column names changed:** six columns were replaced by `winsorized_*` versions. Old code referencing the originals will break.