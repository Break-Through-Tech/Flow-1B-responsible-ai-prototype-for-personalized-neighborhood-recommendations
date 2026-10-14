"""Shared text helpers: normalization, clause splitting, keyword matching."""

import re
from functools import lru_cache

# Sentiment is scored per clause, so "Rent is high but the area is great"
# gives one rent clause and one area clause.
CLAUSE_SPLIT = r"[;.!?—]|\bbut\b|\bthough\b|\balthough\b|\bhowever\b|\bwhile\b"
_SUFFIXES = r"(?:s|es|er|ers|ed|ing)?"


def normalize(text):
    text = (text or "").lower().replace("’", "'").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def split_clauses(text):
    parts = re.split(CLAUSE_SPLIT, text)
    return [p.strip(" ,") for p in parts if p and p.strip(" ,")]


@lru_cache(maxsize=None)
def _compile(term):
    """Word-boundary match; a trailing * matches any ending (afford* -> affordable)."""
    if term.endswith("*"):
        return re.compile(r"\b" + re.escape(term[:-1]) + r"[\w-]*")
    return re.compile(r"\b" + re.escape(term) + _SUFFIXES + r"\b")


def find_terms(text, terms):
    """[(term, start, end)] for each term found."""
    return [(t, m.start(), m.end()) for t in terms for m in _compile(t).finditer(text)]
