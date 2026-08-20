# Responsible AI for Personalized Neighborhood Recommendations

**Company / Org (BTT submission):** Flow  
**Challenge Advisor:** Karla Reyes, AI Engineer @ Flow Miami · k.reyes@outlook.com  
**AI Studio Coach:** Harshini Donepudi, harshini.donepudi@breakthroughtech.org  
**Program:** Break Through Tech AI Studio — Fall 2026

> **Attribution:** The **concept, architecture, and Challenge Advisor materials** are **independent work by Karla Reyes, AI Engineer @ Flow Miami**. Flow is listed as the affiliated org on the BTT submission only; **this project is hosted by the Challenge Advisor alone**. See **[ATTRIBUTION.md](ATTRIBUTION.md)**.

---

## 🏢 Illustrative context — residential operators (e.g. Flow)

*This section describes how a **residential operator could** use a system like the one students will build. It is **not** a Flow corporate product plan or an assigned Flow initiative.*

Many operators care about **occupancy** and **renewals (retention)**. A grounded recommender could help prospects find the right fit faster — an **example** business case for this architecture:

| Business goal | What goes wrong today | How this project helps |
|---------------|----------------------|-------------------------|
| **Occupancy** | Prospects churn during a slow, confusing housing search | Personalize **3–5 neighborhood matches** faster → better fit → **lease signed sooner** |
| **Renewals / retention** | Bad initial match → unhappy residents → move out at renewal | Match newcomers to the **right area and living setup** upfront → higher satisfaction → **residents stay** |
| **Investor & lender confidence** | Hard to show differentiated, data-driven leasing | Responsible AI rec engine + LLM → measurable match quality → **stronger ops story** for capital partners |

**End users** are newcomers (e.g. moving from NYC with a co-leaser, wanting their own apartment in Wynwood, Downtown, or Brickell — not a co-living facility). An operator **could** deploy an engine like this for lease-up and retention. **PE and lenders** (in this illustrative story) evaluate portfolio metrics — they are not app users.

### What students build (technical goal)

A **recommendation / personalization engine** connected to an **LLM via MCP**:

```text
Prospect preferences → Rec engine (rank ZIPs) → MCP tools → LLM (explain results)
                              ↓
                    Better match → occupancy ↑, renewals ↑
```

**What we won't do:** steer people by race or family status, score individual tenants, or show fake listings as if they're real.

**Read next:** [STAKEHOLDERS.md](STAKEHOLDERS.md) (value proposition) · [ARCHITECTURE.md](ARCHITECTURE.md) (system design) · [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) (how to measure accuracy)

---

## 🎯 The Challenge

### The problem

For newcomers, housing search in Miami is overwhelming — listings are scattered and AI tools often invent facts. In an **illustrative operator scenario**, slow or mismatched search can hurt lease-up and retention. Your job is to build a **grounded personalization engine** that helps people find the right fit — with measurable quality via [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md).

### What you'll build

A **neighborhood recommender for Miami newcomers**.

**Primary use case:**  
*"I'm moving from NYC with a co-leaser. We want our own apartment on a private lease — not a co-living facility — in Wynwood, Downtown, or Brickell."*

> **Co-leaser vs. co-living:** A **co-leaser** shares *your* private lease (partner, friend, etc.). **Co-living** is a separate housing preference for shared/stranger roommate setups — not the same thing.

| Input | Options | Example |
|-------|---------|---------|
| **Household** | Alone or with co-leaser | With co-leaser |
| **Housing preference** | **Own apartment** or **co-living** | Own apartment |
| **Budget + lifestyle** | Rent max, transit, social, quiet, etc. | $2,500, transit + walkable |

| Preference | Meaning |
|------------|---------|
| **Own apartment** | Private unit on your lease — studio, 1BR, or 2BR. Alone or with a **co-leaser**. Not a co-living facility. |
| **Co-living** | Optional — shared housing / stranger roommates when you're alone and want that setup |

