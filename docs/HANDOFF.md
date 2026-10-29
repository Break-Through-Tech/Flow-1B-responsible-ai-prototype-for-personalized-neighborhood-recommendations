# Handoff: recommendation engine and feature work

Last updated: October 21, 2026. Owner: Om (`ompatel181005`). Written for an AI coding agent continuing this work; read it fully before changing anything.

## Note: authorship (October 28, 2026)

Per Om: everything in the repo's initial commit (`ac60486`, git author Hari Raghavan) was authored by the challenge advisor, Karla Reyes. That includes `data/` (`co_living_friendly`, `single_family_friendly`), `eval/` profiles and fixtures, and the docs. Treat the profiles' expected ZIPs as Karla's labels. Her public reference repo is incomplete and not the only source of truth.

## Update: October 28, 2026 (later)

Open choices were settled by include/exclude tests (`experiments/feature_candidates/decisions.py`, rule fixed in advance: adopt only if MRR +0.02 with no profile worse; ties go to the fairer, then simpler option). Results: transit = transit-commute share only (no-car dropped); social = restaurants+bars/sq mi; walkable = walk-to-work share; quiet = 1 - share of land >= 55 dB road/aviation noise (BTS 2020 tiles, `noise.py`); rent stays all-unit median; co_living_friendly kept; pet_friendly kept with warning. **`census` is now the default feature set** (`provided` kept for comparison). Defaults: P@3 0.53, P@5 0.32, MRR 0.72; P4 expected ZIPs 11/31/14. 55 tests. `docs/karla_review.md` rewritten. Caches `experiments/feature_candidates/{census,noise}/` are git-ignored.

## Update: October 28, 2026

Om decided: quiet = low population density + few bars/nightclubs (no family/household-composition data: familial status is fair-housing protected); co-leaser `budget_max` is the couple's total (decided Oct 28 after R1 fixture review; per-person rule reverted), with warning; noise data for quiet not provided — BTS noise raster is the only source (multi-GB, needs ZIP polygons), raised with Karla; users can prioritise tags (`weights`, 1-3); named neighborhoods supported via `near` and a separate alias dictionary; `area_name` untouched, `usps_city` added. Implemented locally on `Om`: `feature_set="census"` (opt-in; provided stays default), new data files `data/zcta_geography.csv`, `data/census_features.csv`, `data/neighborhood_aliases.csv` (built by `experiments/feature_candidates/build_data.py`; `data/zcta_land_area.csv` retired), 54 tests. Census features on the 5 profiles: P@3 0.53, P@5 0.32, MRR 0.70 (starter 0.13 / 0.16 / 0.32); P4 worsens. Review doc for the advisor: `docs/karla_review.md`; comparison: `experiments/feature_candidates/compare.py`. Pending Karla's answers (in that doc) before making census the default.

## Continuation update: October 21, 2026

Fetched origin and merged main (`fdd2c9a`) into local Om using merge commit `cd7ef78`. Om approved removal of the rejected density prototype. Its code and three prototype-only tests have been removed, restoring the runtime to main's provided-feature behavior. Commit `6b5b030`, the land-area CSV, the experiment files, and the diagnosis remain intact. No history was rewritten. This handoff and the experiment remain untracked. No push, PR, review submission, or GitHub comment was made.

Verified PR #16's merge and absence of formal reviews; PR #15 remains open at `d915eece`. Completed an offline review: 27 NLP tests pass, but targeted probes show unsupported quotes are published and mixed-source input loses its demo label. Findings are in `docs/nlp_pr15_review.md`. Proposed definitions/ownership are in `docs/feature_spec_proposal.md`; no new source or feature is approved. After cleanup, Om passes 40 tests and Ruff checks; the prior 43 included three removed density-only tests. Rerunning the candidate experiment reproduces rounded P@3 0.53, P@5 0.32, MRR 0.71 for the proposed configuration with provided quiet.

The branch-state table and priorities below describe the incoming snapshot. The merge and review above supersede those status observations; feature decisions remain open.

## 1. Status in one paragraph

