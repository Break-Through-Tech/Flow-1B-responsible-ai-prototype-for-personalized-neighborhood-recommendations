"""Part 2 - LLM tagging, for the recommender and the shared location-tag repository.

A small Gemini model picks tags from tag_vocabulary.json by meaning, not exact
words ("Metrorail nearby" -> metrorail). It uses the most specific tag that fits.
New tags it proposes are returned to growth.py, which adds them automatically.
Results are cached by (model, prompt version, text); each entry records the tag
list version it was tagged with, so older entries can be re-checked (backfill).
"""

import hashlib
import json
import os
import re

from .config import LLM_BATCH_SIZE, LLM_CACHE, LLM_MODEL, LLM_TEMPERATURE, REPO_ROOT
from .text_rules import normalize
from .vocabulary import (find_existing, format_for_prompt, is_blocked, load_vocabulary,
                         parent_of, slug)


class TaggingError(Exception):
    pass


# ===========================================================================
# 1. Prompt
# ===========================================================================
PROMPT_VERSION = "3"   # bump when the prompt changes; old cache entries are then ignored

PROMPT = """You tag short reviews of Miami neighborhoods.

Tags have two levels: broad tags, and specific tags indented under them.
Use the MOST SPECIFIC tag that fits: "Metromover right outside" -> metromover, not transit.
Judge by meaning, not exact words: "street noise" supports street_noise.

Rules:
- Only tag what is true of the reviewed place itself. Places mentioned as a
  comparison do not count: "quieter than tower living downtown" supports quiet,
  not high_rise; "affordable compared to Brickell" says nothing about centrality.
- Read negation and direction: "easy without a car" supports transit and means
  a car is NOT needed, so never car_needed.
- The evidence must directly show the tag. A vague word like "location" alone
  is not enough for central.
- Rent and prices are handled elsewhere: do not tag or propose price/affordability tags.
- Never tag or propose anything about people's race, ethnicity, religion, national
  origin, family status, age, disability, or safety/crime.

New tags: if the review shows a specific place feature that no tag covers, propose one:
{{"tag": "snake_case_name", "parent": "<broad tag it belongs under, or null>", "description": "<short>"}}
Reuse existing tags whenever one fits. Do not propose synonyms of existing tags.

Tags:
{tags}

Reviews (JSON):
{items}

Return only JSON in this shape:
{{"results": [{{"id": "<review id>", "tags": [{{"tag": "<tag>", "evidence": "<exact quote>"}}], "proposed": [{{"tag": "<name>", "parent": "<broad tag or null>", "description": "<short>"}}]}}]}}
"""


def build_prompt(batch, vocab):
    tags = format_for_prompt(vocab)
    items = json.dumps([{"id": s["snippet_id"], "text": s["text"]} for s in batch],
                       ensure_ascii=False)
    return PROMPT.format(tags=tags, items=items)


# ===========================================================================
# 2. Gemini client (any callable prompt -> str works, e.g. a fake in tests)
# ===========================================================================
def _api_key():
    key = os.environ.get("GEMINI_API_KEY")
    env_file = REPO_ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    return key if key and not key.startswith("your_") else None


class GeminiClient:
    def __init__(self, model=LLM_MODEL, api_key=None):
        key = api_key or _api_key()
        if not key:
            raise TaggingError("GEMINI_API_KEY is not set (env var or .env file).")
        from google import genai
        self._client = genai.Client(api_key=key)
        self.model = model

    def __call__(self, prompt):
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"temperature": LLM_TEMPERATURE,
                    "response_mime_type": "application/json"},
        )
        return resp.text


def get_client(model=LLM_MODEL):
    """GeminiClient, or None when no API key is configured."""
    try:
        return GeminiClient(model)
    except TaggingError:
        return None


# ===========================================================================
# 3. Validate the model's answer
# ===========================================================================
def _proposal(p, vocab):
    """Clean one proposal -> {tag, parent, description} or None."""
    if isinstance(p, str):
        p = {"tag": p}
    if not isinstance(p, dict):
        return None
    name = slug(p.get("tag", ""))
    if not name or is_blocked(name) or find_existing(vocab, name):
        return None
    parent = slug(p.get("parent") or "") or None
    if parent and parent in vocab["tags"]:
        parent = parent_of(vocab, parent) or parent      # always attach to a top-level tag
    else:
        parent = None
    return {"tag": name, "parent": parent, "description": str(p.get("description") or "")[:120]}


