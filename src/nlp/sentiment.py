"""Part 1 - Sentiment (keywords + VADER), for internal flags.

Each clause is routed by keyword:
  - mentions rent/price  -> RENT sentiment  (is it affordable?)
  - anything else        -> AREA sentiment  (how do people feel about the place?)
VADER scores the clause, with domain words added (e.g. "noise", "pricey").
Clauses about safety/crime are skipped and marked needs_review.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .config import (AREA_LEXICON, NEGATIVE_AT, POSITIVE_AT, RENT_KEYWORDS,
                     RENT_LEXICON, SENSITIVE_TERMS)
from .text_rules import find_terms, normalize, split_clauses


# ===========================================================================
# 1. Analyzers (one per aspect, so "high" is only negative when about rent)
# ===========================================================================
def _analyzer(extra):
    a = SentimentIntensityAnalyzer()
    a.lexicon.update(extra)
    return a


_RENT = _analyzer(RENT_LEXICON)
_AREA = _analyzer(AREA_LEXICON)


def label(score):
    if score >= POSITIVE_AT:
        return "positive"
    if score <= NEGATIVE_AT:
        return "negative"
    return "neutral"


# ===========================================================================
# 2. Clause routing and scoring
# ===========================================================================
def score_clauses(text):
    """[{clause, aspect, score, label, keywords}] for each clause in the text."""
    out = []
    for clause in split_clauses(normalize(text)):
        if find_terms(clause, SENSITIVE_TERMS):
            out.append({"clause": clause, "aspect": "needs_review", "score": None,
                        "label": None, "keywords": []})
            continue
        rent_hits = find_terms(clause, RENT_KEYWORDS)
        aspect = "rent" if rent_hits else "area"
        analyzer = _RENT if rent_hits else _AREA
        score = analyzer.polarity_scores(clause)["compound"]
        out.append({"clause": clause, "aspect": aspect, "score": round(score, 3),
                    "label": label(score), "keywords": sorted({t for t, _, _ in rent_hits})})
    return out


def combine(labels):
    """positive + negative -> mixed; neutral is ignored unless nothing else."""
    s = set(labels)
    if {"positive", "negative"} <= s:
        return "mixed"
    for l in ("positive", "negative", "neutral"):
        if l in s:
            return l
    return "not_mentioned"


# ===========================================================================
# 3. Snippet-level result
# ===========================================================================
def analyze(text):
    """{"rent": {...}, "area": {...}, "needs_review": bool, "clauses": [...]}"""
    clauses = score_clauses(text)
    result = {"clauses": clauses,
              "needs_review": any(c["aspect"] == "needs_review" for c in clauses)}
    for aspect in ("rent", "area"):
        cs = [c for c in clauses if c["aspect"] == aspect]
        scores = [c["score"] for c in cs]
        result[aspect] = {
            "label": combine([c["label"] for c in cs]),
            "score": round(sum(scores) / len(scores), 3) if scores else None,
        }
    return result
