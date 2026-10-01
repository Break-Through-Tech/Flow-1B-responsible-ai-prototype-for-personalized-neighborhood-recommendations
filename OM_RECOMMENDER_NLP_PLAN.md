# Om's recommendation engine and NLP collaboration plan

Prepared September 30, 2026. This is an implementation plan, not a report of completed engine work. Dates below are proposed work targets; the existing team plan uses December 15 as a provisional submission date.

## Verified GitHub assignments

Checked September 30, 2026 against all 12 items on the [Flow 1B Project Board](https://github.com/orgs/Break-Through-Tech/projects/185), including draft-item lookup. Five open issues are assigned to ompatel181005. These verified assignments take precedence over the proposed task ownership later in this document. Statuses are a snapshot; no GitHub items were changed.

| Issue | Board status | Co-assignees | Required deliverable |
|---|---|---|---|
| [#5: Recommender and MCP interfaces](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/5) | In progress | Anna, Daniel, Azibator | Recommender input/output format and JSON contracts for all five MCP tools |
| [#8: Preference vector and budget filter](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/8) | Ready | Anna | Map user inputs to preferences; define the hard budget filter and no-match behavior |
| [#9: Initial theme lookup](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/9) | Ready | Nadia | Lookup over demo snippets with initial theme categories mapped to ZIPs |
| [#10: recommend MCP stub](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/10) | Backlog | Daniel, Azibator | Callable recommend tool returning a stub payload that validates the proposed interface |
| [#11: Baseline cosine recommender](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/11) | Backlog | Anna | Budget filtering before deterministic top-3/top-5 ranking; invalid budget, unsupported tag, and no-match tests |

**Additional support:** [#12: Baseline scorecard](https://github.com/Break-Through-Tech/Flow-1B-responsible-ai-prototype-for-personalized-neighborhood-recommendations/issues/12) is assigned to Amelie and in Backlog. Its description explicitly names Nadia and Om as supporting theme-coverage measurements. Supply ranked outputs and theme evidence for per-profile and overall metrics.

**Completed shared assignments:** #1 (read docs/data), #2 (clone/branch/PR process), and #3 (real versus demo data) are assigned to you along with the team and marked Done/closed. This reports board status, not an independent acceptance audit.

**Dependencies:** #6 (loading/cleaning) and #7 (normalization/quality checks) are assigned to Amelie and Joana and are both In review. Coordinate the prepared-data contract with them before connecting #11. The retrieved board fields have no populated task dates, so the dates later in this plan remain proposed targets.

**Recommended order:** finish #5 and define #8 together; progress #9 with Nadia; validate #10 after the interface is agreed; connect #11 after the data handoff; support #12 once rankings and theme lookup run. The plan's REC-01 maps to #5, REC-02/03 to #8/#11, NLP-01 to #9, and EVAL-01 to #12. Add #10 as an explicit early stub milestone; the later INT-01 real-engine integration does not replace it. #5 also requires contracts for schema, area_stats, crowd_themes, and ethics, beyond this document's detailed recommend proposal.

## 1. Understand the project through one request

A user says: "We are moving together, want our own apartment, have a total monthly budget of $2,500, and care about transit and walkability."

The system turns that into a structured request, removes ZIPs whose known rent estimate exceeds the budget, scores the remaining ZIPs against the selected preferences, and returns up to five results. NLP adds evidence about what the available text says. MCP exposes these functions to the agent. The agent explains the returned results and the interface displays them.

```text
Structured preferences --> validate --> filter by budget --> Python ranking
                                                              |
Review text --> theme extraction --> ZIP evidence -------------+
                                                              |
                                                  structured tool response
                                                              |
                                                     agent explanation
                                                              |
                                                      Streamlit display
```

For example, the inspected cleaned snapshot has median_rent_usd=1283 for 33127, 1191 for 33128, and 1553 for 33130. These pass the example's $2,500 proxy-budget filter. Their final order still depends on scoring all eligible ZIPs. These values are dataset estimates, not current apartment prices or proof that a unit is available.

### Where each part fits

| Part | What it produces | How it connects to your work | Existing project sources |
|---|---|---|---|
| Data cleaning | Consistent ZIPs, numeric fields, missing-value decisions | Your engine consumes the prepared table | data_dictionary.md; cleaning work on joana |
| Recommendation engine | Ranked ZIPs, scores, reasons, limitations | Your main deliverable with Anna | ARCHITECTURE.md; eval/recommendation_profiles.json |
| NLP | Themes and supporting text grouped by ZIP | You and Nadia define the evidence returned with results | data/crowd_text_snippets.csv |
| MCP | Five callable tools with JSON inputs and outputs | recommend calls your engine; crowd_themes calls NLP | MCP_SETUP.md |
| Agent | Interprets requests and explains tool results | Needs clear output fields and honest empty states | ARCHITECTURE.md |
| Streamlit | Input form and result display | Uses your status, warnings, and result fields | README.md |
| Evaluation | Reproducible rankings and quality reports | Shows whether your changes help | EVAL_FRAMEWORK.md; eval/ |

The five tools are schema, recommend, area_stats, crowd_themes, and ethics. Python owns the ranking. The language model explains returned evidence. Your MVP is a content-based recommender: it compares user preferences with area attributes. The repository does not yet provide user interaction histories needed for a collaborative-filtering approach.

## 2. Verified repository state

Inspected local files, fetched remote branches, read the cleaning notebook code and saved outputs. The notebook was not executed during this planning pass.

| Branch at inspection | Commit | Observed work |
|---|---|---|
| Local main, now the base of Om | e1d1258 | Starter repository plus PROJECT_PLAN.md |
| origin/main | ac60486 | Starter repository |
| origin/amelie | b9ec276 | Cleaning notebook; commit describes handling suppressed values |
| origin/joana | c4bb320 | Extended cleaning notebook, four cleaned CSVs, data/cleaned_data.md |

Git confirms amelie is an ancestor of joana, so joana already includes that cleaning history. Neither inspected remote branch contains the recommendation engine or an NLP implementation. The existing five recommendation profiles are fixtures, not measured results.

Created and switched to local branch **Om** from the existing local main. Teammate changes have been inspected but not merged. The existing .gitignore modification is preserved. No branch has been pushed and no implementation has been claimed complete.

### Important findings from joana

- area_features_cleaned.csv has 80 rows. Rent is missing for 33101, 33109, and 33039; sentinel replacement alone does not resolve these cases.
- public_features_cleaned.csv has 78 rows. A join can change coverage; measure unmatched ZIPs before deciding which table controls eligibility.
- crowd_text_snippets_cleaned.csv has 20 rows across 11 ZIPs. It keeps ZIP and theme indicators but drops text, source, and snippet_id. It cannot supply attributable quotations by itself.
- area_features_cleaned.csv drops area_name. Preserve a validated ZIP-to-display-name lookup from the original table.
- area_options_cleaned.csv drops option_id, summary, and disclaimer. Preserve original metadata if demo cards are displayed.
- The notebook extracts median_rent and migration_score from synthetic option summaries, substituting zero when extraction fails. These are not an authoritative rent source for the engine.
- The notebook replaces remaining public-feature zeros with column means and caps several high values. Review the meaning of zeros column by column with the data owners. Keep uncapped monetary estimates separate from transformed model features.
- Normalization is explicitly unfinished. The core lifestyle columns are already documented as 0-1 proxies; validate them rather than blindly scaling every numeric field.
- The CSV contains single_family_friendly although the original dictionary omits it. Keep it outside the initial feature contract pending a documented use case.
- A source value such as kaggle_reviews in the starter text does not establish authentic review provenance. The repository identifies these snippets as demo text.

## 3. Scope and team handoffs

The existing plan names Anna and Om for recommendations, Nadia and Om for NLP, Amelie and Joana for data, and Om/Daniel/Azibator for MCP. Proposed task ownership below should be agreed at the next team meeting.

| Owner | Deliverable | Handoff / review |
|---|---|---|
| Om | Recommendation contract, filter/ranker implementation, evidence adapter | Anna reviews ranking; MCP team reviews JSON |
| Anna | Feature mapping, alternative baseline, weight/error analysis | Om reviews integration |
| Nadia | Text preprocessing, theme taxonomy, extraction and annotation | Om reviews ZIP joins and output schema |
| Amelie / Joana | Prepared loader, rent provenance, missingness and metadata preservation | Om validates downstream assumptions |
| Amelie | Independent relevance labels, evaluation runner and scorecard coordination | Om supplies deterministic engine interface |
| Daniel / Azibator | MCP wrappers and routing integration | Om reviews recommend and crowd_themes |

Prioritize a working engine and NLP handoff. Give the MCP wrappers a separate directly responsible owner so all three lanes do not wait on Om.

### Integration sequence

1. Review the cleaned data contract with Amelie and Joana using the findings above.
2. Before implementation, bring the agreed cleaning changes into Om through a reviewed merge of joana or the team's eventual main merge. Do not copy competing versions of the notebook into the engine.
3. Preserve the existing .gitignore work separately when preparing commits. Check the working tree before merging; protect unrelated changes if a merge would overlap them.
4. Add a small adapter around the team's loader. Keep data cleaning in the data lane and scoring in the engine lane.
5. Use one PR per coherent deliverable: contract/adapter, baseline engine, evaluation, NLP evidence, and integration. Record the source data commit in each run.

## 4. Proposed data and API contracts

### Prepared area table

One unique row per five-character ZIP. Required: zip, median_rent_usd, transit, social, quiet, pet_friendly, walkable, co_living_friendly. Display metadata and quality fields should include area_name, rent_source, source_period, rent_is_imputed, data_version, and feature provenance where available. Unknown provenance stays explicitly unknown.

Rules:

- Read ZIPs as strings. Reject invalid/duplicate area keys with a useful error.
- Rent must be finite and positive to pass the initial affordability filter. Missing or imputed rent is excluded by default until the data team agrees an explicit policy; report exclusions.
- Keep budget rent in original dollar units. Do not use capped/scaled rent, rent-band lower bounds, or a synthetic card's parsed rent for affordability.
- Validate preference features as finite values in [0,1]. Do not silently replace a missing preference with a high score. Initial policy: exclude rows missing any active scoring dimension and report counts.
- Join display names one-to-one by ZIP. Aggregate many text records per ZIP before attaching evidence so joins cannot duplicate recommendations.
- Keep public demographic counts and migration_score outside the initial scoring vector. They are not direct measurements of the user's requested transit, quiet, or walkability preferences.

### Recommendation request

```json
{
  "budget_max": 2500,
  "household": "with_co_leaser",
  "housing_preference": "own_apartment",
  "tags": ["transit", "walkable"],
  "k": 3
}
```

- budget_max: positive finite monthly USD amount. Proposed default meaning is total housing budget; never divide rent by the number of people without an explicit budget-basis field.
- household: alone or with_co_leaser. It does not imply marital status, children, age, or another unprovided attribute.
- housing_preference: own_apartment or co_living. Never infer co-living from living alone.
- tags: allowlisted, deduplicated lifestyle preferences. Unknown tags produce a validation response listing allowed values. An empty list asks the user for priorities rather than creating a zero cosine vector.
- k: integer from 1 to 5, with default 3. Return fewer when fewer are eligible.
- A co_living tag alongside own_apartment needs clarification. The brief describes co-living as an optional solo path; with_co_leaser plus co_living should also request clarification until the team defines support.

The current area data does not prove housing-type availability. Household and housing preference control compatible synthetic-card display and co-living scoring mode; do not exclude a ZIP merely because it lacks a demo card. Describe results as area matches, with availability unverified. Accurate room-price filtering for co-living requires room-price data; the current median rent remains an explicitly labeled area-level proxy.

### Recommendation response

Agree a versioned structure before connecting MCP:

```text
schema_version
status: ok | no_matches | needs_clarification
applied_filters: budget amount, rent field/basis, household, housing preference
results[]:
  zip, area_name, rank, score, score_method
  median_rent_usd, rent_source, source_period, rent_is_imputed
  matched_preferences[]: tag, feature_value, contribution
  themes[]: theme, polarity, evidence_ids, source_count, is_demo
  limitations[]
eligible_count, returned_count
excluded_counts: missing_rent, over_budget, missing_features
warnings[], data_version, model_version
```

Input/schema errors should have an explicit error code and field details rather than looking like valid no-match responses. A score is a similarity value, not a probability of satisfaction. Explanations must distinguish a proxy feature match from a supported review statement. Do not serialize NaN or infinity into JSON.

## 5. Recommendation algorithm

### Baseline pipeline

1. Validate the request and normalize allowed tag names.
2. Load the prepared snapshot through one adapter and validate its schema.
3. Filter missing/invalid rent, then filter median_rent_usd <= budget_max.
4. Select the fixed scoring dimensions for the requested housing mode. Validate those dimensions.
5. Build a user preference vector, compute cosine scores, and sort by score descending then ZIP ascending for deterministic ties.
6. Select up to k unique ZIPs; attach display metadata and NLP evidence afterward.
7. Return counts, data versions, reasons, and limitations. Never fill a short list with over-budget ZIPs.

### Feature vector and scoring

For own_apartment use ordered dimensions [transit, social, quiet, pet_friendly, walkable]. An area's vector holds its values; the user's vector has 1 for requested tags and 0 otherwise. For co_living, add co_living_friendly and map the explicit co_living preference to that dimension. Keep the co-living dimension out of the own-apartment mode entirely.

With all initial feature weights set to 1:

```text
score(x, u) = sum(x[j] * u[j]) / (sqrt(sum(x[j]^2)) * sqrt(sum(u[j]^2)))
```

Compute cosine across the whole fixed mode vector, not just selected dimensions: one selected positive dimension alone would make every positive candidate score 1. Handle zero-norm area vectors explicitly as score 0; an empty user vector requests clarification.

When testing weighted cosine later, transform both vectors with sqrt(weight[j]) before cosine. This gives each dimension weight[j] in the dot product, rather than accidentally squaring the intended weights. Use positive versioned feature weights; keep them separate from the user's selected priorities.

Cosine measures alignment rather than absolute feature strength. Unrequested strong features also affect the denominator. Compare it against a simple weighted mean of requested feature values during evaluation, and inspect disagreement examples. Keep cosine as the required baseline; propose a change only with evidence and team agreement.

For a reason breakdown, expose each selected dimension's normalized dot-product contribution. These contributions sum to the cosine score. Raw feature values should also be returned so the explanation is understandable. Do not claim a numerical score guarantees lifestyle fit.

### Edge-case decisions

| Case | Expected behavior |
|---|---|
| Rent equals budget | Eligible |
| No eligible ZIPs | no_matches, empty list, exclusion counts; user can choose to revise preferences |
| Only two eligible ZIPs, k=5 | Return two; explain shortage |
| Missing themes | Keep ranking; show evidence unavailable |
| Duplicate input tags | Deduplicate without increasing their importance |
| Duplicate area ZIPs | Fail data validation |
| Equal scores | Stable ZIP tie-break |
| High proxy score but negative text evidence | Preserve baseline rank and show the conflict honestly |
| Missing area name | Display ZIP; do not invent a neighborhood name |

## 6. NLP work with Nadia

There are two different text tasks. The agent may convert a user sentence into structured preferences. Your NLP workstream extracts themes from neighborhood text. Keep separate tests and contracts for these tasks.

### Stage A: evidence-preserving lookup

Start with the original demo snippets and their existing theme labels. This supplies a working evidence interface before building an extractor. Preserve snippet_id, ZIP, source, text, and is_demo=true. Do not reverse-join cleaned indicators to raw rows by row position; IDs were dropped and ordering is not a durable key.

Ask the data lane to export a metadata/evidence table alongside the numeric table. Keep original card IDs and disclaimers in a separate display table for the same reason.

### Stage B: reproducible extraction baseline

1. Nadia defines a taxonomy aligned with transit, social, quiet, pet_friendly, and walkable. Keep extra themes such as expensive as context; co_living is conditional on the requested mode.
2. Preserve original text; create a separate cleaned text field. Deduplicate and remove personal information according to the agreed corpus policy.
3. Assign ZIP only from supported location metadata. Record mapping method and ambiguity; exclude unresolved locations from ZIP-specific evidence.
4. Build keyword/phrase rules with basic negation and evidence spans. "Not quiet" must not become positive quiet evidence. A theme label alone establishes a topic, not positive sentiment.
5. Support multiple themes per snippet and positive/negative/mixed/unknown polarity.
6. Have Nadia and Om independently label a small sample and resolve disagreements. Separate development and held-out examples, keeping duplicates and related source records together.
7. Evaluate per-theme precision, recall, F1, and support. If the corpus stays too small for a meaningful holdout, report descriptive errors and the limitation rather than a confident generalization claim.

### Evidence contract

Each extracted record contains evidence_id, zip, theme, polarity, original snippet or permitted excerpt, source identifier/URL when known, is_demo, mapping_method, and extractor_version. Real corpora additionally need source/license notes and collection period. Rule matches should carry a rule identifier; do not label an uncalibrated score as a probability.

Aggregate by ZIP and theme with unique-source counts and supporting IDs. Limit repeated excerpts from the same source. Preserve negative and mixed evidence. Missing reviews mean unknown coverage, not poor neighborhood quality.

### Stage C: optional ranking experiment

The first engine ranks structured features and attaches NLP evidence afterward. This keeps missing reviews from automatically hurting a ZIP and makes the baseline interpretable.

Only test NLP reranking after the structured baseline and evidence quality are measured. Compare structured-only versus structured-plus-NLP with the same eligible ZIPs, report coverage effects, and keep the budget filter unchanged. Avoid counting walkability twice through both a proxy and repeated review mentions. Keep this optional if source coverage is weak.

## 7. Proposed implementation layout

These files are planned, not present yet:

```text
src/
  contracts.py             # request/response and validation
  data_loader.py           # adapter to the agreed prepared-data interface
  features.py              # explicit tag mapping and feature weights
  recommender.py           # filtering, cosine scoring, deterministic ranking
  nlp_themes.py            # evidence lookup/extraction and ZIP aggregation
  tools.py                 # shared functions consumed by MCP
tests/
  test_data_contract.py
  test_recommender.py
  test_nlp_themes.py
eval/
  run_recommender_eval.py
  recommendation_profiles_holdout.json
docs/
  recommender_contract.md
  nlp_contract.md
  recommender_results.md
```

Choose package entry points with the MCP owners before coding. Keep exploratory plots in notebooks and reusable behavior in importable modules. Use the existing Python/numpy/pandas/scikit-learn stack for the initial engine; no new model service is needed. Generated run details can go under ignored outputs/, with reviewed summary metrics and reproduction commands in docs/.

## 8. Evaluation and acceptance criteria

Start with all five existing profiles, but do not tune repeatedly against them and then claim they are an independent test. Ask Amelie for additional independently labeled development and holdout profiles. Expected relevance that conflicts with budget constraints should be flagged for review, not used to bypass the filter.

| Check | Definition / success condition |
|---|---|
| Precision@3 and @5 | Relevant returned ZIPs divided by requested k; report short lists separately |
| Label ceiling | Record min(k, number of relevant labels)/k; a profile with two labels cannot reach Precision@5=1 |
| Budget compliance | Every returned ZIP has eligible known rent <= budget; target 100% |
| Empty-result coverage | Report empty-profile count separately; empty lists cannot establish useful budget performance |
| Mean cosine | Average over returned items; descriptive, not independent relevance evidence |
| Theme coverage | Returned ZIPs with evidence matching at least one selected tag / returned ZIPs; also report each tag and real/demo split |
| No-result theme metric | Mark undefined when no results exist, rather than reporting 100% |
| NLP quality | Per-theme precision/recall/F1 and support on independently labeled text |
| Determinism | Same input, snapshot, and configuration yield the same results |
| JSON contract | Valid finite values, explicit error/empty status, stable field names |
| Evidence integrity | Every returned evidence ID resolves to stored text and source metadata |

Unit tests should use small hand-calculable tables for exact-budget boundaries, above-budget strong matches, NaN/sentinel/zero rent, missing features, duplicate ZIPs, zero vectors, tie ordering, k limits, unknown tags, and housing-mode behavior. An integration test should run the five repository profiles through the real prepared-data adapter. NLP tests should cover negation, multiple themes, duplicate text, unsupported ZIPs, and missing evidence.

Each evaluation run records code commit, data snapshot/hash, feature order, weights, rent policy, test profile version, timestamp, per-profile outputs, and aggregate metrics. Do not backdate the September baseline: if completed in October, label it October baseline and explain the schedule shift.

Before MCP handoff, demonstrate valid input, invalid input, no matches, fewer than k matches, and missing text evidence. The team's existing agent tests cover prohibited requests and grounding; the engine contract should accept only allowed structured preference fields. This plan follows the repository's responsible-use requirements and does not establish legal compliance.

## 9. Dated work plan

The old September baseline deadline has passed without engine code visible in the inspected branches. This recovery schedule targets a reproducible baseline on October 9 while preserving the October 30 integration milestone.

| Dates, 2026 | Work and proposed lead | Dependencies | Reviewable completion evidence |
|---|---|---|---|
| Sep 30-Oct 2 | Om with data/NLP owners: review snapshot; agree rent, feature, and evidence contracts | Cleaning branch review | Contract draft, sample request/response, explicit unresolved decisions |
| Oct 5-7 | Om: integrate agreed cleaning changes and implement adapter/validation; Nadia: demo evidence lookup | Stable ZIP/rent fields and metadata plan | Data report, importable loader, meaningful boundary tests |
| Oct 8-9 | Om + Anna: implement cosine baseline; Amelie: run five fixtures | Validated adapter | Reproducible baseline results and commit/data versions |
| Oct 12-16 | Anna + Om: error analysis and baseline comparison; Nadia + Om: extraction/annotation | Baseline; usable text | Comparison table, failure examples, theme metrics and coverage |
| Oct 19-23 | Om with Daniel/Azibator: connect recommend/crowd_themes; Nadia: provenance review | Stable JSON contracts | Contract tests and end-to-end tool output |
| Oct 26-30 | Team: integrated alpha; Om resolves engine integration issues | Agent and MCP integration | One complete request plus no-match demonstration; contract freeze |
| Nov 2-6 | Om + Anna: improve only measured ranking issues; Nadia: text quality | Alpha error report | Reviewed changes and comparison against frozen baseline |
| Nov 9-13 | Amelie with Om: full evaluation and coverage analysis | Integrated system | Layer 1 metrics plus routing/grounding handoff evidence |
| Nov 16-20 | Om + NLP owners: fix critical failures and document gaps | Evaluation findings | Beta with all budget and evidence-integrity checks passing |
| Nov 23-27 | Om: documentation and reproducibility work | Stable beta | Setup instructions, limitations, provenance, example outputs |
| Nov 30-Dec 4 | Team: final evaluation and feature freeze | Final data/model versions | Fresh-checkout reproduction and final scorecard |
| Dec 7-11 | Om: explain algorithm/results and rehearse demo with team | Frozen system | Presentation material and backup demo |
| Dec 14-15 | Team: final handoff, subject to confirmed deadline | Submission review | Final deliverables and attribution |

If the adapter or source metadata slips, continue baseline work with an explicitly versioned starter-data adapter. Do not silently mix raw and cleaned files or present demo evidence as real. Defer optional NLP reranking before reducing budget, evidence, or reproducibility checks.

## 10. First implementation tasks

- [ ] REC-01 (Om): write the versioned input/output contract. Done when Anna and an MCP owner can independently implement against it.
- [ ] DATA-HANDOFF (Amelie/Joana, Om reviews): resolve missing rents, metadata preservation, and snapshot loader. Done when ZIP uniqueness, coverage, provenance, and active-feature checks are explicit.
- [ ] REC-02 (Om): implement the adapter and budget filter. Done when missing/invalid rents never qualify and equality at the limit passes.
- [ ] REC-03 (Om, Anna reviews): implement deterministic cosine ranking and reason fields. Done when hand-calculated tests and short/empty cases pass.
- [ ] EVAL-01 (Amelie with Om): run fixtures and create the baseline report. Done when results can be reproduced from a clean checkout.
- [ ] NLP-01 (Nadia with Om): preserve demo evidence and define taxonomy/polarity. Done when every returned theme resolves to text with a demo label.
- [ ] NLP-02 (Nadia, Om reviews): implement extraction and annotated evaluation. Done when per-theme quality and ZIP coverage are reported.
- [ ] INT-01 (Daniel/Azibator with Om): connect tools to shared functions. Done when MCP returns the same rankings as direct engine calls.

### Decisions to settle in the first meeting

1. Confirm total monthly budget semantics and whether any imputed rent can establish eligibility.
2. Confirm the prepared loader and cleaning branch integration path.
3. Confirm the metadata tables that preserve review text, source IDs, area names, and synthetic disclaimers.
4. Confirm how co-living is described when only area-level rents are available.
5. Confirm who creates independent relevance labels and holds the evaluation set.
6. Confirm each task owner and the official submission deadline.

Your first concrete milestone is a Python function that returns reproducible, budget-filtered ZIP rankings and a separate ZIP-to-theme evidence function. Those two pieces give the MCP and agent teams a stable foundation to build on.