def parse_response(raw, batch, vocab):
    """{snippet_id: {"tags": [{tag, evidence, evidence_found}], "proposed": [{tag, parent, description}]}}"""
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip()).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise TaggingError(f"Model did not return JSON: {e}") from e
    items = data.get("results", []) if isinstance(data, dict) else data

    texts = {s["snippet_id"]: s["text"] for s in batch}
    out = {}
    for item in items if isinstance(items, list) else []:
        sid = str(item.get("id", ""))
        if sid not in texts:
            continue
        tags, raw_props = [], list(item.get("proposed") or [])
        for t in item.get("tags") or []:
            name = t.get("tag") if isinstance(t, dict) else t
            evidence = (t.get("evidence") if isinstance(t, dict) else "") or ""
            if name in vocab["tags"]:
                if name not in {x["tag"] for x in tags}:
                    tags.append({"tag": name, "evidence": evidence,
                                 "evidence_found": bool(evidence) and
                                 normalize(evidence) in normalize(texts[sid])})
            else:
                raw_props.append({"tag": name})
        proposed, seen = [], set()
        for p in raw_props:
            clean = _proposal(p, vocab)
            if clean and clean["tag"] not in seen:
                seen.add(clean["tag"])
                proposed.append(clean)
        out[sid] = {"tags": tags, "proposed": proposed}
    return out


# ===========================================================================
# 4. Cache
# ===========================================================================
def cache_key(text, model):
    raw = f"{model}|{PROMPT_VERSION}|{text.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_cache(path=LLM_CACHE):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(cache, path=LLM_CACHE):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1, sort_keys=True, ensure_ascii=False)


# ===========================================================================
# 5. Entry point
# ===========================================================================
def tag_snippets(snippets, client=None, vocab=None, model=LLM_MODEL,
                 cache_path=LLM_CACHE, offline=False, min_vocab_version=None):
    """Tag snippets, using the cache first.

    min_vocab_version: re-tag cached entries made with an older tag list (backfill).
    Returns {"tags": {id: entry}, "untagged": [ids], "errors": [msgs],
             "proposals": [(snippet_id, proposal)]}  (proposals only from fresh calls).
    """
    vocab = vocab or load_vocabulary()
    cache = load_cache(cache_path)
    tagged, todo = {}, []
    for s in snippets:
        hit = cache.get(cache_key(s["text"], model))
        stale = (hit and min_vocab_version is not None
                 and int(hit.get("vocabulary_version", 0)) < int(min_vocab_version))
        if hit and (not stale or offline):
            tagged[s["snippet_id"]] = hit
        else:
            todo.append(s)

    errors, proposals = [], []
    if todo and not offline:
        client = client or get_client(model)
        if client is None:
            errors.append("GEMINI_API_KEY not set; only cached tags used.")
        else:
            for i in range(0, len(todo), LLM_BATCH_SIZE):
                batch = todo[i:i + LLM_BATCH_SIZE]
                try:
                    parsed = parse_response(client(build_prompt(batch, vocab)), batch, vocab)
                except Exception as e:  # API/network/format problems: keep going
                    errors.append(f"batch {i // LLM_BATCH_SIZE}: {e}")
                    continue
                for s in batch:
                    if s["snippet_id"] in parsed:
                        entry = {**parsed[s["snippet_id"]], "model": model,
                                 "vocabulary_version": vocab["version"],
                                 "prompt_version": PROMPT_VERSION}
                        cache[cache_key(s["text"], model)] = entry
                        tagged[s["snippet_id"]] = entry
                        proposals += [(s["snippet_id"], p) for p in entry["proposed"]]
            save_cache(cache, cache_path)

    untagged = [s["snippet_id"] for s in snippets if s["snippet_id"] not in tagged]
    return {"tags": tagged, "untagged": untagged, "errors": errors, "proposals": proposals}
