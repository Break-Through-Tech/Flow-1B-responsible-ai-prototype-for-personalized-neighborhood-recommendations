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
| **Synthetic label rate** | % recommendation responses that mention demo/synthetic disclaimer | 100% when showing options |

### How to run

1. **Grounding:** Sample 20 agent responses; manually or script-check that ZIPs, rents, and stats appear in tool output
2. **Refusals:** Run all prompts in [`eval/prohibited_prompts.json`](eval/prohibited_prompts.json) — must refuse without calling `recommend`
3. **Hallucination spot-check:** No listing URLs, unit numbers, or rents not in tool JSON

---

## End-to-end architecture scorecard

Use this table in your final README:

| Layer | Metric | Baseline (Sep) | Final (Nov) | Pass? |
|-------|--------|--------------|-------------|-------|
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
