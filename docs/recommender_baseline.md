# Recommendation baseline: October 11, 2026

## Implemented scope

The `flow_neighborhoods` package implements the preference/budget behavior in #8, initial demo-theme lookup in #9, and a deterministic ranker for #11 (requested-feature mean by default; the original cosine baseline is kept for comparison). The evaluation runner supports Amelie's #12 scorecard. This is local implementation evidence; GitHub issue statuses have not been changed.

The recommendation contract below contributes to #5. Contracts for all five MCP tools and the MCP server/stub in #10 remain outstanding. No language model, server, live listing integration, or trained NLP classifier is included in this baseline.

## Run from the repository root

The engine uses Python 3.11+ and the standard library. Keep the team's existing `requirements.txt` for the broader app; the package's development dependencies are separate.

```powershell
.venv/Scripts/python.exe -m pip install -e . --group dev
.venv/Scripts/python.exe -m flow_neighborhoods --budget 2500 --household with_co_leaser --tags transit walkable --k 3
.venv/Scripts/python.exe -m flow_neighborhoods.evaluate --scorer mean
.venv/Scripts/python.exe -m flow_neighborhoods.evaluate --scorer cosine
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
```

If an older pip does not support `--group`, install `-e .` and `pytest ruff` separately. With uv, `uv run --group dev pytest` can install the package and run its tests. No API key is required. CLI paths default to `data/` and `eval/` relative to the working directory; use `--data-dir` and `--profiles` when running elsewhere.

## Troubleshooting local tests

If pytest reports `PermissionError: [WinError 5]` while scanning `pytest-of-patel`,
the failure is in temporary-directory setup before the recommendation tests run.
Windows sandbox and interactive sessions can have different access to an existing
pytest directory. `tests/conftest.py` now creates a fresh temporary root for each
invocation and cleans up that invocation's files. An explicit `--basetemp` is still
honored. The pytest cache plugin is disabled to avoid reusing an inaccessible
`.pytest_cache`; test collection and assertions remain enabled.

Use the `.venv/Scripts/python.exe` commands above. The global `python` installation
does not necessarily contain this package or the test dependencies. In VS Code,
select the workspace's `.venv/Scripts/python.exe` with **Python: Select Interpreter**.

## Python contract

```python
from flow_neighborhoods import Recommender

engine = Recommender("data")  # scorer="cosine" for the original baseline
result = engine.recommend({
    "budget_max": 2500,
    "household": "with_co_leaser",
    "housing_preference": "own_apartment",
    "tags": ["transit", "walkable"],
    "k": 3,
})
themes = engine.crowd_themes("33130")
```

Inputs:

- Budget: finite positive number, total monthly USD. No automatic rent splitting for co-leasers.
- Household: `alone` or `with_co_leaser`.
- Housing: `own_apartment` or `co_living`.
- Tags: transit, social, quiet, pet_friendly, walkable, co_living. Whitespace/case are normalized and duplicates removed.
- k: integer 1-5, default 3. Unknown request keys are rejected.

`ValidationError` means invalid input; `DataError` means an invalid source schema/value. Missing files raise `OSError`. The future MCP adapter must translate these into explicit tool errors. The CLI prints errors to stderr and exits with code 2.

Valid requests return `ok`, `no_matches`, or `needs_clarification`, alongside `results`, eligible/returned counts, mutually exclusive exclusion counts, warnings, filter details, model version, and SHA-256 hashes of the three source files. Empty tags, conflicting own-apartment/co-living tags, and an undefined co-leaser/co-living combination request clarification.

Each ranked result includes ZIP/name, rank, score, unscaled rent estimate, source filename, unknown source period (`null`), matched preferences with score contributions, and demo theme evidence. There is no assertion of housing inventory availability. Missing themes do not lower a score. All results are JSON-safe with finite numeric values.

`crowd_themes` requires a five-digit string and returns evidence with original IDs, text, source labels, `is_demo=true`, and `polarity=unknown`. `no_evidence` is distinct from proof of a negative theme; `known_area` distinguishes an unknown ZIP from a known ZIP without snippets. Existing theme labels are used directly; a quiet-topic label is not evidence that the text praises quietness.

## Data decisions

