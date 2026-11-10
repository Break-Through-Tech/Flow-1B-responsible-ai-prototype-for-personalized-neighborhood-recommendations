# Recommendation engine: review for Karla

October 28, 2026 · Om Patel · [PR #17](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/pull/17)

## Summary

The lifestyle scores that shipped with the challenge data were placeholders. `build_features.py` derives them from ZIP population and rent, which is why Precision@3 was 0.13. The engine now ranks on **measured** data by default:

- transit: transit commuting
- social: restaurant and bar density
- walkable: walking to work
- quiet: modeled road and aviation noise

It also supports **priorities**, a clear **household budget** rule, and **"near" a named neighborhood**. On the five test profiles, Precision@3 rises from 0.13 to 0.53 and MRR from 0.32 to 0.72, with 100% budget compliance. Each open choice was settled by an include/exclude test under a fixed rule (see "How decisions were made").

## How the pipeline works

```
request ──► 1 validate ──► 2 clarify? ──► 3 budget filter ──► 4 score ──► 5 rank ──► 6 explain + evidence
                                           (hard, never relaxed)   (weighted mean of requested features)
```

**Example request:**

```json
{"budget_max": 2500, "household": "with_co_leaser", "housing_preference": "own_apartment",
 "tags": ["transit", "quiet"], "weights": {"quiet": 2}, "near": ["Coconut Grove"], "k": 3}
```

1. **Validate.** Reject bad types, unknown tags, k outside 1–5, priorities other than 1/2/3, and more than 3 `near` names. Invalid input is an error, which is distinct from "no matches".
2. **Clarify.** No tags, own apartment combined with a co-living tag, or co-living with a co-leaser → `needs_clarification` instead of guessing.
3. **Budget filter.** `budget_max` is the household's total monthly rent; with a co-leaser it covers both people, and the response says so. ZIPs are excluded for unknown rent (never estimated), rent over budget, or a missing value for a requested feature. Every exclusion is counted.
4. **Score.** A weighted mean of the requested features, each a 0–1 percentile among Miami-Dade ZIPs. Here quiet (priority 2) counts twice as much as transit. `near` adds a closeness score: 1 at the named neighborhood, falling with distance between ZIP centers.
5. **Rank.** Sort by score, with ties broken by ZIP, so the same input always gives the same output.
6. **Explain.** Each result carries its rent, score, per-feature contributions with their priority, raw measurements (e.g. share of land above 55 dB), distance to the named neighborhood, USPS city, and demo text evidence. The response also lists warnings, exclusion counts and data-file hashes.

The LLM agent only narrates this output; it never ranks.

## What each lifestyle tag measures

| Tag | Starter value (`build_features.py`) | Measure used now (default) | Source |
|---|---|---|---|
| transit | `minmax(1/rent)`; 9 ZIPs forced to ≥ 0.85 | Share of workers commuting by public transit | ACS 2018–22 B08301 |
| social | `minmax(population)`; 9 ZIPs forced to ≥ 0.80 | Restaurants and bars per sq mi | ZIP Business Patterns 2021 (NAICS 722) |
| walkable | `minmax(rent)` computed before the −666666666 code was removed, so ≈ 1.0 everywhere | Share of workers who walk to work | ACS 2018–22 B08301 |
| quiet | `1 − minmax(population)/2` | 1 − share of land with ≥ 55 dB road or aviation noise | BTS National Transportation Noise Map 2020 (24-hour LAeq), averaged within Census 2020 ZCTA boundaries |
| pet_friendly | 0.6 for every ZIP | Unchanged; warns that it cannot distinguish areas | — |
| co_living | Shipped with the challenge data | Unchanged (kept as provided) | — |

The starter features stay available with `feature_set="provided"` for comparison.

## Results on the five profiles

| Features | Scorer | P@3 | P@5 | MRR |
|---|---|---:|---:|---:|
| Starter | cosine (original) | 0.13 | 0.08 | 0.15 |
| Starter | mean | 0.13 | 0.16 | 0.32 |
| Measured | cosine | 0.07 | 0.08 | 0.19 |
| **Measured (default)** | **mean** | **0.53** | **0.32** | **0.72** |

- **Four profiles improve.** P1, P2, P3 and P5 each get 2 of their expected ZIPs into the top 3 (Downtown and Brickell).
- **P4 (quiet + pets) still misses its top 3,** but its expected ZIPs moved from 26th–37th (starter data) to **11th, 31st and 14th**. The ZIPs above them (Homestead area, West Kendall) genuinely have less road and air noise. pet_friendly carries no information.
- **Cosine gets worse with better data.** It rewards an area whose overall profile has the same *shape* as the request, so for a transit-only request its ideal area is strong on transit and weak on everything else.
- **Noise fixes a real error.** Under the density + nightlife definition, ZIP 33122, next to Miami International Airport, ranked among the 5 quietest, even though 76% of its land is above 55 dB.
- **Caveat:** five team-written profiles cannot show generalization. Each tag is tested by only 1–3 profiles.

## How decisions were made

Each open choice was tested with and without the change (`experiments/feature_candidates/decisions.py`). The rule was fixed before running: **adopt a change only if MRR rises ≥ 0.02 and no profile gets worse. Otherwise it's a tie, broken by the fairer option (no resident-demographic proxies), then the simpler one.**

| Choice | Tested | MRR change | Outcome |
|---|---|---:|---|
| transit | Commute share alone vs. + households without a car | 0 | Tie → **commute only** (car ownership tracks income) |
| social | Restaurants and bars vs. + arts venues | 0 | Tie → **restaurants and bars** (simpler) |
| walkable | Walk to work vs. + grocery/pharmacy density | 0 | Tie → **walk to work** (simpler; grocery density repeats social, r = 0.90) |
| quiet | Density + nightlife vs. noise | +0.014 | Tie → **noise**: one direct measure, and it fixes the airport error |
| rent | All-unit median vs. 2-bedroom for co-leasers (± 1-bedroom alone) | 0 | Tie → **all-unit median** (simpler; 2-bedroom would exclude 3 more ZIPs) |
| co_living_friendly | Keep vs. drop | 0 | Tie → **keep as provided**. P3 succeeds without it, so its success is not built in. |
| pet_friendly | Keep vs. drop | 0 | Tie → **keep with warning** (it is constant, so it cannot reorder results) |
| scorer | Mean vs. cosine | +0.53 | **Mean** |
| default | Measured vs. starter features | +0.40 | **Measured (census) is now the default** |

## Other decisions

| Topic | Decision |
|---|---|
| Household budget | `budget_max` is the couple's **total**, matching routing fixture R1 ("We're moving… with a co-leaser… Budget $2500"). The response warns that median rent covers all unit sizes. |
| Priorities | Each tag gets 1 (nice to have), 2 (important) or 3 (top priority). |
| Named neighborhoods | Supported through a separate dictionary (`data/neighborhood_aliases.csv`): your starter labels plus USPS city names. A name covering more than 10 ZIPs (e.g. "Miami") is rejected as too broad, and typos get a suggestion. |
| Area names | `area_name` is unchanged. A new `usps_city` field comes from `data/zcta_geography.csv`. |
| Family data | Not used anywhere. Familial status is fair-housing protected, and `single_family_friendly` stays unused for that reason. |
| Starter data | Everything in the repo's initial commit (data, test profiles, fixtures) is yours. Your public reference repo is not treated as the complete source, so columns it doesn't produce (e.g. `co_living_friendly`) are kept as provided. |
| P4 labels | Your expected answers are left unchanged and P4 is reported as a known miss; editing them to fit the engine would be circular. |

## Joana's new data (November 4)

Joana's branch adds ZIP names, GTFS transit service and rent benchmarks. Each was tested with the same rule (`experiments/feature_candidates/joana_decisions.py`):

| Data | Result | Decision |
|---|---|---|
| **Area names** (USPS + Census ZCTA-to-Place) | Rankings unchanged | **Adopted.** Results gain `neighborhood` and `other_areas`; `area_name` is unchanged. All 24 "ZCTA5 xxxxx" ZIPs are now named, and `near` understands Brickell Key, Overtown, Florida City, Redland and others. |
| **Transit service** (GTFS stops, routes, departures, headways) | As the transit score: MRR 0.72 → 0.44–0.62, with P5 worse in every variant | **Shown, not ranked.** Each result gains `transit_service` (e.g. Brickell: 28 routes, Metrorail and Metromover, bus every 16 min). |
| **HUD rent benchmarks** by unit size | MRR 0.80, but P@3 0.53 → 0.33 and P4 fails; eligible ZIPs drop from 65 to 9 for P4 | **Not adopted; needs your input** (question 5) |
| **Zillow rent, August 2026** | Real values for only 29 of 80 ZIPs; the cleaned file fills the other 51 with the median | **Not usable** for the budget filter, which never uses estimated rents |

Two data-quality points:

- The starter label for **33131 is "South Beach"**, but 33131 is Brickell / Brickell Key (South Beach is 33139). 28 ZIPs differ between the starter labels and the sourced names.
- **Our rents look out of date.** The engine filters on the ACS 2018–22 median gross rent. Downtown is $1,191 there, versus a HUD 1-bedroom benchmark of $1,750 and an August 2026 Zillow rent of $2,799. Some recommendations may be unaffordable in practice.

## Advisor feedback (November 9) and actions

| Feedback | Action | Status |
|---|---|---|
| **Test profiles:** score by neighborhood; one neighborhood spans several residential ZIPs | `eval/neighborhood_zips.json` holds the advisor's table; profiles gain `expected_neighborhoods`; `evaluate` counts a result as relevant when its ZIP is in an expected neighborhood, adds `neighborhood_coverage`, and keeps `zip_label_precision` for comparison. Downtown (not in the table) keeps 33128. No residential addresses are available, so shared ZIPs (33129, 33133, 33143, 33156) count for each listed neighborhood. | Done. Current engine: P@3 0.53, coverage@3 0.67; P4 still 0. |
| **Held-out set for review** | `eval/heldout_profiles_draft.json`: 8 profiles, expected neighborhoods written **before** running the engine. Not evaluated until the advisor approves them. | Awaiting review |
| **"Quiet" = residential character** (quiet residential streets, suburban feel); noise is a separate measure | New `low_noise` tag (transportation noise). Building-type candidates (single-unit share, low-rise share) were tested and did not move P4's matches (`experiments/feature_candidates/quiet_residential.py`). `quiet` uses the noise measure as a labeled stand-in until a residential-character signal exists; candidates are review-text sentiment (Nadia's NLP) or tree canopy cover. | Partial |
| **Rent:** 2026 asking rents by comparable unit size; flag profiles | Zillow Aug-2026 asking rents cover only 29 of 80 ZIPs and have no unit sizes. HUD rents cover all ZIPs by unit size but are benchmarks (vintage unstated), and Zillow is a median 17% higher. Budget flags at 2026 rents (living alone → 1-bedroom, co-leasers → 2-bedroom): **P4 ($2,200) has no affordable expected ZIP** (cheapest HUD 2-bedroom $2,510). P1, P2 and P3 keep only Wynwood 33127 and Downtown. At Zillow asking rents, no profile except P5 has an affordable expected ZIP. | **HUD adopted** (Nov 9). Census features now filter on HUD rent by unit size (`rents_hud.csv`). With neighborhood scoring: P@3 0.53 → 0.33, MRR 0.72 → 0.80, coverage@3 0.67 → 0.43, budget compliance 100%. Fewer ZIPs are affordable: P4 has 9 eligible ZIPs, none in its neighborhoods; Brickell drops out for P1–P3. Budgets need updating. |
| **Co-living:** listings with a private bedroom in a shared apartment; per-bedroom rent; count each property once | Flow Wynwood and i5 Wynwood, both 33127. i5 per-bedroom is about $1,299–$1,626 across listing sites; Flow Wynwood publishes no per-bedroom price. Only Wynwood qualifies, but P3 (co-living) expects Downtown/Brickell. | Data gap; P3 conflict |

