# Starter Dataset

See [`data_dictionary.md`](../data_dictionary.md) for column details.

## Who this is for

Newcomers to Miami — e.g. moving from NYC with a **co-leaser** on a private lease, wanting **your own apartment** in Wynwood, Downtown, or Brickell. **Not a co-living facility.**

Co-living is an **optional** path for people who are **alone** and **want** shared/stranger roommate housing.

## User inputs (what the recommender uses)

| Field | Values | Example |
|-------|--------|---------|
| `household` | `alone`, `with_co_leaser` | `with_co_leaser` |
| `housing_preference` | `own_apartment`, `co_living` | `own_apartment` |
| Budget + lifestyle tags | transit, social, quiet, etc. | transit, walkable |

## Anchor neighborhoods (own apartment)

| Neighborhood | ZIP |
|--------------|-----|
| Wynwood | 33127 |
| Downtown Miami | 33128 |
| Brickell | 33130 |

## Files

| File | What's inside |
|------|-----------------|
| `area_features.csv` | ZIP-level scores for the model |
| `area_options.csv` | Demo cards with `housing_preference` + `household` |
| `crowd_text_snippets.csv` | Sample review text by ZIP |

All listing-style rows are **synthetic demos** — not real apartments.
