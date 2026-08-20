# Responsible AI for Personalized Neighborhood Recommendations

**Break Through Tech AI Studio — Fall 2026**  
**Affiliated org (BTT submission):** Flow  
**Challenge Advisor:** Karla Reyes, AI Engineer @ Flow Miami ([k.reyes@outlook.com](mailto:k.reyes@outlook.com))

> **Independent project:** Concept and CA materials by **Karla Reyes, AI Engineer @ Flow Miami** — not a Flow corporate product. **Hosted by Challenge Advisor alone.** See **[ATTRIBUTION.md](ATTRIBUTION.md)**.

---

## The idea, in plain terms

**For newcomers:** You're moving to Miami — maybe from NYC — and need the **right neighborhood** and **living setup** (e.g. your own apartment with a **co-leaser** on the lease in Wynwood, Downtown, or Brickell — not a co-living facility).

**Illustrative business case:** A residential operator *could* use a **recommendation engine + LLM** to improve lease-up and retention. That scenario motivates the eval metrics — it is **not** a Flow-assigned product roadmap.

This project builds that engine: match users to **3–5 neighborhoods** from budget, household, housing preference, and lifestyle — with an MCP-backed LLM that explains results without inventing listings.

> **Student team:** Sections marked *(your team fills this in)* are for your portfolio. Start with [Challenge-Project-Overview.md](Challenge-Project-Overview.md).

---

## Example user stories

| Who | What they want | Illustrative operator impact |
|-----|----------------|------------------------------|
| **Couple from NYC** | Own apartment with a co-leaser | Faster lease decision → **occupancy** |
| **Solo mover** | Own studio/1BR, no roommates | Better initial fit → **renewal** likelihood |
| **Solo, wants community** | Co-living (optional path) | Fill appropriate inventory → **occupancy** |

---

## What you'll build

| Step | What happens |
|------|----------------|
| 1 | User enters budget, alone vs. with co-leaser, own apartment vs. co-living, and lifestyle priorities |
| 2 | Recommender ranks ZIP codes — prioritizing **own apartment** matches for couples and solo movers |
| 3 | NLP surfaces review themes (transit, social, co_living, etc.) |
| 4 | MCP server + agent answer only from tool outputs |

### Anchor neighborhoods (own apartment)

| Area | ZIP | Why newcomers like it |
|------|-----|------------------------|
| **Wynwood** | 33127 | Creative, walkable, social — good for couples who want energy |
| **Downtown Miami** | 33128 | Central, Metromover, easy commute |
| **Brickell** | 33130 | Towers, Metrorail, restaurants, young professional vibe |

Full details: [Challenge-Project-Overview.md](Challenge-Project-Overview.md)

---

## What's in this repo

| File or folder | What's inside |
|----------------|---------------|
| [Challenge-Project-Overview.md](Challenge-Project-Overview.md) | Full project brief |
| [ATTRIBUTION.md](ATTRIBUTION.md) | **Read first** — ownership & independence |
| [STAKEHOLDERS.md](STAKEHOLDERS.md) | Stakeholders & illustrative value prop |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Rec engine → MCP → LLM blueprint |
| [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) | Metrics to prove the stack works |
| [RESOURCES.md](RESOURCES.md) | Curated online resources |
| [eval/](eval/) | Starter test profiles and routing prompts |
| [data/](data/) | Starter dataset |
| [data_dictionary.md](data_dictionary.md) | Column definitions |
| [MCP_SETUP.md](MCP_SETUP.md) | MCP server guide |

**Reference prototype:** [Miami Newcomer Housing Explorer](https://github.com/karlarey/miami-newcomer-explorer)

---

## Get started locally

```bash
git clone https://github.com/Break-Through-Tech/Flow-Responsible_AI_Neighborhood_Recommendation.git
cd Flow-Responsible_AI_Neighborhood_Recommendation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Starter data is in [`data/`](data/). Key fields:

| File | Key columns |
|------|-------------|
| `area_features.csv` | ZIP scores + `co_living_friendly` |
| `area_options.csv` | `housing_preference` (`own_apartment` / `co_living`), `household` (`alone` / `with_co_leaser`) |
| `crowd_text_snippets.csv` | Review themes by ZIP |

---

## 👥 Team members *(your team fills this in)*

| Name | GitHub | What they worked on |
|------|--------|---------------------|
| | | |

---

## 🎯 Project highlights *(your team fills this in)*

---

## 📊 Data exploration *(your team fills this in)*

---

## 🧠 Model development *(your team fills this in)*

---

## 📈 Results *(your team fills this in)*

---

## 🚀 Next steps *(your team fills this in)*

---

## 📝 License

MIT License — confirm with Challenge Advisor before final submission.

---

## 🙏 Acknowledgements

- **Challenge Advisor:** Karla Reyes, AI Engineer @ Flow Miami
- **Program:** Break Through Tech AI Studio, Fall 2026
