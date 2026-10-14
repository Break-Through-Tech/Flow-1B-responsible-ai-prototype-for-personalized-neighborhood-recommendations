"""Automatic growth of the tag list.

Proposed tags are counted across areas in data/nlp/tag_proposals.json.
Once a tag has been proposed for MIN_PROPOSALS different reviews, it is added to
tag_vocabulary.json and logged in data/nlp/tag_additions.jsonl.
"""

import json
from collections import Counter
from datetime import datetime, timezone

from .config import MIN_PROPOSALS, TAG_ADDITIONS_LOG, TAG_PROPOSALS
from .vocabulary import add_tag, find_existing, is_blocked


# ===========================================================================
# 1. Pending proposals (persist between runs)
# ===========================================================================
def load_ledger(path=TAG_PROPOSALS):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_ledger(ledger, path=TAG_PROPOSALS):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=1, sort_keys=True, ensure_ascii=False)


def record(ledger, proposals, zip_of):
    """Add (snippet_id, proposal) pairs to the ledger."""
    for sid, p in proposals:
        e = ledger.setdefault(p["tag"], {"snippet_ids": [], "zips": [], "parents": [],
                                         "descriptions": []})
        if sid in e["snippet_ids"]:
            continue
        e["snippet_ids"].append(sid)
        e["parents"].append(p.get("parent"))
        if zip_of.get(sid) and zip_of[sid] not in e["zips"]:
            e["zips"].append(zip_of[sid])
        if p.get("description") and len(e["descriptions"]) < 3:
            e["descriptions"].append(p["description"])


# ===========================================================================
# 2. Promote proposals into the tag list
# ===========================================================================
def promote(vocab, ledger, min_count=MIN_PROPOSALS, log_path=TAG_ADDITIONS_LOG):
    """Add every proposal with enough support. Returns the names added."""
    added = []
    for name in sorted(ledger):
        e = ledger[name]
        if is_blocked(name) or find_existing(vocab, name):
            del ledger[name]                      # now covered by an existing tag
            continue
        if len(e["snippet_ids"]) < min_count:
            continue
        votes = Counter(p for p in e["parents"] if p in vocab["tags"])
        parent = votes.most_common(1)[0][0] if votes else None
        description = e["descriptions"][0] if e["descriptions"] else ""
        version = add_tag(vocab, name, parent, description, source="auto")
        _log(log_path, {"tag": name, "parent": vocab["tags"][name]["parent"],
                        "description": description, "vocabulary_version": version,
                        "snippet_ids": e["snippet_ids"], "zips": e["zips"],
                        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        del ledger[name]
        added.append(name)
    return added


def _log(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
