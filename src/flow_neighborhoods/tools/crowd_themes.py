"""crowd_themes tool: review snippets and theme labels for one ZIP."""

import hashlib
import json
import re
from collections import Counter
from typing import Literal, TypedDict

from ..contracts import ValidationError
from ..data import DataError
from ..engine import Recommender


class Evidence(TypedDict):
    evidence_id: str
    theme: str
    text: str
    source_label: str
    is_demo: bool
    polarity: str
    needs_review: bool


class TagQuote(TypedDict):
    snippet_id: str
    quote: str
    is_demo: bool


class NlpTag(TypedDict):
    tag: str
    level: str
    count: int
    quotes: list[TagQuote]


class CrowdThemes(TypedDict):
    zip: str
    area_name: str | None
    status: Literal["ok", "no_evidence", "unknown_area"]
    theme_counts: dict[str, int]
    theme_polarity: dict[str, dict[str, int]]
    evidence: list[Evidence]
    nlp_tags: list[NlpTag]
    is_demo: bool
    extractor_version: str
    warning: str
    guidance: str
    data_version: dict[str, str]


GUIDANCE = (
    "Quote snippet text exactly and cite its evidence_id. These are demo snippets, not "
    "authentic reviews: say so. A theme label is a topic; use polarity for whether a snippet "
    "speaks for or against it ('quiet' with polarity negative, e.g. 'Not quiet at night.', "
    "is evidence against quiet). Polarity is automated and can be wrong; say 'reviews suggest'. "
    "Never describe an area as safe or unsafe: needs_review snippets mention safety and must "
    "not be characterized. Do not generalize beyond these snippets or invent others; if status "
    "is no_evidence or unknown_area, say there are no snippets for this ZIP."
)


def nlp_tags(engine: Recommender, zip_code: str) -> tuple[list[NlpTag], dict[str, str], int]:
    """Only publish quotes grounded in this engine's active ZIP/snippet snapshot.

    A cached index may predate a CSV refresh. Never trust its quote, count or demo
    label just because it was checked when that index was originally built.
    """
    path = engine.data_dir / "nlp" / "location_tags.json"
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return [], {}, 0
    versions = {"nlp/location_tags.json": hashlib.sha256(raw).hexdigest()}
    try:
        index = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise DataError("NLP tag index must be valid UTF-8 JSON.") from exc
    if not isinstance(index, dict) or not isinstance(index.get("locations"), dict):
        raise DataError("NLP tag index must contain a locations object.")
    location = index["locations"].get(zip_code, {})
    if not isinstance(location, dict) or not isinstance(location.get("tags", {}), dict):
        raise DataError("NLP tag index must contain a tags object per ZIP.")
    active = {item["evidence_id"]: item for item in engine.evidence.get(zip_code, [])}
    out, rejected = [], 0
    for name, record in location.get("tags", {}).items():
        if not isinstance(record, dict) or not isinstance(record.get("evidence"), list):
            raise DataError("NLP tag records must contain an evidence list.")
        level = record.get("level", "parent")
        if not isinstance(level, str):
            raise DataError("NLP tag levels must be strings.")
        quotes, seen = [], set()
        for cached in record["evidence"]:
            sid = cached.get("snippet_id") if isinstance(cached, dict) else None
            quote = cached.get("quote") if isinstance(cached, dict) else None
            source = active.get(sid) if isinstance(sid, str) else None
            quote = quote.strip() if isinstance(quote, str) else ""
            if not source or not quote or quote not in source["text"]:
                rejected += 1
                continue
            if (sid, quote) in seen:
                continue
            seen.add((sid, quote))
            quotes.append({"snippet_id": sid, "quote": quote, "is_demo": source["is_demo"]})
        if quotes:
            out.append(
                {
                    "tag": name,
                    "level": level,
                    "count": len({quote["snippet_id"] for quote in quotes}),
                    "quotes": quotes,
                }
            )
    return sorted(out, key=lambda t: (-t["count"], t["tag"])), versions, rejected


def crowd_themes(engine: Recommender, zip_code: str) -> CrowdThemes:
    """Snippets and theme counts for a ZIP, with grounding rules for the agent.

    status: ok (snippets found), no_evidence (known ZIP, no snippets) or
    unknown_area (valid ZIP outside the Miami-Dade snapshot). Malformed input
    raises ValidationError.
    """
    if not isinstance(zip_code, str) or not re.fullmatch(r"[0-9]{5}", zip_code.strip()):
        raise ValidationError(
            f"zip_code must be a five-digit ZIP such as '33130', got {zip_code!r}. "
            "Look up the ZIP for a neighborhood name first."
        )
    result = engine.crowd_themes(zip_code.strip())
    names = {area["zip"]: area["area_name"] for area in engine.areas}
    status = result["status"] if result["known_area"] else "unknown_area"
    tags, tag_versions, rejected = nlp_tags(engine, result["zip"])
    warning = result["warning"]
    if rejected:
        warning += (
            " Cached NLP quotes unsupported by the current ZIP/snippet snapshot were omitted; "
            "rebuild the NLP index after refreshing review data."
        )
    return {
        "zip": result["zip"],
        "area_name": names.get(result["zip"]),
        "status": status,
        "theme_counts": dict(sorted(Counter(e["theme"] for e in result["evidence"]).items())),
        "theme_polarity": {
            theme: dict(
                sorted(
                    Counter(
                        e["polarity"] for e in result["evidence"] if e["theme"] == theme
                    ).items()
                )
            )
            for theme in sorted({e["theme"] for e in result["evidence"]})
        },
        "evidence": result["evidence"],
        "nlp_tags": tags,
        "is_demo": result["is_demo"],
        "extractor_version": result["extractor_version"],
        "warning": warning,
        "guidance": GUIDANCE,
        "data_version": {
            name: digest
            for name, digest in engine.data_version.items()
            if name == "crowd_text_snippets.csv"
        }
        | tag_versions,
    }
