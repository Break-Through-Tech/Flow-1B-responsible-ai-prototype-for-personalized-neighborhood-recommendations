"""Run both parts on the review snippets.

python -m src.nlp.pipeline             # sentiment + tags (Gemini only for uncached text)
python -m src.nlp.pipeline --offline   # sentiment + cached tags, no API calls
"""

import argparse
import csv
from collections import defaultdict

from .config import (DEFAULT_SNIPPETS, LLM_CACHE, LLM_MODEL, LOCATION_TAGS,
                     TAG_ADDITIONS_LOG, TAG_PROPOSALS)
from .growth import load_ledger, promote, record, save_ledger
from .sentiment import analyze
from .tag_index import build_index, load_index, save_index, similar_zips, tags_for_zip
from .tagging import get_client, tag_snippets
from .vocabulary import load_vocabulary, save_vocabulary

SCHEMA_VERSION = "nlp-0.3"


# ===========================================================================
# 1. Load
# ===========================================================================
def _zip5(value):
    value = str(value or "").strip()
    return value if value.isdigit() and len(value) == 5 else None


def load_snippets(path=DEFAULT_SNIPPETS, is_demo=True):
    """Raw snippet CSV -> list of dicts. Rows without a valid ZIP or text are skipped."""
    rows, seen = [], set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            z, text = _zip5(r.get("zip")), (r.get("text") or "").strip()
            if not z or not text or (z, text.lower()) in seen:
                continue
            seen.add((z, text.lower()))
            rows.append({"snippet_id": r.get("snippet_id", ""), "zip": z,
                         "source": r.get("source") or "unknown", "text": text,
                         "is_demo": is_demo})
    return rows


# ===========================================================================
# 2. Sentiment -> internal flags
# ===========================================================================
def sentiment_records(snippets):
    out = []
    for s in snippets:
        a = analyze(s["text"])
        out.append({"snippet_id": s["snippet_id"], "zip": s["zip"], "text": s["text"],
                    "rent": a["rent"]["label"], "rent_score": a["rent"]["score"],
                    "area": a["area"]["label"], "area_score": a["area"]["score"],
                    "needs_review": a["needs_review"]})
    return out


def internal_flags(records):
    """One flag per ZIP and reason: rent_negative, area_negative, needs_review."""
    flags = defaultdict(list)
    for r in records:
        if r["rent"] in ("negative", "mixed"):
            flags[(r["zip"], "rent_negative")].append(r)
        if r["area"] in ("negative", "mixed"):
            flags[(r["zip"], "area_negative")].append(r)
        if r["needs_review"]:
            flags[(r["zip"], "needs_review")].append(r)
    return [{"zip": z, "flag": f, "snippet_ids": [r["snippet_id"] for r in rs],
             "texts": [r["text"] for r in rs]}
            for (z, f), rs in sorted(flags.items())]


# ===========================================================================
# 3. Tags -> shared location index (area by area; the tag list grows as it goes)
# ===========================================================================
def build_location_tags(snippets, client=None, offline=False, grow=True, backfill=True,
                        save=True, vocab=None, cache_path=LLM_CACHE,
                        ledger_path=TAG_PROPOSALS, log_path=TAG_ADDITIONS_LOG,
                        progress=None):
    vocab = vocab or load_vocabulary()
    ledger = load_ledger(ledger_path)
    zip_of = {s["snippet_id"]: s["zip"] for s in snippets}
    if not offline:
        client = client or get_client()

    by_zip = defaultdict(list)
    for s in snippets:
        by_zip[s["zip"]].append(s)

    tagged, errors, added = {}, [], []
    for n, (z, area) in enumerate(by_zip.items(), 1):
        if progress:
            progress(f"  tagging {z} ({n}/{len(by_zip)}, {len(area)} reviews)")
        res = tag_snippets(area, client=client, vocab=vocab, cache_path=cache_path,
                           offline=offline or client is None)
        tagged.update(res["tags"])
        errors += res["errors"]
        if grow:
            record(ledger, res["proposals"], zip_of)
            new = promote(vocab, ledger, log_path=log_path)
            if new:
                added += new
                if save:
                    save_vocabulary(vocab)

    # Backfill: re-check reviews tagged before the latest tags were added.
    backfilled = []
    if backfill and added and client is not None:
        stale = [s for s in snippets
                 if int(tagged.get(s["snippet_id"], {}).get("vocabulary_version", 0)) < vocab["version"]]
        res = tag_snippets(stale, client=client, vocab=vocab, cache_path=cache_path,
                           min_vocab_version=vocab["version"])
        tagged.update(res["tags"])
        errors += res["errors"]
        record(ledger, res["proposals"], zip_of)          # counted, promoted on the next run
        backfilled = [s["snippet_id"] for s in stale]

    if save and grow:
        save_ledger(ledger, ledger_path)
    if client is None and not offline:
        errors.append("GEMINI_API_KEY not set; only cached tags used.")

    index = build_index(snippets, tagged, vocab, LLM_MODEL)
    if save and tagged:
        save_index(index)
    return index, {"tags": tagged, "errors": sorted(set(errors)), "added": added,
                   "backfilled": backfilled, "pending": ledger, "vocab": vocab}


