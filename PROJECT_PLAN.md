# Fall 2026 Project Plan

## Responsible AI for Personalized Neighborhood Recommendations

**Working project window:** September 9-December 15, 2026

**Plan start:** September 9, 2026

**Working cadence:** Weekly team stand-up; advisor check-ins during the second and fourth weeks of each month. Daniel should confirm the exact lab dates with the advisor.

This plan uses December 15 as the working submission date because the project is due in mid-December. If the program publishes a different date, Daniel should move only the final handoff milestone and preserve the earlier feature freeze.

Because work begins after the original August onboarding period, the team should use September 9-11 to confirm any work already completed and immediately create recovery issues for anything missing. Do not redo finished work; link evidence such as notes, pull requests, or board items and continue from the current state.

## Team ownership

| Workstream | Owners | Primary responsibility |
|---|---|---|
| Data and preprocessing | Amelie, Joana | Loading and cleaning, ACS missing values, joins, normalization, Census API and Zillow Research upgrades |
| Recommender engine | Anna, Om | Preference vector, budget hard filter, cosine-similarity ranking, weight tuning |
| NLP and themes | Nadia, Om | Theme extraction, ZIP mapping, and replacement of demo text with filtered review data |
| MCP server | Om, Daniel, Azibator | Five tool contracts, implementation, routing, and integration |
| Agent, ethics, and demo | Joana, Nadia | Gemini integration, tool-grounded responses, refusal layer, synthetic-data labels, and Streamlit app |
| Evaluation | Amelie | Three-layer scorecard, fixtures, baseline/final comparison, and results tracking |
| Project management | Daniel | GitHub Project, issues, deadlines, check-in agendas, decisions, README, and final submission coordination |

Shared ownership means both named owners review the work. Each GitHub issue should still have one directly responsible assignee so tasks do not sit between two people.

## Definition of the MVP

By the end of the project, a user must be able to enter a budget, household type, housing preference, and lifestyle tags and receive 3-5 ranked Miami ZIP codes. The system must:

- Apply the budget as a hard filter before ranking.
- Rank in Python with cosine similarity; Gemini only explains tool results.
- Return themes tied to ZIP codes and document the source of the text.
- Expose `schema`, `area_stats`, `crowd_themes`, `recommend`, and `ethics` through MCP with stable JSON contracts.
- Refuse tenant scoring, demographic steering, hidden screening criteria, and unsupported live-listing requests.
- Clearly label `area_options.csv` cards as synthetic and not real listings.
- Report the required baseline and final evaluation metrics.
- Run through a Streamlit demo with documented setup instructions.

## Dependency map

```text
Data contract and cleaned features
    +--> Recommender --> recommend MCP tool --+
    +--> NLP themes --> crowd_themes MCP tool +--> Gemini agent --> Streamlit demo
    +--> area_stats/schema MCP tools ----------+
Ethics rules --> ethics MCP tool --> refusal layer

Evaluation fixtures run throughout every layer; they are not a final-week task.
```

The critical path is cleaned data -> recommender -> MCP integration -> agent -> full evaluation -> final demo. NLP can progress in parallel after the ZIP and text schemas are agreed.

## Dated execution plan

