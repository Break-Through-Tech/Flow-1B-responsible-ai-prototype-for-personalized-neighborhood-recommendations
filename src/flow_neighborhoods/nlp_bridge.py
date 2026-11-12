"""Optional link to the NLP package in src/nlp (Nadia, PR #15): sentiment for review snippets.

When the NLP extras (vaderSentiment) are installed, each snippet gets the area sentiment of
its text, so "Not quiet at night." tagged `quiet` reads as negative evidence. Without them,
polarity stays "unknown" and nothing else changes. Clauses about safety or crime are never
scored; they are marked needs_review, so the system does not characterize areas as safe or
unsafe.
"""

try:
    from nlp.sentiment import analyze
except ImportError:  # src/ not on the path, or vaderSentiment missing
    try:
        from src.nlp.sentiment import analyze
    except ImportError:
        analyze = None

EXTRACTOR = "nlp-v1: provided theme labels + VADER area sentiment (src/nlp)"
FALLBACK = "provided-label-lookup-v1"


def available() -> bool:
    return analyze is not None


def annotate(evidence: list[dict]) -> list[dict]:
    """Set polarity (positive / negative / mixed / neutral / not_mentioned / needs_review)
    and needs_review on each snippet dict, in place."""
    for item in evidence:
        if analyze is None:
            item["needs_review"] = False
            continue
        result = analyze(item["text"])
        item["needs_review"] = bool(result["needs_review"])
        item["polarity"] = "needs_review" if result["needs_review"] else result["area"]["label"]
    return evidence