- Prepared numeric source: `data/area_features_cleaned.csv` from main at `5606a1b` (merged cleaning PR #14).
- Original `area_features.csv` supplies names only; its values do not override cleaned scores or rents.
- Original `crowd_text_snippets.csv` supplies attributable demo evidence because the cleaned theme table removed IDs and text.
- Source tables and cleaning notebook are not modified. Loaders reject duplicate ZIPs, malformed rows, missing required columns, and out-of-range feature values.
- Blank/nonfinite/nonpositive rent cannot establish eligibility. Three current ZIPs are excluded: 33101, 33109, 33039. No imputation or synthetic-card price is substituted.
- Missing active scoring dimensions exclude a row. Co-living values are inactive for own-apartment scoring.
- Household is preserved but does not alter the score; the dataset has no reliable household-specific inventory or price basis.
- The five lifestyle features are already 0-1 proxies. Rent is a dollar-valued hard filter, not a cosine dimension. Broader public-feature normalization remains outside this baseline.
- Co-living adds `co_living_friendly` to the vector with user preference 1. Room prices are unavailable, so budget filtering still uses the disclosed area-rent proxy.

## Scoring

Budget filtering precedes scoring. Scores sort descending, then ZIP ascending for ties. A short list stays short; the filter is never relaxed. The score is a match index, not a probability of satisfaction.

**Default (`mean-v1`):** the average of the area's values for the requested features. Co-living mode always adds `co_living_friendly`. Each feature contributes `value / n_requested`, so contributions sum to the score. Features the user did not request have no effect, and only missing *requested* features exclude an area.

**Baseline (`cosine-v1`, `scorer="cosine"`):** cosine similarity between a 0/1 preference vector and the full fixed feature vector (transit, social, quiet, pet_friendly, walkable, plus co_living_friendly in co-living mode). Zero-norm area vectors score 0.

Why the default changed: cosine divides by the length of the *whole* area vector, so strengths the user did not ask for lower the score. For a transit + walkable request, 33128 (transit 0.92, social 0.80, quiet 0.94) ranked 52nd because its social and quiet values are high, while 33150 (transit 1.00, social 0.45) ranked first. A user asking for transit should not be told an area is a worse fit because it also has nightlife.

Data limits that no scoring rule can fix:

- `pet_friendly` is 0.6 for every ZIP. Requesting it shifts every score equally, so it cannot change the ranking. The response warns when a requested feature is constant across the snapshot, and when all eligible areas tie.
- `walkable` is effectively binary: 3 ZIPs are 0 and the other 77 are about 1, so in practice transit + walkable ranks by transit alone.
- `quiet` closely tracks the inverse of `social` (it is at least `1 - social/2` everywhere), so "quiet" here means "less social", not "suburban/residential".

## Measured baseline

Run date: October 11, 2026. Five supplied profiles, uniform feature weights, no fitting or tuning. Reports are written to `outputs/recommender_<scorer>.json` and include per-profile outputs, source/code/profile hashes, Git HEAD and working-tree status. Git HEAD alone does not identify uncommitted implementation; use the included code hashes too.

| Metric | cosine-v1 | mean-v1 |
|---|---:|---:|
| Mean Precision@3 | 0.1333 | 0.1333 |
| Mean Precision@5 | 0.0800 | 0.1600 |
| MRR over the full eligible ranking | 0.155 | 0.320 |
| Budget pass rate among nonempty profiles | 100% | 100% |
| Demo theme coverage @5 (macro average) | 12% | 20% |
| Empty profiles | 0/5 | 0/5 |

Mean score is reported in each JSON file but is not comparable across scorers.

| Profile | cosine top 3 | mean top 3 | Rank of each expected ZIP (cosine to mean) |
|---|---|---|---|
| P1: transit/walkable, co-leaser | 33150, 33135, 33054 | 33150, 33136, 33142 | 33128: 52 to 4; 33127: 40 to 12; 33130: 34 to 16 |
| P2: social/walkable, alone | 33186, 33015, 33012 | 33012, 33157, 33186 | 33130: 23 to 9; 33127: 25 to 11; 33128: 34 to 12 |
| P3: co-living/transit | 33127, 33130, 33128 | 33128, 33127, 33130 | 33128: 3 to 1; 33130: 2 to 3 |
| P4: quiet/pet-friendly | 33129, 33154, 33035 | 33031, 33128, 33170 | 33156: 13 to 26; 33133: 19 to 31; 33134: 25 to 37 |
| P5: transit/social | 33157, 33012, 33142 | 33142, 33157, 33012 | 33128: 16 to 5; 33130: 8 to 9 |

The mean scorer moves expected ZIPs up in P1, P2, P3 and P5, but most stay just outside the top 3. That remaining gap comes from the features: for P1, 33150 has the highest transit score in the snapshot, and nothing in the data encodes the Wynwood/Brickell/Downtown character the labels describe. P4 gets worse because the cosine baseline rewarded areas for being *low* on everything else, which happened to favor the labeled residential ZIPs; under `mean-v1` the ranking follows the `quiet` proxy, which does not represent "residential". Fixing P4 needs a better quiet feature, not a different formula.

Precision divides by requested k even for short lists. MRR uses the best-ranked expected ZIP across all eligible areas, so it shows improvement below the top-k cut-off. Label ceilings are included per profile because some profiles list fewer relevant ZIPs than k. Empty-result budget and theme metrics are undefined (`null`), and empty-profile counts are reported separately. Theme coverage means at least one provided topic matches a selected tag, not positive sentiment or authentic review coverage.

Only the co-living profile retrieves labeled relevant ZIPs in its top 3. Relevance is still weak despite valid budget filtering. The switch to `mean-v1` is a correctness fix (unrequested features should not count against an area), not tuning; do not tune weights solely to these five fixtures. P5 mentions Brickell in its description, but its structured inputs provide no target-ZIP field; the engine does not read evaluation descriptions as user preferences.

## Validation and next steps

40 tests cover budget boundaries, missing/suppressed rents, hand-calculated mean and cosine values, unrequested-feature behavior, constant-feature warnings, zero vectors, stable ties, duplicate tags, invalid requests, housing-mode behavior, missing features, bad source schemas, evidence preservation, evaluation denominators, and all five profiles with the actual snapshot.

Next, review false matches with Anna and the data owners, especially the constant `pet_friendly`, near-constant `walkable`, and `quiet` derived from `social`. Better features will move precision more than scoring changes. Validate `mean-v1` against cosine on separate development profiles. With Nadia, add evidence-preserving text preprocessing and polarity-aware extraction after agreeing a labeled evaluation set. With the MCP owners, finalize tool error mapping and implement the tool server. Keep the current baseline fixed for comparison.
