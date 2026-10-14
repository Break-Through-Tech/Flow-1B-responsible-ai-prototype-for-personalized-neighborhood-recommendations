"""Tag list: two levels (broad parent -> specific tags). Grows automatically (see growth.py)."""

import difflib
import json
import re

from .config import BLOCKED_TAG_TERMS, MERGE_SIMILARITY, TAG_VOCABULARY


# ===========================================================================
# 1. Load / save
# ===========================================================================
def load_vocabulary(path=TAG_VOCABULARY):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_vocabulary(vocab, path=TAG_VOCABULARY):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ===========================================================================
# 2. Structure
# ===========================================================================
def parent_of(vocab, tag):
    return vocab["tags"].get(tag, {}).get("parent")


def parents(vocab):
    return [t for t, v in vocab["tags"].items() if not v.get("parent")]


def children(vocab, parent):
    return [t for t, v in vocab["tags"].items() if v.get("parent") == parent]


def with_parents(vocab, tags):
    """Tags plus their parents, no duplicates. A child always implies its parent."""
    out = []
    for t in tags:
        for name in (t, parent_of(vocab, t)):
            if name and name not in out:
                out.append(name)
    return out


def format_for_prompt(vocab):
    lines = []
    for p in parents(vocab):
        lines.append(f"- {p}: {vocab['tags'][p]['description']}")
        for c in children(vocab, p):
            lines.append(f"    - {c}: {vocab['tags'][c]['description']}")
    return "\n".join(lines)


# ===========================================================================
# 3. Names, duplicates, blocked tags
# ===========================================================================
def slug(tag):
    return re.sub(r"[^a-z0-9]+", "_", str(tag).lower()).strip("_")


def is_blocked(tag):
    return any(part.startswith(term) for part in slug(tag).split("_")
               for term in BLOCKED_TAG_TERMS)


def _singular(name):
    return "_".join(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in name.split("_"))


def find_existing(vocab, name):
    """Existing tag that `name` duplicates (same, plural, or near-identical spelling)."""
    s = slug(name)
    if s in vocab["tags"]:
        return s
    for t in vocab["tags"]:
        if _singular(t) == _singular(s):
            return t
    close = difflib.get_close_matches(s, list(vocab["tags"]), n=1, cutoff=MERGE_SIMILARITY)
    return close[0] if close else None


def add_tag(vocab, name, parent, description, source="auto"):
    """Add a tag and bump the version. Parent must be an existing top-level tag."""
    if parent and (parent not in vocab["tags"] or parent_of(vocab, parent)):
        parent = None
    vocab["tags"][name] = {"parent": parent, "source": source, "description": description}
    vocab["version"] = int(vocab["version"]) + 1
    return vocab["version"]
