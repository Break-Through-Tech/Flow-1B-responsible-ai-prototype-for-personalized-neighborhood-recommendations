# Eval Fixtures

Starter test cases for [EVAL_FRAMEWORK.md](../EVAL_FRAMEWORK.md).

| File | Layer | Purpose |
|------|-------|---------|
| `recommendation_profiles.json` | 1 — Rec engine | User profiles + expected relevant ZIPs |
| `agent_routing_prompts.json` | 2 — Chatbot routing | Prompt → expected tool (+ args), and the map settings for the same intent |
| `agent_routing_prompts_map.json` | 2 — Chatbot routing | 50 map-app prompts by `category`: searches, map edits with prior filters, pin questions, UI-only actions, clarifications, refusals, injections, edge cases |
| `prohibited_prompts.json` | 3 — LLM refusals | Must refuse; no harmful compliance |

Layer 1 runs with `python -m flow_neighborhoods.evaluate`. Layers 2 and 3 are scored together from
one LLM run, and the scorecard in EVAL_FRAMEWORK.md is generated, not typed in:

```bash
python -m flow_neighborhoods.scorecard --run-llm --update-docs                         # live (GEMINI_API_KEY)
python -m flow_neighborhoods.scorecard --log eval/logs/llm_<model>.json --update-docs  # offline re-score
```

| File | Written by | Commit? |
|---|---|---|
| `eval/logs/llm_<model>.json` | the live run: every prompt in all three fixture files, with tool calls, tool results and answers | yes, so the run can be re-scored |
| `outputs/routing.json` | Layer 2 report from that log | no (regenerated) |
| `outputs/responses.json` | Layer 3 report from that log | no (regenerated) |
| `outputs/scorecard.md` / `.json` | the scorecard | no; the table is copied into EVAL_FRAMEWORK.md |

## Layer 2 runner (draft)

Users get in two ways: a **chatbot** (an LLM calling the MCP tools) and a **filtered map**
(budget, household, housing and priorities set directly; shows the top 3–5 ZIPs). Only the
chatbot turns text into tool calls, so only the chatbot is scored here. The map has no
routing to get wrong. It is tested with ordinary contract tests that must pass every time,
not averaged into these rates.

The map serves as the answer key instead. A user who types their preferences should see
the same ZIPs as a user who sets them on the map.

`python -m flow_neighborhoods.routing` scores both routing files (or `--prompts FILE ...`) and writes
`outputs/routing.json` (`outputs/routing_placeholder.json` for the placeholder). The router is pluggable:

| `--router` | What it is |
|---|---|
| `llm [--model ID]` | **The Layer 2 result.** Gemini (same provider as `src/nlp`; default `gemini-3.5-flash-lite`, or set `ROUTER_LLM_MODEL`) at temperature 0, given the MCP server's real tool definitions and instructions plus `update_map`. Needs `GEMINI_API_KEY` in the environment or `.env`. Tools are read-only, so each call is run through the MCP server and the result is sent back to the model, up to 6 turns. This lets the agent read `ethics` and then call `recommend`. The run covers the Layer 3 prompts too and saves to `eval/logs/llm_<model>.json` (or `--save-log FILE`), the same log `responses.py` and the scorecard read. The log is written after every prompt. 429 and 5xx errors are retried with backoff. A prompt that still fails is recorded as `api_error` and listed in `not_logged`, and the run carries on. A bad key or an unknown model stops the run straight away. |
| `log [--log FILE]` | Replays recorded tool calls offline. The default is the `--model`'s `eval/logs/llm_<model>.json`. Also accepts a hand-written `{"R1": [{"name": "recommend", "args": {...}}], ...}`, where `"R3": []` means the agent called no tool. A prompt left out of the log is listed in `not_logged` and is not scored. |
| `placeholder` (default) | Keyword rules standing in for the LLM, so the harness can run without a key. It is **not** a Layer 2 result, and the scorecard ignores it. The rules were written for the first 7 prompts and miss many of the map prompts. |

```bash
python -m flow_neighborhoods.routing --router llm   # live run over all fixtures, saves the log
python -m flow_neighborhoods.routing --router log   # re-score eval/logs/llm_<model>.json offline
```

Fixture formats:

- One tool: `"expected_tool": "area_stats"` with flat `"expected_args"`.
- No tool, e.g. a steering prompt: `"expected_tool": null`.
- Several tools: `"expected_tools": ["area_stats", "crowd_themes"]` with `"expected_args"` keyed by tool name.
- `recommend` args the scorer checks: `budget_max`, `household`, `housing_preference`, `tags_contains`, `tags_excludes` (a removed filter must not be resent), `k` (3 when not sent), `weights` (an unsent weight counts as 1), and `near_contains` (compared by name). Any other key is rejected, so a check can't be skipped silently.
- `context` is app state the user didn't type: `previous_recommend` (the filters the map shows now) and `selected_zip` (the clicked pin). The LLM router sends it as a separate, labelled part of the message.
- `category`, `note` and `decision_needed` aren't scored. The summary's `by_category` reports tool accuracy for each category.
- `"map_filters"`: the map settings that express the same intent, e.g. `{"budget_max": 2500, "household": "with_co_leaser", "housing_preference": "own_apartment", "tags": ["transit", "walkable"], "k": 5}`. Allowed on prompts that expect `recommend` or `update_map`, and required for `update_map`. They must pass the `recommend` contract, with `k` 3–5 (3 if left out).
- `update_map` is the chatbot's action for setting the map's filters, e.g. "show the top 5 on the map". It runs in the app, not on the MCP server, and the name is a placeholder until the frontend defines it. Its `expected_args` is `{}` because it is checked against `map_filters`.

Scoring rules:

- **Routing** is correct when the set of tools called matches the expected set exactly. Missing tools and extra tools are both misses, and both are listed for each prompt.
- `ethics` is ignored unless it is expected, so a policy check before `recommend` doesn't count against routing. For the same reason, `null` passes when only `ethics` was called.
- **`recommend` arguments** need exact budget, household and housing values. The expected tags must be among the tags sent.
- The arguments must also pass the `recommend` input contract (`Request.parse`). This is stricter than EVAL_FRAMEWORK.md.
- If `recommend` is never called, its arguments count as wrong.
- **Other tools:** the expected keys must match exactly on the first call of that tool.
- **Map parity** (prompts with `map_filters` that expect `recommend`):
  - `request_match`: the chatbot's `recommend` arguments rank the same request as the map. Two requests match when they have the same budget, household and housing, the same preference vector, and the same places. Tag order, weights of 1, the `co_living` tag implied by co-living housing, and `k` don't count as differences.
  - `results_match`: the same status and the same ZIPs in the same order, compared over the shorter list, since the chat may show 3 where the map shows 5.
  - Reported as `map_parity_rate` and `map_results_parity_rate`. Parity is stricter than `recommend_arg_accuracy`: an extra tag passes the framework's subset rule but fails parity, because it changes the ranking.
- **`update_map` arguments** must pass the contract, keep `k` within 3–5, match `map_filters` (including `k` when the fixture gives one), and agree with the chatbot's own `recommend` call. A map that shows something other than what the chat described is a miss. Reported as `map_update_arg_accuracy`.
- The new rates have no targets yet. The team should set them.

Not covered yet:

- Map contract tests. No map code exists. When it does, test that each filter state produces the matching `recommend` request through the same `tools.recommend` path the chatbot uses.
- Follow-ups such as "now show those on the map". Every fixture is a single turn, so the harness can't test them.
