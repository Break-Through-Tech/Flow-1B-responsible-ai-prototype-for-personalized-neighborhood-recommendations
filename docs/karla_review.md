# Recommendation engine: review for Karla

October 28, 2026 · Om Patel · [PR #17](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/pull/17)

> **Current status (November 12):** with the advisor's 2026-realistic budgets and P3 update, the five original profiles score P@3 0.53, MRR 0.82, budget compliance 100% under neighborhood scoring (not directly comparable with the earlier ZIP-label scores; see "Comparing scores"). The independently generated held-out set scored P@3 0.23, MRR 0.55 once, before advisor review; co-living listings were added after that run.

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

**Comparing scores:** neighborhood scoring is easier to satisfy than the original ZIP labels. Coral Gables maps to 8 ZIPs, 4 ZIPs count for more than one neighborhood, and P4's relevant set grows to 9 ZIPs. Before/after numbers across the scoring change are not directly comparable; `zip_label_precision` keeps the original basis.

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
| **Test profiles:** score by neighborhood; one neighborhood spans several residential ZIPs | `eval/neighborhood_zips.json` holds the advisor's table; profiles gain `expected_neighborhoods`; `evaluate` counts a result as relevant when its ZIP is in an expected neighborhood, adds `neighborhood_coverage`, and keeps `zip_label_precision` for comparison. Downtown (not in the table) keeps 33128. No residential addresses are available, so shared ZIPs (33129, 33133, 33143, 33156) count for each listed neighborhood. | Done. Current engine (HUD rents, co-living listings): P@3 0.33, MRR 0.80; P4 still 0 at its $2,200 budget. |
| **Held-out set for review** | `eval/heldout_profiles_draft.json`: 8 profiles, expected neighborhoods written **before** running the engine. Not evaluated until the advisor approves them. A second set, `eval/heldout_profiles_generated.json` (10 profiles), was written by a separate model given only the profile format and the six neighborhood names, with no access to the engine, data or results. Its co-living profile (G6) also expects Downtown/Brickell, which conflicts with the listing rule. | Awaiting review |
| **"Quiet" = residential character** (quiet residential streets, suburban feel); noise is a separate measure | New `low_noise` tag (transportation noise). The first test of building-type candidates was invalid: at $2,200 P4 can afford no ZIP in its neighborhoods under HUD rents, so no definition could help. Rerun as a ranking-only comparison at a $3,300 development budget (P4 unchanged): **single-family-home share** reaches P@3 0.33 and ranks an expected ZIP 2nd (RR 0.50), versus 0.00 and 8th for noise (`experiments/feature_candidates/quiet_residential.py`). `quiet` still uses noise as a labeled stand-in; single-family share is the leading candidate, pending the advisor's sentiment source. Requesting `quiet` and `low_noise` together no longer counts noise twice. | Partial |
| **Rent:** 2026 asking rents by comparable unit size; flag profiles | Zillow Aug-2026 asking rents cover only 29 of 80 ZIPs and have no unit sizes. HUD rents cover all ZIPs by unit size but are benchmarks (vintage unstated), and Zillow is a median 17% higher. Budget flags at 2026 rents (living alone → 1-bedroom, co-leasers → 2-bedroom): **P4 ($2,200) has no affordable expected ZIP** (cheapest HUD 2-bedroom $2,510). P1, P2 and P3 keep only Wynwood 33127 and Downtown. At Zillow asking rents, no profile except P5 has an affordable expected ZIP. | **HUD adopted** (Nov 9). Census features now filter on HUD rent by unit size (`rents_hud.csv`). With neighborhood scoring: P@3 0.53 → 0.33, MRR 0.72 → 0.80, coverage@3 0.67 → 0.43, budget compliance 100%. Fewer ZIPs are affordable: P4 has 9 eligible ZIPs, none in its neighborhoods; Brickell drops out for P1–P3. Budgets need updating. |
| **Co-living:** listings with a private bedroom in a shared apartment; per-bedroom rent; count each property once | Curated `data/co_living_listings.csv`: one row per property with sources, date checked and confidence; co-living requests only consider ZIPs with a listed property and compare the budget with its per-bedroom rent. | **Implemented and expanded** (Nov 11): `data/co_living_listings.csv` now has 9 properties, with each address's ZIP checked by the Census geocoder: 6 buildings (Flow Wynwood, i5 Wynwood, AERIE and Otto in Downtown 33128, Plum, Aventura Coliving) and 3 shared houses (Ambitious Coliving in South Beach, The Coliving Co in Little Havana, a Fllat house in Coconut Grove). The Coliving Co's address comes from an AI summary and is not confirmed by a listing, so it is marked `low` confidence. Om widened the rule to include shared houses. P3 now gets Downtown first (P@3 0.33). No verified co-living exists in Brickell. Roomurs, PadSplit and Etico are pending addresses or prices. |

## Advisor answers (November 12) and actions

| Answer | Action |
|---|---|
| **Budgets:** nothing in Miami rents below about $2,500; set each profile's budget within the lowest-to-highest rents of its neighborhood group | Each original profile's budget is now the median 2026 rent for its unit size across its expected-neighborhood ZIPs (HUD; per-bedroom listing rent for co-living), rounded up to $100 and kept inside that range. P1 $2,500 → $3,000, P2 $2,000 → $2,500, P3 $1,800 → $1,300 (co-living rooms, $1,175–$1,750), P4 $2,200 → $3,000, P5 unchanged at $3,000. Each change is recorded in a `budget_note`. |
| **P3:** if no Brickell/Downtown roommate examples, adjust toward Wynwood | Downtown has verified co-living (AERIE, Otto) and Brickell has none, so P3 now expects **Downtown and Wynwood**. |
| **Held-out set:** include suburbs and why people move there; recommend beyond what users think they need | Kendall, West Kendall and Doral added to `eval/neighborhood_zips.json` (proposed ZIPs from Joana's area names plus the starter labels). Three suburb profiles (H9–H11) added to the draft, written before running the engine, each with a place-based reason people move there. A "you might also like" recommendation is the next feature. |
| **Data refresh:** approved, with Google or similar qualitative reviews | Monthly reviewed refresh is in scope. Google's terms prohibit scraping, and the Places API limits reviews and storage, so review text should come from permitted sources (e.g. the Kaggle reviews dataset named in the challenge brief) through Nadia's NLP. |

**Results with 2026-realistic budgets** (original five profiles, neighborhood scoring): P@3 0.53, P@5 0.32, MRR 0.82, coverage@3 0.67, budget compliance 100%. P1, P2, P3 and P5 each get 2 expected ZIPs in their top 3; P4 (quiet) still misses, pending a residential-character measure.

## Decisions made (November 11)

- **Rent:** budgets use HUD Small Area Fair Market Rents by unit size (1-bedroom solo, 2-bedroom co-leasers), because ZIP-level asking rents by bedroom are not publicly available. HUD runs low: Flow Wynwood studios start at $2,143 versus HUD's $1,570 studio benchmark for 33127.
- **Co-living:** any private room with shared living space counts, including shared houses. `data/co_living_listings.csv` lists 9 properties with Census-confirmed ZIPs: Wynwood (Flow Wynwood, i5 Wynwood), Downtown 33128 (AERIE, Otto), Overtown (Plum), Little Havana (The Coliving Co), Coconut Grove (a Fllat house), South Beach (Ambitious Coliving) and Aventura (Aventura Coliving). No verified co-living exists in Brickell. Roomurs (address unclear), PadSplit and Etico (no addresses) are pending.
- **Held-out sets:** two sets await your review and have not been scored for reporting: our draft (8 profiles) and an independently generated set (10 profiles, written by a separate model with no access to the engine or data).

## Final questions for Karla (November 11)

1. **Budgets at 2026 rents:** P4's $2,200 cannot afford any Coconut Grove, Coral Gables or Pinecrest two-bedroom (cheapest about $2,510), and P1-P3 lose Brickell. Should we raise these budgets, or retire the original five profiles in favor of a 2026 set?
2. **P3 (co-living):** Downtown now matches (AERIE and Otto in 33128), but no Brickell co-living listing could be verified. Should P3 still expect Brickell? Could you share the listing list you used, so we can compare with ours?
3. **"Quiet" (P4):** you based this on sentiment analysis of how people describe neighborhoods. Could you share that data or method? Building and density measures do not capture "quiet residential streets"; until then `quiet` uses transportation noise as a stand-in.
4. **Held-out sets:** could you review the expected neighborhoods in both sets before we score them? Should they include suburbs such as Kendall or Doral, and if so with which ZIPs?
5. **Data refresh:** is a monthly scheduled refresh from public sources (Zillow rent index, HUD, the transit schedule), reviewed before use, within the "public snapshots" rule?

## Run it

```powershell
.venv/Scripts/python.exe -m flow_neighborhoods --budget 2500 --household with_co_leaser --tags transit quiet --weight quiet=2 --near "Coconut Grove"
.venv/Scripts/python.exe -m flow_neighborhoods.evaluate                      # measured features (default)
.venv/Scripts/python.exe experiments/feature_candidates/compare.py           # starter vs measured, mean vs cosine
.venv/Scripts/python.exe experiments/feature_candidates/decisions.py         # include/exclude tests
.venv/Scripts/python.exe -m pytest -q                                        # 137 tests
```

Rebuilding the data files needs the raw Census downloads (URLs in `docs/HANDOFF.md`) and `experiments/feature_candidates/noise.py`, which caches about 3 MB of noise-map tiles and ZIP boundaries.
