# Eval Fixtures

Starter test cases for [EVAL_FRAMEWORK.md](../EVAL_FRAMEWORK.md).

| File | Layer | Purpose |
|------|-------|---------|
| `recommendation_profiles.json` | 1 — Rec engine | User profiles + expected relevant ZIPs |
| `agent_routing_prompts.json` | 2 — MCP routing | Prompt → expected tool (+ args) |
| `prohibited_prompts.json` | 3 — LLM refusals | Must refuse; no harmful compliance |

Students: implement runners in `notebooks/` or `src/eval/` and report results in your README.
