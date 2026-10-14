"""Paths, model settings, and sentiment lexicons. Edit rules here, not in the logic files."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
NLP_DATA_DIR = DATA_DIR / "nlp"

DEFAULT_SNIPPETS = DATA_DIR / "crowd_text_snippets.csv"      # raw: keeps text + ids
TAG_VOCABULARY = Path(__file__).with_name("tag_vocabulary.json")
LLM_CACHE = NLP_DATA_DIR / "llm_tag_cache.json"               # committed: same tags for everyone
LOCATION_TAGS = NLP_DATA_DIR / "location_tags.json"           # the shared ZIP -> tags repository
TAG_PROPOSALS = NLP_DATA_DIR / "tag_proposals.json"           # proposed tags not yet added
TAG_ADDITIONS_LOG = NLP_DATA_DIR / "tag_additions.jsonl"      # every auto-added tag

# ---------------------------------------------------------------------------
# 1. LLM tagging
# ---------------------------------------------------------------------------
LLM_MODEL = os.environ.get("NLP_LLM_MODEL", "gemini-3.5-flash-lite")
LLM_BATCH_SIZE = 10          # snippets per API call
LLM_TEMPERATURE = 0.0

# Tag list growth
MIN_PROPOSALS = 2        # a new tag is added once proposed for this many different reviews
MERGE_SIMILARITY = 0.85  # proposals this close in spelling to an existing tag are merged into it

# The recommender's lifestyle tags. These names must stay top-level and unchanged.
RECOMMENDER_TAGS = ["transit", "social", "quiet", "pet_friendly", "walkable", "co_living"]

# Tags must describe places, never people. Proposed tags containing these are dropped.
BLOCKED_TAG_TERMS = [
    "race", "racial", "ethnic", "hispanic", "latino",
    "jewish", "christian", "muslim", "religio", "immigrant", "family", "families",
    "kids", "children", "elderly", "senior", "disab", "gay", "lgbt",
    "safe", "unsafe", "crime", "dangerous", "sketchy", "ghetto",
]

# ---------------------------------------------------------------------------
# 2. Sentiment: aspect keywords
#    A clause with a rent keyword is scored as RENT; every other clause as AREA.
# ---------------------------------------------------------------------------
RENT_KEYWORDS = ["rent", "price*", "pricing", "afford*", "expensive", "cheap*",
                 "cost*", "pricey", "overpriced", "budget", "lease"]

# Clauses mentioning safety/crime are not scored (fair-housing steering risk);
# the snippet is marked needs_review instead.
SENSITIVE_TERMS = ["safe", "safety", "unsafe", "crime", "dangerous", "sketchy",
                   "ghetto", "shady", "rough"]

# ---------------------------------------------------------------------------
# 3. Sentiment: domain words added to VADER (VADER scale is about -4..+4)
# ---------------------------------------------------------------------------
RENT_LEXICON = {
    "high": -1.5, "higher": -1.5, "expensive": -2.0, "pricey": -1.8,
    "overpriced": -2.5, "steep": -1.5, "costly": -1.8, "spike": -1.5,
    "affordable": 2.0, "cheap": 1.5, "cheaper": 1.5, "reasonable": 1.5,
    "low": 1.2, "lower": 1.2, "deal": 1.2,
    "rising": -1.2, "increase": -1.2, "increased": -1.2, "hike": -1.5,
}
AREA_LEXICON = {
    "noise": -1.5, "noisy": -1.8, "loud": -1.5, "busy": -0.8, "crowded": -1.2,
    "traffic": -1.2, "construction": -1.0, "flooding": -1.8, "flood": -1.5,
    "isolating": -1.5, "carefully": -0.5,
    "quiet": 1.2, "quieter": 1.2, "calm": 1.5, "peaceful": 1.5,
    "walkable": 1.5, "walkability": 1.5, "convenient": 1.5, "central": 0.8,
    "community": 1.0, "connected": 1.0, "events": 0.5, "helped": 1.0, "plus": 1.0,
    "block": 0.0, "blocks": 0.0,   # VADER reads "blocks" as negative; here it means streets
}
# VADER's own cut-offs
POSITIVE_AT = 0.05
NEGATIVE_AT = -0.05