The offline recommendation engine (`src/flow_neighborhoods/`) is built, tested and **merged to `main`** (PR #16, merged Oct 20 by DanielM7852, no formal reviews recorded). It filters ZIPs by budget, ranks them by the mean of the requested lifestyle features, explains each score, and attaches demo text evidence. Budget compliance is 100%, but relevance is low (Precision@3 = 0.13) because **the lifestyle features in the starter data are placeholders**, not measurements. An experiment with real Census data shows large gains (MRR 0.32 → ~0.72), but which features to adopt depends on decisions from the challenge advisor and team that are still open (section 8). The next build step is a real-data feature set; it is blocked on those answers.

## 2. Repository and branch state

| Item | State |
|---|---|
| `main` (`fdd2c9a`) | Contains the engine, 40 tests, evaluation runner, `docs/recommender_baseline.md` |
| Local branch `Om` | One **unpushed** commit on top of main's content: `6b5b030` "Add density feature set prototype". **Superseded** (see section 5, stage 4). Recommended: drop it, but keep `data/zcta_land_area.csv` (the experiment uses it). Ask Om before dropping or pushing. |
| `experiments/feature_candidates/` | **Untracked.** Real-data feature experiment: scripts plus filtered Census files. Reproducible (section 7). Not yet decided whether to commit. |
| PR #15 (Nadia, branch `NLP`) | Open, unreviewed: sentiment analysis and tagging, ~2,650 lines under `src/nlp/`. Will conflict with main on `.gitignore` and on layout: it adds `src/__init__.py` / `tests/__init__.py` (treats `src` as a package), while main uses `src` as the import root (`pythonpath = ["src"]` in `pyproject.toml`). |
| `outputs/` | Git-ignored. Evaluation reports go here. |

## 3. Project context you need

- **Goal:** a user enters budget, household, housing preference and lifestyle tags, and gets 3–5 Miami-Dade ZIP codes. Architecture: Python engine → MCP tools → LLM agent. **"Ranking happens in Python. The LLM narrates."** The LLM never ranks.
- **Hard rules** (Challenge-Project-Overview.md, PROJECT_PLAN.md):
  - The budget is a hard filter and is never relaxed.
  - No demographic steering (race, ethnicity, family status), and never infer relationship status.
  - Never score tenants.
  - Label synthetic listings as demos.
  - No live scraping; use public snapshots only.
- **Team:**
  - Anna (`annaryan-bos`): recommender, #8 and #11
  - Amelie (`Amelie1253`) and Joana (`Joanachoong`): data cleaning (#6, #7); Amelie also runs evaluation (#12)
  - Nadia (`nadiawoo`): NLP (#9)
  - Daniel (`DanielM7852`) and Azibator (`azibat0r`): MCP (#5, #10)
  - Challenge advisor: Karla Reyes, who designed the challenge and the reference app
- **Reference app:** https://github.com/karlarey/miami-newcomer-explorer. Its `scripts/build_features.py` generated our starter `area_features.csv` (section 6). Use it for structure (tools, MCP server, ethics charter), not for feature values. Clone with `git -c core.longpaths=true` on Windows.
- **Dates:** the plan uses Dec 15 as the submission date. The Oct 26–30 milestone is integrated alpha with MCP; Nov 9–13 is the full three-layer scorecard.

## 4. How the engine works (on `main`)

| File | Role |
|---|---|
| `contracts.py` | `Request.parse` validates `budget_max` (positive finite USD), `household` (`alone` / `with_co_leaser`), `housing_preference` (`own_apartment` / `co_living`), `tags` (transit, social, quiet, pet_friendly, walkable, co_living; normalized and de-duplicated), and `k` (1–5). Unknown keys are rejected. `clarification()` returns a question for empty tags, own_apartment combined with a co_living tag, or co_living with a co-leaser. |
| `data.py` | `load_snapshot` reads `area_features_cleaned.csv` (scores and rent), `area_features.csv` (names only) and `crowd_text_snippets.csv` (evidence with original IDs). It rejects duplicates, malformed rows and out-of-range values. Blank, nonfinite or nonpositive rent becomes `None`. It returns SHA-256 hashes of the files. |
| `engine.py` | `Recommender(data_dir, scorer="mean")`. `rank()` excludes ZIPs for missing rent, then over budget, then missing a *requested* feature (each counted once), scores the rest and sorts by score descending, then ZIP. `recommend()` builds the response: status (`ok` / `no_matches` / `needs_clarification`), results with per-feature `contributions`, exclusion counts, warnings and data hashes. `crowd_themes(zip)` returns demo evidence with `polarity: "unknown"`. |
| `evaluate.py` | Runs `eval/recommendation_profiles.json` and reports Precision@3/5, MRR over the full eligible ranking, budget pass rate and theme coverage, plus code, data and profile hashes. |
| `__main__.py` | CLI. |

**Scorers:**
- `mean` (default): average of the requested features; contributions sum to the score.
- `cosine`: the original baseline, kept for comparison.

**Behavior kept on purpose:**
- Household is recorded but has no effect on ranking.
- Co-living adds `co_living_friendly` to the score.
- Evidence never affects ranking.
- Warnings fire when a requested feature is constant across ZIPs (e.g. `pet_friendly`) and when all eligible ZIPs tie.

**Run from the repo root (Windows; use the venv, not the global python):**

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
.venv/Scripts/python.exe -m flow_neighborhoods --budget 2500 --household with_co_leaser --tags transit walkable --k 3
.venv/Scripts/python.exe -m flow_neighborhoods.evaluate --scorer mean    # writes outputs/recommender_mean.json
```

`tests/conftest.py` makes a fresh pytest temp dir per run; this is a fix for Windows ACL errors, so keep it.

## 5. What was done and decided, in order

| Stage | What happened | Decision and reason |
|---|---|---|
| 0. Baseline | Om built the loader, contracts, cosine ranker, evidence lookup, evaluation and 36 tests. P@3 0.13. | Budget is a hard filter, applied before scoring; unknown rent is excluded, never imputed; invalid input is distinct from no matches; ask rather than guess; household doesn't affect score (no data supports it); evidence only, with no sentiment claims; deterministic ties. |
| 1. Scorer fix | Cosine penalizes strengths the user didn't request: Downtown ranked 52nd for transit + walkable because it is also social and quiet. | Default changed to `mean`; cosine kept. Added MRR, the constant-feature warning and the all-tie warning. P@5 0.08 → 0.16, MRR 0.155 → 0.320; P@3 unchanged. |
| 2. PR #16 | Pushed and opened with 5 reviewers. Since merged. | — |
| 3. Feature diagnosis | Reverse-engineered the starter features (section 6). They encode ZIP population and rent. | Proven to be the main cause of low precision. |
| 4. Density prototype (local commit `6b5b030`) | `social` = `walkable` = density percentile, `quiet` = 1 − that. P@3 0.47, MRR 0.83. | **Rejected after review by Om:** social and quiet aren't opposites, and social and walkable aren't the same thing. A social + quiet request scored every ZIP exactly 0.5. The high score came from collapsing everything onto one "urban" axis that the 5 profiles happen to favor. |
| 5. Reframe | Agreed the right order: define each tag in user terms → find data that measures it → scale to 0–1 → rank → evaluate. The engine (rank/evaluate) is solid; the earlier steps were never done. | Ranking stays rule-based and explainable. ML belongs in NLP (Nadia). Learned ranking needs far more labels than 5 profiles. |
| 6. Real-data experiment | 720 feature combinations using Census data (section 7). | The provided features are the problem. The 5 profiles cannot choose between good real candidates, so choose on meaning and independence. |
| 7. Reference repo | Confirmed the origin of the features and found a walkable bug. | Use the repo for structure only. We deliberately differ: it relaxes the budget to the 5 cheapest ZIPs when nothing fits and assumes transit + walkable when no tags are given; we do neither. |

## 6. Key finding: what the starter features are

From `scripts/build_features.py` in the reference repo (the docstring calls them proxies "until NLP enriches tags"), verified against `data/miami_dade_public_features.csv`:

| Feature | Actual definition |
|---|---|
| `quiet` | `1 - minmax(population) * 0.5`. Exact for all 80 ZIPs. |
| `social` | `minmax(population)`, then forced to ≥ 0.80 for 9 "urban" ZIPs (33127, 33128, 33130, 33131, 33132, 33136, 33137, 33138, 33139). Hialeah (33012) scores highest. |
| `transit` | `minmax(1 / (rent + 1))` (cheap = "transit"), forced to ≥ 0.85 for the same 9 ZIPs |
| `walkable` | `minmax(rent)`, computed **before** the −666666666 Census missing code was removed, so every real ZIP ≈ 1.0 and only the 3 ZIPs with missing rent are 0. Effectively useless. |
| `pet_friendly` | 0.6 constant |
| `co_living_friendly`, `single_family_friendly` | Not produced by the reference script; origin undocumented. Ask Karla. |

## 7. Real-data experiment (`experiments/feature_candidates/`)

**Data** (filtered to the 80 Miami-Dade ZIP areas; full downloads were 15–90 MB each):
- ACS 2018–2022 5-year tables, bulk files from `https://www2.census.gov/programs-surveys/acs/summary_file/2022/table-based-SF/data/5YRData/acsdt5y2022-<table>.dat`:
  - B08301 (commute mode)
  - B08201 (vehicles available)
  - B25024 (units in structure)
- ZIP Code Business Patterns 2021: `https://www2.census.gov/programs-surveys/cbp/datasets/2021/zbp21detail.zip`. Establishment counts for NAICS 722 (restaurants and bars), 7224 (bars), 71 (arts/entertainment), 4451 (grocery), 446 (pharmacy).
- Land area: `data/zcta_land_area.csv`, from the 2023 Census Gazetteer. **Only present in local commit `6b5b030`**; keep this file if you drop that commit.
- The Census API now requires a free key (`missing_key` redirect), which is why bulk files were used.

**Rerun from the repo root:**

```powershell
.venv/Scripts/python.exe experiments/feature_candidates/features_experiment.py experiments/feature_candidates/census
.venv/Scripts/python.exe experiments/feature_candidates/pick.py experiments/feature_candidates/features_experiment.py experiments/feature_candidates/census
```

**Method.** Candidates were fixed before measuring. All are converted to a percentile among snapshot ZIPs, which overwrites the corresponding `area` values in memory. Tags are tested one at a time on the profiles that request them, then all combinations together. The script also reports correlations between candidates and checks that a social + quiet request does not tie.

**Results:**

| Configuration | P@3 | P@5 | MRR |
|---|---:|---:|---:|
| Cosine, provided features (original) | 0.133 | 0.080 | 0.155 |
| Mean, provided features (**main today**) | 0.133 | 0.160 | 0.320 |
| Mean, density for social/walkable/quiet (rejected) | 0.467 | 0.320 | 0.825 |
| Median of 720 real-data combinations | — | — | 0.70 |
| **Proposed:** transit = transit-commute share + no-car share (averaged); social = restaurants and bars per sq mi; walkable = walk-to-work share; quiet = provided (open) | 0.533 | 0.320 | 0.71 |
| Same, with quiet = owner-occupied share | 0.533 | 0.320 | 0.73 |

**Why these picks:**
- The top 5 for each pick looks right: transit → Downtown, Health District, Brickell, Wynwood, Allapattah; social → South Beach, Miami Beach, Brickell, Edgewater, Design District.
- They are reasonably independent. Grocery/pharmacy density was rejected for walkable because it correlates 0.90 with restaurant density, which would make walkable ≈ social again.
- Social + quiet now yields 72 distinct scores instead of a full tie.

**Limits:**
- Each tag is tested by only 1–3 profiles (quiet by 1). Many combinations tie at the top. Do not pick by score.
- P4 (quiet + pets) is never solved: its labels expect Coral Gables, Coconut Grove and Pinecrest.
- Wynwood stays ~11–14 for social/walkable profiles.
- ACS margins of error are large for small ZIPs; business counts use mailing ZIPs, not Census ZIP areas.
- **Responsible-AI concern:** owner-occupancy, single-family share and car ownership describe *residents* and correlate with income and demographics, which risks demographic steering. Prefer *place* measures: venues, transit service (GTFS), noise maps. Transit currently uses resident commute behavior; GTFS stop and service data would be better.

## 8. Open decisions (blocked; need Om, the advisor or the team)

1. What does `quiet` mean: low noise, low density, or settled residential? Is `pet_friendly` getting real data, or should the tag be dropped?
2. Are resident-based measures allowed under the no-steering rule, or only place-based ones?
3. Which data sources are approved (ACS, Business Patterns, Gazetteer, GTFS, noise maps)? Any licensing limits (e.g. Zillow terms)?
4. Who wrote the profile labels and how? Can we get more profiles, or write a held-out set? What Precision@3 target counts as good enough?
5. Is mean scoring acceptable instead of cosine? Issue #11 and ARCHITECTURE.md still say cosine.
6. Household: is the budget total or per person? Should household affect ranking? Is co-living with a co-leaser valid?
7. Should users be able to weight their priorities, or should named-neighborhood requests (e.g. "near Brickell") be supported?
8. Do the MCP contracts need to match the reference app's `mcp_server.py` and `tools.py`? Is a Streamlit app expected?
9. Who approves data-source changes: the advisor, or the data owners (Amelie and Joana)?

Om has the full list of 26 advisor questions from the session; ask him for it if needed.

## 9. Next steps, in priority order

1. **Branch cleanup completed with Om's approval.** Main was merged without rewriting history; density code was removed while preserving the land-area CSV, experiment, and diagnosis. The baseline guide now labels density results as historical/rejected. Cleanup changes are local and uncommitted.
2. **Review Nadia's PR #15.** Check the output against the `crowd_themes` contract: evidence IDs, `is_demo`, polarity. Check negation handling ("Not quiet at night." must not be positive evidence for quiet). Flag the `src/` layout and `.gitignore` conflicts with main. Report findings to Om; don't post comments without his approval.
3. **After decisions 1–3, build a `census` feature set.** Add `Recommender(feature_set="census")` (and `--features` in the CLI and evaluate). Load the extracted per-ZIP measures from small committed CSVs, with sources documented in `data_dictionary.md`. Leave unapproved tags on provided values with a warning. Add tests:
   - percentile scaling
   - missing inputs excluded only when the feature is requested
   - social + quiet doesn't tie
   - real-data profiles keep 100% budget compliance

   Keep `provided` as the default until the data owners adopt the features in their cleaning notebook.
4. **Write a short feature spec for the team:** each tag's user-facing definition, data source, owner and known bias risk. Use it to hand ownership to Amelie and Joana.
5. **MCP integration (#5, #10) with Daniel and Azibator:**
   - Wrap `recommend` and `crowd_themes`.
   - Map `ValidationError` / `DataError` / `needs_clarification` to tool responses.
   - Define the `schema`, `area_stats` and `ethics` tools.
6. **Evaluation:** get more independently labeled profiles (Amelie) before any further ranking changes. Don't tune weights to the 5 fixtures.
7. **Later:** a real transit feature from GTFS, a noise-based quiet feature, real area names (many are still `ZCTA5 xxxxx`), and polarity-aware NLP evidence.

## 10. Conventions and guardrails for the next agent

- **Commits:** a short subject plus at most a couple of body lines. **No `Co-Authored-By` or `Claude-Session` trailers** (Om's standing preference). Keep PR text short.
- **Ask Om before:** pushing, opening or merging PRs, commenting on GitHub, or deleting commits.
- **Run before claiming done:** `pytest`, `ruff check` and `ruff format --check`.
- **Evaluation:** never claim model quality from 5 profiles. Report all metrics, including regressions (e.g. P4).
- **Hard rules:** never relax the budget, impute rent, or let the LLM rank. Every response must say what its numbers are proxies for.
- **Prefer place-based features over resident-based ones** (fair-housing / steering risk).
- **Environment:** Windows with Git Bash and PowerShell. Long paths can break `git clone` (use `-c core.longpaths=true`). The repo venv is `.venv/Scripts/python.exe`.

## 11. File index

- `src/flow_neighborhoods/`: engine package
- `tests/test_recommender.py`, `tests/conftest.py`: tests
- `docs/recommender_baseline.md`: run guide, contract, data decisions, measured results
- `OM_RECOMMENDER_NLP_PLAN.md`: Om's original plan and the Oct 11 update
- `eval/recommendation_profiles.json`: the 5 labeled profiles
- `data/area_features_cleaned.csv`: what the engine ranks on; placeholder lifestyle scores
- `data/miami_dade_public_features.csv`, `data/public_features_cleaned.csv`: real ACS and Zillow-style public data
- `experiments/feature_candidates/`: real-data experiment (untracked)
- `ARCHITECTURE.md`, `EVAL_FRAMEWORK.md`, `Challenge-Project-Overview.md`, `PROJECT_PLAN.md`: project rules and targets
