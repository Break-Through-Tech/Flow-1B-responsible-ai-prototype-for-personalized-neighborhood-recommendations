# NLP

This section tries to acheive two things: 

1. **Sentiment.** Is the rent good or bad, and is the area good or bad? Used to flag ZIPs or specific apartments for the internal team, to understand customer's satistifaction. Not shown to users, not used in ranking.
2. **Tags.** Gemini tags each review (beach, quiet, transit, ...). Tags are saved per ZIP so ZIPs can be compared and fed to the recommender.

## Sentiment

- Each review is split into clauses.
- If a clause mentions rent or price, it gets a rent score. Otherwise it gets an area score.
- Scoring is VADER plus extra words in `config.py` ("pricey", "noise", "loud").
- Clauses about safety or crime are not scored. They get `needs_review`.

## Tags

- Gemini picks tags from `tag_vocabulary.json`. It tags by meaning, so "five minutes from the sand" = `beach`.
- Two levels: broad tags (`transit`, `nightlife`) and specific tags under them (`metromover`, `after_work_scene`). Gemini uses the most specific one.
- A specific tag always counts for its parent too. ZIPs tagged `bars` and `live_music` both count as `nightlife`, so they still match.
- Each tag comes with a quote from the review.
- Output: `data/nlp/location_tags.json` (ZIP -> tags -> quotes).
- Do not rename the recommender tags: `transit, social, quiet, pet_friendly, walkable, co_living`.

## Tag list grows on its own

Reviews are tagged one area (ZIP) at a time.

1. Gemini proposes a tag when nothing in the list fits.
2. Proposals are counted in `data/nlp/tag_proposals.json`, across areas and runs.
3. Once a tag is proposed for 2 different reviews (`MIN_PROPOSALS`), it is added to `tag_vocabulary.json` and the next area uses it.
4. Every addition is logged in `data/nlp/tag_additions.jsonl`.
5. At the end, reviews tagged before the new tags existed are re-checked.

Dropped automatically: near-duplicates of existing tags (`metro_rail` = `metrorail`) and tags about people or safety. To remove a bad tag, delete it from `tag_vocabulary.json`.

Results are cached in `data/nlp/llm_tag_cache.json`, so the API is only called for new or outdated reviews.

## Files

| File | What it does |
|---|---|
| `config.py` | Paths, model name, word lists |
| `text_rules.py` | Clause splitting, keyword matching |
| `sentiment.py` | Rent / area sentiment |
| `tagging.py` | Gemini prompt, call, cache |
| `tag_vocabulary.json` | Tag list (parent -> specific) |
| `vocabulary.py` | Tag list loading, parents, duplicate check |
| `growth.py` | Counts proposals, adds tags automatically |
| `tag_index.py` | ZIP tag lookups, similar ZIPs |
| `pipeline.py` | Runs everything, `crowd_themes()` for MCP |
| `try_sentences.py` | Test your own sentences |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # add GEMINI_API_KEY
```

Model: `gemini-3.5-flash-lite`. Change with `NLP_LLM_MODEL`.

## Run

```bash
python -m src.nlp.pipeline              # full run
python -m src.nlp.pipeline --offline    # no API calls
python -m src.nlp.try_sentences         # sample sentences
python -m src.nlp.try_sentences "Rent is steep but the beach is close"
python -m unittest tests.test_nlp_themes -v   # no key needed
```

## Limits

- 20 demo reviews only.
- VADER misses some phrasing ("rent keeps going up"). Add words to `config.py`.
- If you change the prompt, bump `PROMPT_VERSION` in `tagging.py` so old tags are redone.