| Week | Goal and concrete deliverables | Owners |
|---|---|---|
| **Sep 9-11** | **Launch and recovery audit:** read the required project documents, inspect the starter CSVs and eval fixtures, and identify any work already completed. Confirm the MVP, official deadline, repository layout, branch/PR rules, and responsible-AI constraints. Create the GitHub Project with Backlog, Ready, In Progress, Review, Blocked, and Done. Draft the recommender interface and five MCP JSON contracts. | Everyone; Daniel owns board and decision log |
| **Sep 14-18** | Build the first loading/cleaning pipeline; preserve ZIPs as strings; convert ACS suppression values such as `-666666666` to missing; document imputation decisions; normalize features; and add data-quality checks. In parallel, define the preference vector and budget hard filter, build a stubbed `recommend` MCP path, and implement initial demo-theme lookup. | Amelie, Joana; Anna, Om; MCP team; Nadia, Om |
| **Sep 21-25** | Implement and test the baseline cosine ranker with deterministic top-k output. Connect it to cleaned starter data. Add tests for invalid budgets, unknown tags, and no eligible ZIPs. Run all recommendation profiles and record Precision@3, Precision@5, mean cosine similarity, budget-filter pass rate, and initial theme coverage. | Anna, Om; Amelie leads evaluation; Nadia supports themes; advisor check-in target |
| **Sep 28-Oct 2** | Baseline freeze. Tag or document the baseline commit and metrics. Finalize the October upgrade plan, source provenance fields, cache/raw-data policy, and schemas so real-data swaps do not break consumers. | Everyone; Daniel records milestone |
| **Oct 5-9** | Implement reproducible Census ACS and Zillow Research ingestion or checked-in snapshots. Validate geography, dates, types, missingness, and joins. Download/filter the permitted review dataset for Miami/Florida and document its license/source. | Amelie, Joana; Nadia, Om; advisor check-in target |
| **Oct 12-16** | Swap improved features into the pipeline without changing the public interface. Extract and aggregate real review themes by ZIP. Tune feature weights using error analysis while keeping budget a hard filter. | Data, NLP, Recommender |
| **Oct 19-23** | Implement all five MCP tools and contract tests. Test tool selection and arguments against `agent_routing_prompts.json`. Begin Gemini integration using tool outputs only. | Om, Daniel, Azibator; Joana, Nadia; advisor check-in target |
| **Oct 26-30** | **Integrated alpha milestone:** cleaned public data, tuned recommender, themes, and five MCP tools work together. Freeze MCP contracts. Demo one full request from user input to structured recommendation and explanation. | All technical lanes; Daniel coordinates |
| **Nov 2-6** | Connect the Streamlit workflow. Implement the ethics gate before recommendation calls, grounded response formatting, empty/error states, and visible synthetic-data disclaimers. | Joana, Nadia with MCP owners |
| **Nov 9-13** | Run the full three-layer scorecard. Target >=90% tool selection, >=85% argument accuracy, >=95% grounding, 100% prohibited-prompt refusal, 100% synthetic labeling when options are shown, and 100% budget-filter pass rate. File a bug for every miss. | Amelie; lane owners fix failures; advisor check-in target |
| **Nov 16-20** | **Beta milestone:** resolve high-severity eval failures and test edge cases: very low budget, no matches, unsupported tags, missing ZIP, prompt injection, live-listing requests, and demographic steering. Conduct a short usability test with people outside the build lane. | Everyone; Agent/Ethics and Evaluation lead |
| **Nov 23-27** | Reduced-scope holiday week: clean code, tests, citations, provenance, screenshots, architecture diagram, and README draft. Avoid scheduling a critical integration for this week. | Daniel plus all owners; advisor check-in if held |
| **Nov 30-Dec 4** | **Feature freeze:** rerun the final scorecard on a clean checkout, compare baseline versus final, capture demo evidence, and finish setup/run instructions. Only bug fixes after December 4. | Amelie, Daniel, all lane owners |
| **Dec 7-11** | Rehearse the final demo and presentation twice: one normal scenario and one prohibited request. Verify a fresh teammate can install and run the project from the README. Prepare a recorded backup demo. | Everyone; Daniel schedules; advisor check-in target |
| **Dec 14-15** | Final QA and submission: links, credits, attribution, licenses, limitations, results table, issue closure, release/tag, slide deck, and demo artifacts. Submit by the confirmed deadline. | Daniel coordinates; everyone signs off |

## Workstream acceptance criteria

### Data and preprocessing — Amelie and Joana

- One importable module is the only supported way downstream code loads prepared data.
- ZIP codes remain strings and joins have row-count/uniqueness checks.
- ACS suppression values are not treated as real negative values.
- Imputation, exclusion, scaling, source date, and provenance decisions are documented.
- The same public interface works for starter data and October upgrades.

### Recommender engine — Anna and Om

- Input contract covers `budget_max`, `household`, `housing_preference`, tags, and `k`.
- Budget filtering happens before similarity ranking and has a 100% pass rate.
- Ranking is deterministic, returns 3-5 ZIPs when enough eligible areas exist, and handles no-match cases honestly.
- Feature weights and normalization are documented and justified by evaluation results.
- The LLM is never used to calculate the ranking.

### NLP and themes — Nadia and Om

- Text is filtered and mapped to ZIPs with reproducible rules and source/license documentation.
- Generated or copied fake reviews are never presented as authentic reviews.
- Output includes structured themes and supporting snippets or aggregate counts.
- Theme coverage is measured for recommended ZIPs, including missing-theme behavior.

### MCP server — Om, Daniel, and Azibator

- All five tools have stable JSON input/output contracts and validation.
- `recommend` delegates to the recommender; MCP does not duplicate ranking logic.
- Contract tests cover valid, invalid, empty, and error responses.
- Routing fixtures verify both selected tool and arguments.
- README includes exact local run and connection instructions.

### Agent, ethics, and demo — Joana and Nadia

- The agent states only facts present in MCP output and identifies unavailable information.
- The refusal layer prevents prohibited prompts from reaching `recommend` where required.
- Synthetic cards visibly say they are demos and not real listings.
- Gemini-key absence and tool failures produce a useful fallback/error state.
- Streamlit supports the main scenario and at least one refusal scenario.

