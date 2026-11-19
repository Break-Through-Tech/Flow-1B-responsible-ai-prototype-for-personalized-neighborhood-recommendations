# Monthly data refresh

Approved by the advisor on Nov 12. The script is `scripts/refresh_data.py`. Nothing in `data/` changes until a person has read the report and runs `apply`.

## Steps

```powershell
.venv/Scripts/python.exe scripts/refresh_data.py check    # what's new or stale
.venv/Scripts/python.exe scripts/refresh_data.py fetch    # download, rebuild, write the report
# read outputs/refresh/<date>/report.md
.venv/Scripts/python.exe scripts/refresh_data.py apply outputs/refresh/<date>
.venv/Scripts/python.exe -m pytest -q
```

Then update the source years that the report lists in `data_dictionary.md`, and open a PR that includes the report.

## Sources

| Source | Refresh | How |
|---|---|---|
| ACS 5-year B08301, ZIP Code Business Patterns, Census Gazetteer | Yearly | `fetch` picks the newest published year, or pin one with `--acs-year` / `--zbp-year` / `--gazetteer-year` |
| HUD Small Area FMRs | Yearly (new fiscal year starts Oct 1) | huduser.gov blocks automated downloads. Joana supplies `HUD-SAFMR.csv`; pass her folder with `--joana` and `--hud-fy` |
| Transit (GTFS) | When Miami-Dade publishes a new feed | Joana reruns `build_transit_data.py`; pass her folder with `--joana`. `check` flags data older than 35 days |
| Co-living listings | Monthly | Re-verify by hand the listings `check` reports as stale; edit `data/co_living_listings.csv` |
| BTS noise map | Every few years | `experiments/feature_candidates/noise.py` |

Review text (Google or similar) is not in the refresh yet. It needs a source whose terms allow our use.

## What `build` checks

- `tests/test_data_files.py` runs on the staged files; `apply` refuses a stage that fails.
- Changes by file: rows added or removed, and the largest numeric changes.
- Evaluation before and after, on the five original profiles only; the held-out sets stay unscored.

`data/data_sources.json` records the vintage of each source. `apply` updates it.

## First run (Nov 18): staged, not applied

Moving from ACS 2018–22 to 2020–24, ZBP 2021 to 2023 and Gazetteer 2023 to 2026: data checks pass; P@3 0.53 → 0.47, MRR 0.82 → 0.82, budget compliance 100%. P5 (Brickell focus) drops Downtown from its top 3. The team should decide whether to apply it before the final scorecard, since it changes the reported scores.
