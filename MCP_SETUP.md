# MCP Server Setup

An **MCP server** lets your AI agent call your recommender and data functions directly — instead of guessing answers.

Think of it like a waiter who can only bring items from the kitchen menu. If it's not on the menu (your tools), the agent shouldn't serve it.

---

## The five tools you need to build

| Tool | You pass in… | You get back… |
|------|--------------|---------------|
| `schema` | Nothing | Column names and notes about each dataset |
| `area_stats` | A ZIP code (optional) | Public stats for that ZIP, or all ZIPs if blank |
| `crowd_themes` | A ZIP code | Review theme snippets (transit, quiet, social, etc.) |
| `recommend` | Budget, tags, `household` (`alone`/`with_co_leaser`), `housing_preference` (`own_apartment`/`co_living`), `k` | Top neighborhood matches |
| `ethics` | Nothing | Rules for fair, responsible use |

---

## See a working example

Karla's reference prototype has all of this already built:

**Repo:** https://github.com/karlarey/miami-newcomer-explorer

| File | What it does |
|------|--------------|
| `src/mcp_server.py` | Defines the five MCP tools |
| `src/tools.py` | Shared logic behind the tools |
| `src/recommender.py` | Cosine-similarity ranking |
| `src/nlp_themes.py` | Pulls themes from review text |

### Run it locally

```bash
git clone https://github.com/karlarey/miami-newcomer-explorer.git
cd miami-newcomer-explorer
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python src/mcp_server.py
```

Optional — for the Gemini agent (separate from MCP):

```bash
copy .env.example .env
# Add your GEMINI_API_KEY
```

---

## Connect in Cursor

Add this to your Cursor MCP settings (update the path to your project):

```json
{
  "mcpServers": {
    "miami-neighborhood-rec": {
      "command": "python",
      "args": ["src/mcp_server.py"],
      "cwd": "C:/path/to/your/project"
    }
  }
}
```

---

## Your team's deliverable (October)

By end of October, your team should:

1. Build your own MCP server using this repo's `data/` files
2. Confirm the agent only uses tool outputs (**tool grounding rate**)
3. Confirm bad requests get refused (**refusal rate**)
4. Document how to run your server in the team README

---

## Quick test checklist

- [ ] `schema` lists columns for all starter CSVs
- [ ] `recommend` returns 3–5 ZIPs for a sample budget + tags
- [ ] `crowd_themes` returns text for a ZIP you know exists
- [ ] `ethics` returns the fair-use rules
- [ ] Agent does **not** invent rents, listings, or neighborhoods when tools are available