# ===========================================================================
# 4. Tool-facing function (crowd_themes MCP tool): tags + quotes, no sentiment
# ===========================================================================
def crowd_themes(zip_code, tags=None, index=None):
    z = _zip5(zip_code)
    if z is None:
        return {"schema_version": SCHEMA_VERSION, "status": "invalid_zip",
                "zip": str(zip_code), "tags": []}
    if index is None:
        try:
            index = load_index()
        except FileNotFoundError:
            return {"schema_version": SCHEMA_VERSION, "status": "not_built", "zip": z,
                    "tags": [], "note": f"Run python -m src.nlp.pipeline to build {LOCATION_TAGS.name}."}
    loc = index["locations"].get(z)
    names = [t for t in tags_for_zip(index, z) if not tags or t in tags]
    if not loc or not names:
        return {"schema_version": SCHEMA_VERSION, "status": "no_evidence", "zip": z, "tags": [],
                "note": "No review text for this ZIP; this is unknown, not negative."}
    return {"schema_version": SCHEMA_VERSION, "status": "ok", "zip": z,
            "is_demo": loc["is_demo"], "snippet_count": loc["snippet_count"],
            "model": index["model"], "vocabulary_version": index["vocabulary_version"],
            "tags": [{"tag": t, **loc["tags"][t]} for t in names]}


# ===========================================================================
# 5. CLI report
# ===========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Sentiment + LLM tag report")
    ap.add_argument("--snippets", default=str(DEFAULT_SNIPPETS))
    ap.add_argument("--offline", action="store_true", help="no API calls; cached tags only")
    args = ap.parse_args(argv)

    snippets = load_snippets(args.snippets)
    records = sentiment_records(snippets)
    print(f"Snippets: {len(snippets)}\n\nSentiment (rent | area)")
    for r in records:
        print(f"  {r['snippet_id']:<4} {r['zip']}  {r['rent']:<13} {r['area']:<9} "
              f"{'REVIEW ' if r['needs_review'] else ''}{r['text'][:55]}")

    flags = internal_flags(records)
    print(f"\nInternal flags: {len(flags)}")
    for f in flags:
        print(f"  {f['zip']}  {f['flag']:<14} {', '.join(f['snippet_ids'])}")

    print("\nTagging (one Gemini call per new area, can take a minute)")
    index, result = build_location_tags(snippets, offline=args.offline,
                                        progress=lambda m: print(m, flush=True))
    vocab = result["vocab"]
    print(f"\nTags: {len(result['tags'])}/{len(snippets)} reviews tagged "
          f"| tag list v{vocab['version']}, {len(vocab['tags'])} tags")
    for e in result["errors"]:
        print(f"  note: {e}")
    for z in index["locations"]:
        broad = ", ".join(tags_for_zip(index, z, "parent")) or "(no tags)"
        specific = ", ".join(tags_for_zip(index, z, "specific"))
        print(f"  {z}  {broad}" + (f"  |  {specific}" if specific else ""))

    if result["added"]:
        print(f"\nAdded to tag list: {', '.join(result['added'])}")
    if result["backfilled"]:
        print(f"Re-checked with new tags: {len(result['backfilled'])} reviews")
    pending = {t: len(e["snippet_ids"]) for t, e in result["pending"].items()}
    if pending:
        print(f"Pending (need more reviews): {', '.join(f'{t} ({n})' for t, n in sorted(pending.items()))}")

    if index["locations"]:
        z = next(iter(index["locations"]))
        print(f"\nZIPs most similar to {z}: {similar_zips(index, z)}")
        print(f"Saved {LOCATION_TAGS.relative_to(LOCATION_TAGS.parents[2])}")


if __name__ == "__main__":
    main()