> User chooses household and preference. Never infer relationship status from demographics.

**Anchor neighborhoods (own apartment):**

| Neighborhood | ZIP |
|--------------|-----|
| **Wynwood** | 33127 |
| **Downtown Miami** | 33128 |
| **Brickell** | 33130 |

Your full system will:

1. Take **budget**, **household**, **housing preference**, and **lifestyle tags**
2. Recommend **3–5 ZIP codes** via ML similarity
3. Surface **review themes** from crowd text
4. Connect an **MCP-backed agent** (tool-grounded answers only)
5. **Label synthetic demos** and refuse harmful requests

### How we'll know it's working

Measure **three layers** — see [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) and starter tests in [`eval/`](eval/).

| Layer | Metric | Plain English |
|-------|--------|---------------|
| **1. Rec engine** | Precision@3 / @5 | Top ZIPs match advisor gold labels |
| **1. Rec engine** | Mean cosine similarity | Recommendations fit stated preferences |
| **2. MCP routing** | Tool selection accuracy | Agent calls `recommend` vs `area_stats` vs `ethics` correctly |
| **3. LLM** | Tool grounding rate | Answers cite tool JSON only — no invented facts |
| **3. LLM** | Refusal rate | Prohibited prompts refused ([eval/prohibited_prompts.json](eval/prohibited_prompts.json)) |
| **NLP** | Theme coverage | Recommended ZIPs have relevant review themes |

### Use metrics to improve — not just to report

Don't wait until November to check these. Use them like a GPS:

| When | What to do | If results are weak… |
|------|------------|----------------------|
| **September** | Build a simple baseline recommender | — |
| **Early October** | Swap in stronger public data (Census, Zillow indices) | Recommendations feel random → upgrade features |
| **Mid October** | Tune weights, filters, similarity approach | Top picks all look the same → adjust model |
| **Late October** | Add NLP themes + MCP tools + agent | Agent makes up stats → enforce tool-only answers |
| **November** | Test edge cases and fair-housing refusals | Agent says yes to bad requests → tighten ethics layer |
| **End of semester** | Compare baseline vs. final; write it up in README | — |

### Monthly milestones

| Month | Focus | Your main tasks |
|-------|-------|-----------------|
| **September** | Understand the data | Explore CSVs, note what's real vs. demo, handle missing values, get a baseline score |
| **October** | Build and improve the model | Better public data, recommender tuning, NLP themes, **MCP server** |
| **November** | Evaluate and present | Run full [eval/](eval/) scorecard; presentation + README |

> **Tip:** Create a GitHub Projects board in this repo. Add columns for September, October, and November. Break big tasks into weekly to-dos.

---

## 📊 Dataset

**Source:** Public Miami-Dade snapshots (Census, migration, rent indices) + starter demo files  
**Format:** CSV  
**Size:** Under 1 GB — easy to work with in Colab or locally  
**Where:** [`data/`](data) folder in this repo

### Real data vs. demo data — why both?

| File | Real or demo? | Why it's here |
|------|---------------|---------------|
| `miami_dade_public_features.csv` | **Real** | Actual public stats by ZIP — rent, population, migration |
| `miami_dade_zctas.txt` | **Real** | List of Miami-Dade ZIP codes |
| `area_features.csv` | **Mixed starter** | ZIP scores + `co_living_friendly`; anchor rows for **Wynwood (33127), Downtown (33128), Brickell (33130)** |
| `crowd_text_snippets.csv` | **Demo** | Review themes including transit, social, co_living |
| `area_options.csv` | **Synthetic only** | `housing_preference` (`own_apartment` / `co_living`), `household` (`alone` / `with_co_leaser`) — **NOT REAL LISTINGS** |

**The plan:** Start with this mix so you can build fast. Over the semester, replace demo pieces with stronger public sources. The recommender should lean more on real data as you go.

### Good to know

