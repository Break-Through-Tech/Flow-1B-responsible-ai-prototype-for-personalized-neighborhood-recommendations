"""See what comes out of sample (or your own) sentences.

Run:  python -m src.nlp.try_sentences                       # built-in samples
      python -m src.nlp.try_sentences "Your sentence here"   # your own
      python -m src.nlp.try_sentences -i                     # type sentences live
Sentiment always runs. Tags need GEMINI_API_KEY (or are skipped).
"""

import sys

from .sentiment import analyze
from .config import REPO_ROOT
from .tagging import get_client, tag_snippets

# Samples use their own cache so they don't end up in the shared data/nlp cache.
SAMPLE_CACHE = REPO_ROOT / "outputs" / "try_sentences_cache.json"

# (sentence, expected rent, expected area). Also used by the unit tests.
SENTIMENT_SAMPLES = [
    ("Rent is high but the neighborhood is great.",          "negative", "positive"),
    ("Rent is reasonable for the location.",                 "positive", "not_mentioned"),
    ("The rent is not cheap.",                               "negative", "not_mentioned"),
    ("Rent increased again this year.",                      "negative", "not_mentioned"),
    ("Affordable compared to Brickell; research blocks carefully.", "positive", "negative"),
    ("Metrorail nearby made commuting easy without a car.",  "not_mentioned", "positive"),
    ("Busy area; street noise is real in some towers.",      "not_mentioned", "negative"),
    ("Not quiet at all.",                                    "not_mentioned", "negative"),
    ("Lots of events; can be loud on weekends.",             "not_mentioned", "mixed"),
    ("Too much traffic and flooding.",                       "not_mentioned", "negative"),
    ("Lots of houses and tree-lined blocks.",                "not_mentioned", "neutral"),
    ("Felt unsafe at night.",                                "not_mentioned", "not_mentioned"),  # needs_review
]

# For tags: none of these use the tag word itself.
TAG_SAMPLES = [
    "Five minutes from the sand and the ocean breeze.",        # beach
    "You can grab coffee, groceries and dinner without driving.",  # walkable, food_scene
    "Neighbors know each other by name.",                       # community
    "Hard to sleep with the bars right downstairs.",            # noisy, nightlife
    "Metrorail nearby made commuting easy.",                    # transit
    # tricky cases the first prompt got wrong
    "Easy to get around without a car.",                        # transit, NOT car_needed
    "Quieter than tower living downtown.",                      # quiet, NOT high_rise
    "Affordable compared to Brickell.",                         # no tags (rent is sentiment's job)
]


def show(sentence, tags=None, expected=None):
    a = analyze(sentence)
    got = (a["rent"]["label"], a["area"]["label"])
    mark = "" if expected is None else ("  OK" if got == expected else f"  MISMATCH, expected {expected}")
    print(f'"{sentence}"{mark}')
    print(f"    rent: {a['rent']['label']:<13} area: {a['area']['label']:<9}"
          f"{'  needs_review' if a['needs_review'] else ''}")
    if tags is not None:
        names = ", ".join(f"{t['tag']} (\"{t['evidence']}\")" for t in tags.get("tags", []))
        print(f"    tags: {names or '(none)'}")
        if tags.get("proposed"):
            print(f"    proposed: {', '.join(p['tag'] for p in tags['proposed'])}")
    print()
    return expected is None or got == expected


def _tag_all(sentences):
    client = get_client()
    if client is None:
        print("(Tags skipped: set GEMINI_API_KEY in .env to see LLM tags.)\n")
        return {}
    snips = [{"snippet_id": f"S{i}", "text": s} for i, s in enumerate(sentences)]
    res = tag_snippets(snips, client=client, cache_path=SAMPLE_CACHE)
    for e in res["errors"]:
        print(f"(tagging error: {e})")
    return {s["text"]: res["tags"].get(s["snippet_id"], {}) for s in snips}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ["-i"]:
        print("Type a sentence (empty line to quit).")
        while (line := input("> ").strip()):
            show(line, _tag_all([line]).get(line))
        return
    if args:
        tags = _tag_all(args)
        for s in args:
            show(s, tags.get(s))
        return

    print("== Sentiment samples ==\n")
    ok = sum(show(s, expected=(r, a)) for s, r, a in SENTIMENT_SAMPLES)
    print(f"{ok}/{len(SENTIMENT_SAMPLES)} sentiment samples match\n")
    print("== Tag samples (meaning, not keywords) ==\n")
    tags = _tag_all(TAG_SAMPLES)
    if tags:
        for s in TAG_SAMPLES:
            show(s, tags.get(s))


if __name__ == "__main__":
    main()
