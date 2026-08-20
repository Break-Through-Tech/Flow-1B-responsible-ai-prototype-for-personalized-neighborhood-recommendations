# Online Resources

Curated links for the Fall 2026 AI Studio team. Start with **Architecture** and **Eval** docs, then explore by topic.

| Project doc | Link |
|-------------|------|
| Stakeholders & value prop | [STAKEHOLDERS.md](STAKEHOLDERS.md) |
| System architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Evaluation metrics | [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) |
| MCP setup | [MCP_SETUP.md](MCP_SETUP.md) |
| Reference code | [Miami Newcomer Housing Explorer](https://github.com/karlarey/miami-newcomer-explorer) |

---

## Miami housing & neighborhood context

| Resource | Why it's useful |
|----------|-----------------|
| [Census ACS overview](https://www.census.gov/programs-surveys/acs) | Understand population, rent, migration fields in public data |
| [Census API](https://www.census.gov/data/developers/data-sets.html) | Refresh Miami-Dade ZIP-level features (October upgrade) |
| [Zillow Research data](https://www.zillow.com/research/data/) | Rent and home-value indices by geography |
| [HUD Fair Housing Act overview](https://www.hud.gov/helping-americans/fair-housing-act-overview) | Responsible AI guardrails for housing recommendations |
| [CFPB renting resources](https://www.consumerfinance.gov/consumer-tools/renting/) | Questions newcomers should ask — good LLM response content |

---

## Recommendation systems & ML

| Resource | Why it's useful |
|----------|-----------------|
| [scikit-learn: cosine similarity](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html) | Core ranking metric for this project |
| [Google ML Crash Course: Classification](https://developers.google.com/machine-learning/crash-course/classification/video-lecture) | ML foundations refresher |
| [Precision and recall (Google)](https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall) | Precision@k eval concepts |
| [Surprise library docs](https://surprise.readthedocs.io/) | Optional: explore classic rec-sys patterns |
| [Google Colab](https://colab.research.google.com/) | Free notebook environment for the team |

---

## NLP & review text

| Resource | Why it's useful |
|----------|-----------------|
| [Kaggle: Apartment reviews](https://www.kaggle.com/datasets/teejmahis/apartment-reviews-on-googlemaps) | Replace demo crowd text with real reviews (filter Miami/FL) |
| [spaCy beginner guide](https://spacy.io/usage/linguistic-features) | Optional theme extraction from review text |
| [NLTK book (free)](https://www.nltk.org/book/) | Text processing basics |

---

## LLM, MCP & agent grounding

| Resource | Why it's useful |
|----------|-----------------|
| [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) | Standard for exposing tools to agents |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Build your MCP server |
| [Google Gemini API quickstart](https://ai.google.dev/gemini-api/docs/quickstart) | Optional live agent |
| [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling) | Tool routing patterns |
| [Prompting guide (Google)](https://ai.google.dev/gemini-api/docs/prompting-intro) | Keep LLM responses grounded |

---

## Responsible AI & evaluation

| Resource | Why it's useful |
|----------|-----------------|
| [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) | Framework for trustworthy AI |
| [NIST Generative AI Profile](https://www.nist.gov/itl/ai-risk-management-framework/generative-ai-profile) | LLM-specific risks (hallucination, misuse) |
| [Partnership on AI — synthetic media](https://partnershiponai.org/) | Broader responsible AI context |
| Project [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) | **Required** — your metric definitions |
| Project [eval/](eval/) fixtures | Gold labels for Precision@k and routing tests |

---

## Proptech, multifamily & business context (Flow)

| Resource | Why it's useful |
|----------|-----------------|
| [NMHC industry basics](https://www.nmhc.org/research-insight/) | Multifamily occupancy & retention context |
| [NAA education (National Apartment Association)](https://www.naahq.org/education) | Leasing operations vocabulary |
| Project [STAKEHOLDERS.md](STAKEHOLDERS.md) | **Required** — why Flow cares about occupancy & renewals |

*Note:* Flow-specific internal metrics are documented in the project brief; public industry reports help students understand **why** match quality affects occupancy and renewals.

---

## Tools & collaboration

| Resource | Why it's useful |
|----------|-----------------|
| [GitHub Docs — get started](https://docs.github.com/en/get-started) | Git basics for the team |
| [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) | Track Sep–Nov milestones |
| [Streamlit docs](https://docs.streamlit.io/) | Optional demo UI |
| [pandas docs](https://pandas.pydata.org/docs/) | Data exploration |
| [Break Through Tech AI Studio template projects](https://github.com/Break-Through-Tech) | Other challenge project examples |

---

## Suggested reading order (first two weeks)

1. [STAKEHOLDERS.md](STAKEHOLDERS.md) — why this matters for Flow
2. [ARCHITECTURE.md](ARCHITECTURE.md) — rec engine → MCP → LLM
3. [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md) — how you'll prove it works
4. [Reference prototype](https://github.com/karlarey/miami-newcomer-explorer) — see a working example
5. Census + Zillow links — understand your data sources
6. MCP + Gemini docs — when you build the agent layer (October)

---

*Found something helpful? Add it to your team README references section.*