## Questions for you

1. **Test profiles:** how did you choose the expected ZIPs (local knowledge, data, or both)? Could you write more, including suburban and conflicting-priority cases, or should we write a held-out set that you review? Each tag is currently tested by only 1–3 profiles.
2. **P4 (quiet + pets):** what did "quiet" mean when you chose Coconut Grove, Coral Gables and Pinecrest: low noise, or settled residential with greenery? With noise data they rank 11th, 31st and 14th, behind quieter outer ZIPs.
3. **`co_living_friendly`:** how did you build it? It ranks your three anchor ZIPs highest (Wynwood 0.92, Brickell 0.90, Downtown 0.88), and 18 ZIPs share exactly 0.55 or 0.15. P3 passes even without it, so it isn't inflating results, but we'd like to document its source. Same question for `single_family_friendly` (unused, because of the familial-status risk).
4. Is a Streamlit demo expected for the final presentation?
5. **Rent basis:** the budget filter uses ACS 2018–22 median rent, which is far below 2026 rents. Should we switch to HUD benchmarks by unit size? The profiles' budgets seem to assume the older rents: P4 would have only 9 affordable ZIPs left.

## Run it

```powershell
.venv/Scripts/python.exe -m flow_neighborhoods --budget 2500 --household with_co_leaser --tags transit quiet --weight quiet=2 --near "Coconut Grove"
.venv/Scripts/python.exe -m flow_neighborhoods.evaluate                      # measured features (default)
.venv/Scripts/python.exe experiments/feature_candidates/compare.py           # starter vs measured, mean vs cosine
.venv/Scripts/python.exe experiments/feature_candidates/decisions.py         # include/exclude tests
.venv/Scripts/python.exe -m pytest -q                                        # 55 tests
```

Rebuilding the data files needs the raw Census downloads (URLs in `docs/HANDOFF.md`) and `experiments/feature_candidates/noise.py`, which caches about 3 MB of noise-map tiles and ZIP boundaries.
