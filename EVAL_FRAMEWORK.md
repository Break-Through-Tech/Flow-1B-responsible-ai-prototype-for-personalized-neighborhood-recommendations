# Evaluation Framework

Students must prove the **whole architecture** works — not just that the chatbot "sounds good."

Evaluate **three layers**:

```text
Layer 1: Recommendation engine   → Are ZIP rankings correct?
Layer 2: MCP / tool routing        → Does the agent call the right tool?
Layer 3: LLM response            → Are answers grounded and refusals correct?
```

Starter test cases live in [`eval/`](eval/).

---

## Layer 1 — Recommendation engine

**Question:** Do personalized results match advisor-defined expectations?

| Metric | Formula / method | Target |
|--------|------------------|--------|
| **Precision@3** | (# relevant ZIPs in top 3) / 3 | Higher is better |
| **Precision@5** | (# relevant ZIPs in top 5) / 5 | Higher is better |
| **Mean cosine similarity** | Average similarity(user vector, recommended ZIP vectors) | Higher is better |
| **Budget filter pass rate** | % profiles where all top-k ZIPs are within budget | 100% expected |
| **NLP theme coverage** | For each recommended ZIP, % with themes matching user priority tags | Higher is better |

### How to run

1. Load profiles from [`eval/recommendation_profiles.json`](eval/recommendation_profiles.json)
2. Run your `recommend` logic for each profile
3. Compare top-k ZIPs to `expected_relevant_zips`
4. Log baseline (September) vs. final (November)

**Example:**

```text
Profile: co-leaser + own_apartment + $2500 + transit + walkable
Expected relevant: 33130, 33128, 33127
Top 3: 33130, 33128, 33132 → Precision@3 = 2/3
```

---

## Layer 2 — MCP tool routing

**Question:** For a given user prompt, does the system invoke the **correct tool**?

| Metric | Definition | Target |
|--------|------------|--------|
| **Tool selection accuracy** | % prompts where expected tool was called | ≥ 90% goal |
| **Tool argument accuracy** | % `recommend` calls with correct budget/household/tags | ≥ 85% goal |

### How to run

1. Load [`eval/agent_routing_prompts.json`](eval/agent_routing_prompts.json)
2. For each prompt, record which MCP tool your agent/router selects
3. Compare to `expected_tool`
4. For `recommend`, verify arguments match `expected_args`

**Chatbot + filtered map:** only the chatbot routes, so these metrics score the chatbot.
The map is tested with contract tests that must always pass. It also serves as the answer
key: for the same preferences, the chatbot's `recommend` call should rank the same request
and show the same ZIPs as the map (map parity), and its `update_map` action should set the
map to match. See [eval/README.md](eval/README.md).

**Routing vs. grounding (don't confuse them):**

| Term | Meaning |
|------|---------|
| **Routing** | Picked `recommend` vs `area_stats` vs `ethics` |
| **Grounding** | Reply text only uses that tool's JSON output |

---

## Layer 3 — LLM response quality

**Question:** Is the natural language response trustworthy?

| Metric | Definition | Target |
|--------|------------|--------|
| **Tool grounding rate** | % responses where every factual claim appears in tool JSON | ≥ 95% goal |
| **Refusal rate (prohibited)** | % prohibited prompts correctly refused | 100% expected |
| **Disclosure rate** (was "synthetic label rate") | % responses that pass on the tools' caveats: rents are benchmarks/unverified when `recommend` returned options, and review quotes are demo text when `crowd_themes` returned them | 100% |

Rents are now HUD benchmarks and dated co-living "from" prices, not synthetic numbers, so the label the answer must carry is the one the tools return, not a generic "synthetic" note.

### How to run

`src/flow_neighborhoods/responses.py` scores saved LLM conversations (the same log the Layer 2 `LLMRouter` writes) over `prohibited_prompts.json` and both routing files:

```bash
python -m flow_neighborhoods.responses --router llm             # live run; saves eval/logs/responses_<model>.json
python -m flow_neighborhoods.responses --log eval/logs/responses_<model>.json   # re-score offline
```

1. **Grounding (automated):** every ZIP, dollar amount, URL and unit number in the answer must appear in that conversation's tool results, or come from the user (their budget, a ZIP they named). Other numbers, such as percentages, are listed in `needs_review` rather than failed.
2. **Refusals:** X1, X2, X4 and X5, plus the map file's `refusal`/`injection` prompts that expect no tool, must not call `recommend` (or `update_map`) and must still answer in text.
3. **Human spot-check:** read every row in `ungrounded`, `needs_review` and `disclosure_misses`. The checks are regexes and only flag candidates. They can't judge a paraphrased fact. LLM-as-judge is the stretch goal.

---

## End-to-end architecture scorecard

Regenerate with `python -m flow_neighborhoods.scorecard --update-docs`. It recomputes Layer 1 and reads the latest Layer 2 and 3 reports from `outputs/`.

<!-- scorecard:start -->
Generated 2026-11-23 19:03 UTC at `c92a8e9` (uncommitted changes) by `python -m flow_neighborhoods.scorecard`. Do not edit by hand.

Baseline = cosine-v1, provided features (the October 11 configuration), current = mean-v1, census features, both re-run on today's data over 5 profiles.

| Layer | Metric | Baseline | Current | Target | Pass? | Notes |
|---|---|---:|---:|---|:---:|---|
| Rec engine | Precision@3 | 0.13 | 0.53 | higher is better | ↑ |  |
| Rec engine | Precision@5 | 0.16 | 0.32 | higher is better | ↑ |  |
| Rec engine | MRR (full ranking) | 0.29 | 0.82 | higher is better | ↑ |  |
| Rec engine | Mean match score @3 | 0.71 | 0.91 | higher is better | — | cosine for baseline, requested-feature mean now: different scales, not compared |
| Rec engine | Budget filter pass rate | 100% | 100% | 100% | ✅ |  |
| MCP | Tool selection accuracy | — | pending | ≥ 90% | — | no Layer 2 report yet (outputs/routing_llm.json) |
| MCP | recommend arg accuracy | — | pending | ≥ 85% | — | no Layer 2 report yet (outputs/routing_llm.json) |
| LLM | Tool grounding rate | — | pending | ≥ 95% | — | no Layer 3 report yet (outputs/responses.json) |
| LLM | Refusal rate (prohibited) | — | pending | 100% | — | no Layer 3 report yet (outputs/responses.json) |
| LLM | Disclosure rate | — | pending | 100% | — | no Layer 3 report yet (outputs/responses.json) |
| NLP | Theme coverage @3 | 13% | 53% | higher is better | ↑ | topic match on demo snippets, not authentic reviews |
<!-- scorecard:end -->

-------|--------|--------------|-------------|-------|
| Rec engine | Precision@3 | | | |
| Rec engine | Mean cosine similarity | | | |
| MCP | Tool selection accuracy | | | |
| LLM | Tool grounding rate | | | |
| LLM | Refusal rate (prohibited) | | | |
| NLP | Theme coverage | | | |

---

## Iteration loop (tie metrics to months)

| Month | Focus | If weak… |
|-------|-------|----------|
| **September** | Layer 1 baseline | Fix features, weights, budget filter |
| **October** | Layer 1 + Layer 2 | Fix tool routing; add MCP |
| **November** | All layers | Fix grounding/refusals; final scorecard |

---

## Team deliverables (eval)

- [ ] Notebook or script that runs Layer 1 on `recommendation_profiles.json`
- [ ] Log of Layer 2 routing results on `agent_routing_prompts.json`
- [ ] Layer 3 grounding + refusal check on `prohibited_prompts.json`
- [ ] Completed scorecard in README with baseline vs. final

---

## Optional stretch

- Automate Precision@k in `eval/run_eval.py` (students implement)
- LLM-as-judge for grounding (with human spot-check)
- A/B: engine-only vs. engine+LLM for user trust (qualitative)

Reference metrics also listed in [Challenge-Project-Overview.md](Challenge-Project-Overview.md).
