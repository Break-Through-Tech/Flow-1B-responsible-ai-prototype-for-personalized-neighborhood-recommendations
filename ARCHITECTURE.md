# System Architecture

**What you're building:** A recommendation engine hooked to an LLM — not a chatbot that guesses neighborhoods.

---

## High-level flow

```text
┌────────────────┐
│ Prospect / User│  natural language + preferences (budget, household, tags)
└───────┬────────┘
        ▼
┌────────────────┐
│   LLM Agent    │  explains results, refuses bad requests — DOES NOT rank ZIPs
│   (Gemini)     │
└───────┬────────┘
        │ calls tools only
        ▼
┌────────────────┐
│  MCP Server    │  schema, recommend, area_stats, crowd_themes, ethics
└───────┬────────┘
        │
        ├──────────────────┐
        ▼                  ▼
┌────────────────┐  ┌─────────────┐
│ Rec Engine     │  │ Data + NLP  │
│ (Python/ML)    │  │ CSV + themes│
│ cosine + filters│  └─────────────┘
└────────────────┘
```

---

## Layer responsibilities

| Layer | Owns | Must NOT do |
|-------|------|-------------|
| **Data** | ZIP features, review snippets, public stats | Live listing scrapes, PII |
| **Rec engine** | Rank 3–5 ZIPs from user preference vector | Natural language replies |
| **NLP** | Theme snippets per ZIP | Generate fake reviews |
| **MCP** | Expose tools with structured JSON I/O | Hide recommender logic from eval |
| **LLM** | Narrate tool outputs, ask clarifying questions | Invent rents, ZIPs, or listings |

**Golden rule:** Ranking happens in **Python**. The LLM **narrates** tool results.

---

## MCP tools (contract)

| Tool | When to call |
|------|--------------|
| `schema` | User asks about data columns or dataset structure |
| `recommend` | User wants area suggestions (budget + household + housing preference + tags) |
| `area_stats` | User asks about a specific ZIP or area statistics |
| `crowd_themes` | User asks what people say about a ZIP |
| `ethics` | User asks about limitations, fair housing, or prohibited uses |

Setup details: [MCP_SETUP.md](MCP_SETUP.md)

---

## Reference implementation

Study (do not copy blindly): [Miami Newcomer Housing Explorer](https://github.com/karlarey/miami-newcomer-explorer)

| File | Layer |
|------|-------|
| `src/recommender.py` | Rec engine |
| `src/tools.py` | Shared tool logic |
| `src/mcp_server.py` | MCP |
| `src/agent.py` | LLM integration |

**Your deliverable:** Implement your version in **this repo** with tests from [eval/](eval/) and metrics in [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md).

---

## Business link *(illustrative operator scenario)*

```text
Better rec match → faster lease (occupancy ↑) → happier resident → renewal (↑)
```

Not a Flow corporate initiative — **hosted by Challenge Advisor alone**. See [ATTRIBUTION.md](ATTRIBUTION.md).

Stakeholder detail: [STAKEHOLDERS.md](STAKEHOLDERS.md)

---

## Installation (quick start)

```bash
git clone https://github.com/Break-Through-Tech/Flow-Responsible_AI_Neighborhood_Recommendation.git
cd Flow-Responsible_AI_Neighborhood_Recommendation
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

1. Explore `data/` and [data_dictionary.md](data_dictionary.md)
2. Study reference prototype MCP server
3. Build `src/` in this repo (students)
4. Run eval fixtures in [eval/](eval/) (students)

Optional: `copy .env.example .env` and set `GEMINI_API_KEY` for live agent.