- Everything is **snapshots** — not live Zillow feeds or scraped listings
- Some Census values show as `-666666666` when data is missing; decide how to handle that in cleaning
- Any UI showing `area_options.csv` must say clearly that cards are demos
- Column details: [`data_dictionary.md`](data_dictionary.md)

### Data upgrades for October

- [Census API](https://www.census.gov/data/developers/data-sets.html) — fresher ACS pulls
- [Zillow Research data](https://www.zillow.com/research/data/) — rent and home-value indices
- [Kaggle apartment reviews](https://www.kaggle.com/datasets/teejmahis/apartment-reviews-on-googlemaps) — real review text filtered for Miami/FL

---

## 🛠️ Suggested tools

| Tool | What you'll use it for |
|------|------------------------|
| **Python** | Everything |
| **pandas + scikit-learn** | Data prep and similarity-based recommendations |
| **NLP** | Pulling themes from review text |
| **Streamlit** | Simple demo app for users |
| **Gemini + MCP** | AI agent that calls your tools (Gemini key optional) |
| **Docker** | Optional — for reproducible deployment |

---

## 🔌 MCP server — what it is and why you need it

**MCP (Model Context Protocol)** is a standard way for an AI agent to call your code — like giving it a fixed set of reliable functions instead of letting it guess.

Your team will build an MCP server with **five tools**:

| Tool | What it does |
|------|--------------|
| `schema` | "Here are the columns in our dataset." |
| `area_stats` | "Here are the stats for this ZIP (or all ZIPs)." |
| `crowd_themes` | "Here's what people say about transit, quiet, etc. in this ZIP." |
| `recommend` | "Given budget, household, housing preference, and lifestyle tags — top neighborhoods." |
| `ethics` | "Here's what this tool is allowed and not allowed to do." |

**Why it matters:** If the agent can only speak through these tools, it's much harder for it to invent a $1,200 Brickell apartment that doesn't exist. That's your **tool grounding rate**.

**See it working:** [Miami Newcomer Housing Explorer](https://github.com/karlarey/miami-newcomer-explorer)  
**Setup guide:** [MCP_SETUP.md](MCP_SETUP.md)

---

## 🛡️ Responsible AI — non-negotiables

- **Neighborhoods, not people** — recommend areas, never score tenants or applicants
- **User picks preferences** — no steering by race, ethnicity, or family status
- **Label fake listings** — `area_options.csv` is for demos only
- **No live scraping** — use public snapshots, not real-time rental site crawlers
- **Say no when you should** — refuse tenant scoring, demographic filtering, or anything that breaks fair housing spirit

---

## 📚 Online resources

Full curated list: **[RESOURCES.md](RESOURCES.md)** — Miami data, ML/rec-sys, NLP, MCP/LLM, responsible AI, proptech context, and collaboration tools.

**Start here:**
- [STAKEHOLDERS.md](STAKEHOLDERS.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md)
- [Miami Newcomer Housing Explorer](https://github.com/karlarey/miami-newcomer-explorer) (reference code)
- [Census ACS](https://www.census.gov/programs-surveys/acs) · [Zillow Research](https://www.zillow.com/research/data/) · [MCP docs](https://modelcontextprotocol.io/)

---

## 🤝 Working together

**Check-ins:** Biweekly during AI Studio Lab (2nd and 4th week of each month)  
**Chat:** Discord (Break Through Tech workspace)  
**I'll reply within:** 48 hours on weekdays  

**Tools we recommend:** Google Colab or local Python, GitHub, Notion, Zoom/Meet

---

## 🚀 Your first week

1. Read this doc and write down questions
2. Open the [`data/`](data) folder and skim the CSVs
3. Create your GitHub Projects board
4. Build a simple baseline recommender and record your first scores
5. Read [MCP_SETUP.md](MCP_SETUP.md) and try the reference prototype

Looking forward to working with you!

---

## ❓ Questions?

Bring them to our first meeting — week of **August 24th** (Bridge to Studio, Session C).

---
