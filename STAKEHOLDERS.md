# Stakeholders & Value Proposition

> **Note:** See [ATTRIBUTION.md](ATTRIBUTION.md). This project concept is **independent work by Challenge Advisor Karla Reyes, AI Engineer @ Flow Miami**. **Hosted by CA alone.** Flow appears as the BTT affiliated org only. “Operator” examples below are **illustrative**, not a Flow corporate initiative.

This project is a **recommendation / personalization engine** connected to an **LLM via MCP**.

---

## Stakeholder map

| Stakeholder | Role | Value proposition |
|-------------|------|-------------------|
| **Prospective residents** | End user | Find the right Miami neighborhood and living setup faster — without fake listings or AI guesswork |
| **Residential operator** *(illustrative)* | Example deployer | **Higher occupancy** and **renewals** if match quality improves |
| **Operator capital markets** *(illustrative)* | Reports to PE & lenders | Data-backed responsible AI story for portfolio performance |
| **PE investors** | Equity capital | Stronger occupancy + retention → better NOI narrative → confidence in the asset |
| **Lenders** | Debt capital | Predictable cash flow from stable occupancy and renewals → lower perceived risk |
| **Student team** | Builders | Portfolio artifact: rec engine + MCP + LLM + eval framework |
| **Challenge Advisor** | Karla Reyes, AI Engineer @ Flow Miami | BTT brief, data, architecture, eval for student team |

---

## Value proposition by stakeholder

### 1. Prospective residents (end users)

**Pain:** Moving to Miami is overwhelming — too many neighborhoods, unclear fit, untrustworthy AI answers.

**Value:**
- **3–5 personalized neighborhood recommendations** based on budget, household, and lifestyle
- **Own apartment** path (e.g. couple from NYC — Wynwood, Downtown, Brickell)
- **Conversational LLM** that explains *why* areas match — citing real tool data only
- **Responsible AI:** no demographic steering, no fake apartments

**Success looks like:** "I found areas that fit us in days, not weeks — and I trust the answers."

---

### 2. Residential operator *(illustrative use case)*

**Pain:** Slow or mismatched searches → lost prospects (vacancy) and unhappy residents who leave at renewal.

**Value (example):**

| Metric | How this system helps |
|--------|------------------------|
| **Occupancy** | Better personalization → prospects commit to a lease faster |
| **Renewals / retention** | Right neighborhood + living setup upfront → residents satisfied long-term |
| **Leasing efficiency** | LLM handles exploratory questions; rec engine does ranking — scalable onboarding |
| **Brand trust** | Grounded AI (MCP tools) vs. competitors with hallucinating chatbots |

**Success looks like:** Higher conversion from inquiry → lease, and improved renewal rates in matched cohorts.

---

### 3. PE investors *(illustrative)*

**Pain:** Need proof that an operator runs the portfolio efficiently.

**Value (example):**
- Differentiation via measurable AI personalization — if deployed
- Operational metrics story for due diligence

**They don't use the app.** They evaluate occupancy, renewal rates, and NOI.

---

### 4. Lenders *(illustrative)*

**Pain:** Underwriting depends on stable occupancy and rental income.

**Value (example):** Lower vacancy risk when prospects match communities faster.

---

### 5. Student team

**Value:**
- Real-world architecture: **rec engine → MCP → LLM**
- Responsible AI constraints (grounding, refusals)
- Eval framework to prove the **whole stack** works — not just a demo
- Portfolio piece for AI Studio

---

## Why the value proposition matters for your build

If the architecture is wrong, stakeholders lose trust:

| Failure | Who gets hurt |
|---------|---------------|
| Bad recommendations | Residents + operator occupancy *(if deployed)* |
| LLM invents listings | Everyone — legal/reputation risk |
| Wrong tool routing | Broken user experience |
| No refusals on bad requests | Fair housing exposure for any deployer |

That's why we include **[EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md)** — students must **measure** accuracy at every layer, not just demo a chatbot.

---

## One-line pitch

> **For residents:** the right Miami neighborhood, explained clearly.  
> **For operators *(example)*:** better matches could support occupancy and renewals.  
> **For PE/lenders *(example)*:** portfolio metrics backed by measurable, responsible AI.

See also: [ATTRIBUTION.md](ATTRIBUTION.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [EVAL_FRAMEWORK.md](EVAL_FRAMEWORK.md)