### Evaluation — Amelie

- Evaluation scripts are repeatable and version-controlled, not only manual notebook cells.
- September baseline and final metrics are tied to commit IDs and data versions.
- Failures are visible per fixture/profile as well as in aggregate.
- The README scorecard contains Precision@3, mean cosine similarity, routing accuracy, grounding rate, refusal rate, and theme coverage; also report the other required checks where available.

### Project management — Daniel

- Every issue has one assignee, workstream label, target week, dependency, and acceptance criteria.
- Board and risk log are reviewed weekly; blocked work is raised within one business day.
- Advisor agendas go out before check-ins and decisions/actions are recorded afterward.
- README is updated incrementally and accurately distinguishes real, mixed, demo, and synthetic data.

## Team operating rhythm

- **Monday:** 20-minute planning meeting; each person chooses a deliverable that can be reviewed that week.
- **Midweek:** written blocker update; integration owners resolve contract questions quickly.
- **Friday:** PR/demo review and board update; merge only when acceptance criteria and relevant tests pass.
- **Advisor weeks:** Daniel sends the agenda at least 24 hours before the check-in with current metrics, decisions needed, and the next milestone.
- **Pull requests:** one reviewer from the owning lane and one reviewer from a consuming lane for interface changes.

## Suggested advisor check-in agenda

1. Show the current working increment, not only slides.
2. Report metric movement and the main failure examples.
3. Review data provenance and responsible-AI risks.
4. Ask for decisions that affect interfaces, scope, or evaluation labels.
5. Confirm owners and due dates for the next two weeks.

## Milestone gates

| Gate | Date | Exit condition |
|---|---|---|
| Launch and recovery audit complete | **Sep 11** | MVP, interfaces, risks, success measures, board, and any recovery work agreed |
| Baseline complete | **Sep 25** | Starter pipeline and recommender run on all Layer 1 fixtures; metrics saved |
| Baseline frozen | **Oct 2** | Commit/data version and baseline scorecard recorded |
| Integrated alpha | **Oct 30** | Improved data, recommender, themes, and five MCP tools work end to end |
| Evaluated beta | **Nov 20** | Three layers run; critical grounding, budget, and ethics failures resolved |
| Feature freeze | **Dec 4** | Final metrics and complete demo path reproduced from a clean checkout |
| Submission ready | **Dec 11** | README, presentation, backup demo, credits, and limitations reviewed |
| Final handoff | **Dec 15** | Submission delivered and repository tagged |

## Initial risk register

| Risk | Early warning | Mitigation | Owner |
|---|---|---|---|
| Real-data upgrade breaks downstream modules | Column/interface changes after October begins | Freeze a prepared-data schema by Oct 2; add schema and join tests | Amelie, Joana |
| Om becomes a bottleneck across three lanes | Recommender, NLP, and MCP issues wait on the same person | Give each issue one owner; document contracts; pair Azibator/Daniel on MCP and Nadia on NLP | Daniel |
| Review data cannot be mapped reliably to ZIP | Many reviews lack usable location fields | Validate a sample in early October; keep transparent missing coverage and a documented fallback | Nadia, Om |
| Model looks accurate only on five fixtures | Weight changes are tailored to individual expected ZIPs | Keep a small holdout/edge-case set and document limitations; ask advisor to review labels | Anna, Om, Amelie |
| LLM invents details | Responses include facts absent from tool JSON | Structured response template, grounding audit, and explicit unavailable-data behavior | Joana, Nadia |
| Ethics checks happen too late | Prohibited prompts still call the recommender in November | Implement the refusal gate by Nov 6 and run fixtures on every relevant PR | Joana, Nadia, Amelie |
| Final integration slips into presentation week | MCP contracts or data schema change after Oct 30 | Contract freeze Oct 30 and feature freeze Dec 4 | Daniel |
| Secrets or licensed data enter Git | API key or restricted raw review file appears in a PR | `.env`, ignore rules, source/license review, and PR checklist | All; Daniel verifies |

## First GitHub issues to create

1. Audit starter datasets and document missing-value decisions — Amelie.
2. Define the prepared-feature schema and loader interface — Joana.
3. Define recommender input/output contract and no-match behavior — Anna.
4. Implement baseline budget filter and cosine ranker — Om or Anna as single assignee.
5. Define theme taxonomy and ZIP-mapping rules — Nadia.
6. Draft the five MCP JSON contracts — Azibator or Daniel as single assignee; Om reviews.
7. Build stubbed `recommend` MCP path — MCP team.
8. Create automated Layer 1 baseline runner — Amelie.
9. Draft ethics/refusal decision table — Joana.
10. Create GitHub Project fields, labels, milestones, and check-in templates — Daniel.
