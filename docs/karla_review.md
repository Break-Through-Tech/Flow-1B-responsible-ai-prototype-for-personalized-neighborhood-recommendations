# Recommendation engine: review for Karla

October 28, 2026 · Om Patel · Branch `Om` (local; not yet on GitHub)

## Summary

The engine on `main` filters ZIPs by budget and ranks them reliably, but its lifestyle scores were placeholders. `build_features.py` derives them from ZIP population and rent, which is why Precision@3 was 0.13. Today's changes add a proposed **census** feature set built from public Census measurements, plus three request features: **priorities**, **per-person budget for co-leasers**, and **"near" a named neighborhood**. On the five test profiles, the census features raise Precision@3 from 0.13 to 0.53 and MRR from 0.32 to 0.70. The starter features remain the default until you and the data owners approve the new ones.

## How the pipeline works

```
request ──► 1 validate ──► 2 clarify? ──► 3 budget filter ──► 4 score ──► 5 rank ──► 6 explain + evidence
                                           (hard, never relaxed)   (weighted mean of requested features)
```

**Example request:**

```json
{"budget_max": 1500, "household": "with_co_leaser", "housing_preference": "own_apartment",
 "tags": ["transit", "quiet"], "weights": {"transit": 3}, "near": ["Brickell"], "k": 3}
```

1. **Validate.** Reject bad types, unknown tags, k outside 1–5, priorities other than 1/2/3, and more than 3 `near` names. Invalid input is an error, which is distinct from "no matches".
2. **Clarify.** No tags, own apartment combined with a co-living tag, or co-living with a co-leaser → `needs_clarification` instead of guessing.
3. **Budget filter.** With a co-leaser, `budget_max` is each person's share, so the combined budget is $1,500 × 2 = $3,000. ZIPs are excluded for unknown rent (never estimated), rent over the combined budget, or a missing value for a requested feature. Every exclusion is counted.
4. **Score.** A weighted mean of the requested features, each a 0–1 percentile among Miami-Dade ZIPs. With transit at priority 3 and quiet at 1, transit counts three times as much. `near` adds a closeness score: 1 at the named neighborhood, falling with distance between ZIP centers.
5. **Rank.** Sort by score, with ties broken by ZIP, so the same input always gives the same output.
6. **Explain.** Each result carries its rent, score, per-feature contributions with their priority, raw measurements (e.g. bars per sq mi), distance to the named neighborhood, USPS city, and demo text evidence. The response also lists warnings, exclusion counts and data-file hashes.

The LLM agent only narrates this output; it never ranks.

## What each lifestyle tag measures

| Tag | Starter value (`build_features.py`) | Proposed census measure | Source |
|---|---|---|---|
| transit | `minmax(1/rent)`; 9 ZIPs forced to ≥ 0.85 | Average of the transit-commuter share and the no-car household share | ACS 2018–22 B08301, B08201 |
| social | `minmax(population)`; 9 ZIPs forced to ≥ 0.80 | Restaurants and bars per sq mi | ZIP Business Patterns 2021 (NAICS 722) |
| walkable | `minmax(rent)` computed before the −666666666 code was removed, so ≈ 1.0 everywhere | Walk-to-work share | ACS 2018–22 B08301 |
| quiet | `1 − minmax(population)/2` | Average of (1 − population density) and (1 − bars and nightclubs per sq mi) | ACS, Gazetteer land area, ZBP (NAICS 7224) |
| pet_friendly | 0.6 for every ZIP | Unchanged; warns that it cannot distinguish areas | — |
| co_living | Provenance unknown | Unchanged | — |

## Results on the five profiles

| Features | Budget rule | P@3 | P@5 | MRR |
|---|---|---:|---:|---:|
| Starter | household total (old) | 0.13 | 0.16 | 0.32 |
| Starter | per-person share (new) | 0.13 | 0.16 | 0.32 |
| **Census** | household total | 0.53 | 0.32 | 0.70 |
| **Census** | per-person share | **0.53** | **0.32** | **0.70** |

- P1, P2, P3 and P5 each reach 2 of 3 expected ZIPs in the top 3.
- **P4 (quiet + pets) gets worse.** Its expected ZIPs (Coconut Grove, Coral Gables, Pinecrest) rank in the 50s–60s. Low density plus few bars ranks quieter outer areas first, and pet_friendly carries no information.
- The per-person budget didn't change precision, but co-leaser profiles now see more and pricier ZIPs.
- **With `near: ["Brickell"]`,** P5 returns Brickell (0 mi), Downtown (0.6 mi) and Health District (1.3 mi).
- **Priorities work as expected.** For transit + quiet at $1,800, putting transit at priority 3 surfaces Health District and Downtown; putting quiet at priority 3 surfaces outer ZIPs.
- **Caveat:** five team-written profiles cannot show generalization. Each tag is tested by only 1–3 profiles.

## Decisions made today

| Topic | Decision |
|---|---|
| Quiet | Low density plus few bars and nightclubs. Family-related data was **not** used: familial status is protected under fair housing, and the project rules forbid steering by family status. |
| Household budget | A co-leaser enters their own share; the engine assumes an even split with one co-leaser and warns that median rent covers all unit sizes. |
| Priorities | Each tag gets 1 (nice to have), 2 (important) or 3 (top priority). |
| Named neighborhoods | Supported through a separate dictionary (`data/neighborhood_aliases.csv`): your starter labels plus USPS city names. A name covering more than 10 ZIPs (e.g. "Miami") is rejected as too broad, and typos get a suggestion. |
| Area names | `area_name` is unchanged. A new `usps_city` field comes from `data/zcta_geography.csv`. |
| Default features | Starter features stay the default; census is opt-in until approved. |

## Questions for you

1. Were the `build_features.py` lifestyle scores meant to be replaced? Is the census feature set the right direction?
2. Are these sources approved: ACS commute and vehicle tables, ZIP Business Patterns, the Census Gazetteer? Any licensing limits?
3. **Steering:** transit and walkable use residents' commute behavior and car ownership. Is that acceptable, or should we move to place-based data (GTFS transit service, a walkability index)?
4. **Quiet:** P4's labels expect affluent residential areas. Is low density plus low nightlife right, or should it be noise data?
5. Who wrote the expected ZIPs in the five profiles? Can we get more profiles, or write a held-out set?
6. Is there a Precision@3 target for the final scorecard?
7. Is the mean scorer acceptable instead of cosine? Issue #11 and ARCHITECTURE.md say cosine; cosine is kept for comparison.
8. Where did `co_living_friendly` and `single_family_friendly` come from?
9. **pet_friendly:** is there a data source you intended, or should we drop the tag?
10. **Co-leaser budget:** is per-person share with an even split the right reading? Should co-leasers use 2-bedroom rents?
11. Should the MCP tools follow your `mcp_server.py` / `tools.py` contracts? Is a Streamlit demo expected?

## Run it

```powershell
.venv/Scripts/python.exe -m flow_neighborhoods --features census --budget 1500 --household with_co_leaser --tags transit quiet --weight transit=3 --near Brickell
.venv/Scripts/python.exe experiments/feature_candidates/compare.py
.venv/Scripts/python.exe -m pytest -q   # 54 tests
```
