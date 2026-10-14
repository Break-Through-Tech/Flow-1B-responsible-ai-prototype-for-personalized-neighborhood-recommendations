"""Shared ZIP -> tags repository.

Built from LLM tags, so two ZIPs whose reviews use different words
("near the sand" / "beach culture") still share the tag `beach` and can be matched.
Specific tags roll up to their parent: a ZIP tagged `bars` also counts as `nightlife`,
so ZIPs tagged `bars` and `live_music` match on `nightlife`.
"""

import json

from .config import LOCATION_TAGS
from .vocabulary import parent_of, with_parents


# ===========================================================================
# 1. Build / save / load
# ===========================================================================
def build_index(snippets, tagged, vocab, model):
    locations = {}
    for s in snippets:
        entry = tagged.get(s["snippet_id"])
        if entry is None:
            continue
        loc = locations.setdefault(s["zip"], {"snippet_count": 0, "is_demo": True, "tags": {}})
        loc["snippet_count"] += 1
        loc["is_demo"] = loc["is_demo"] and s["is_demo"]
        counted = set()                       # count each tag once per review
        for t in entry["tags"]:
            for name in with_parents(vocab, [t["tag"]]):
                rec = loc["tags"].setdefault(name, {
                    "level": "specific" if parent_of(vocab, name) else "parent",
                    "parent": parent_of(vocab, name), "count": 0, "evidence": []})
                if name not in counted:
                    rec["count"] += 1
                    counted.add(name)
                rec["evidence"].append({"snippet_id": s["snippet_id"], "quote": t["evidence"],
                                        "via": None if name == t["tag"] else t["tag"]})
    return {"vocabulary_version": vocab["version"], "model": model,
            "locations": dict(sorted(locations.items()))}


def save_index(index, path=LOCATION_TAGS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=1, ensure_ascii=False)


def load_index(path=LOCATION_TAGS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
# 2. Queries
# ===========================================================================
def tags_for_zip(index, zip_code, level=None):
    """Tag names for a ZIP, most frequent first. level: None, "parent" or "specific"."""
    tags = index["locations"].get(zip_code, {}).get("tags", {})
    names = [t for t in tags if level is None or tags[t].get("level") == level]
    return sorted(names, key=lambda t: (-tags[t]["count"], t))


def zips_with_tag(index, tag, min_count=1):
    hits = [(z, loc["tags"][tag]["count"]) for z, loc in index["locations"].items()
            if tag in loc["tags"] and loc["tags"][tag]["count"] >= min_count]
    return sorted(hits, key=lambda x: (-x[1], x[0]))


def similar_zips(index, zip_code, k=3):
    """Other ZIPs ranked by shared tags (Jaccard overlap, parents included)."""
    base = set(index["locations"].get(zip_code, {}).get("tags", {}))
    if not base:
        return []
    out = []
    for z, loc in index["locations"].items():
        other = set(loc["tags"])
        if z == zip_code or not other & base:
            continue
        out.append({"zip": z, "score": round(len(base & other) / len(base | other), 3),
                    "shared_tags": sorted(base & other)})
    return sorted(out, key=lambda r: (-r["score"], r["zip"]))[:k]


def tag_matrix(index, vocab_tags):
    """{zip: {tag: share of that ZIP's snippets with the tag}} for the recommender."""
    return {z: {t: round(loc["tags"].get(t, {}).get("count", 0) / loc["snippet_count"], 3)
                for t in vocab_tags}
            for z, loc in index["locations"].items()}
