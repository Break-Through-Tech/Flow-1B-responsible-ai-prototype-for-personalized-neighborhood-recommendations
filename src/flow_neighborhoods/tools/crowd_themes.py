"""crowd_themes tool: review snippets and theme labels for one ZIP."""

import json
import re
from collections import Counter
from typing import Literal, TypedDict

from ..contracts import ValidationError
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


def nlp_tags(engine: Recommender, zip_code: str) -> list[NlpTag]:
    """Verified LLM tags for the ZIP from data/nlp/location_tags.json (empty if absent)."""
    path = engine.data_dir / "nlp" / "location_tags.json"
    if not path.exists():
        return []
    tags = json.loads(path.read_text(encoding="utf-8")).get("locations", {}).get(zip_code, {})
    out = [
        {
            "tag": name,
            "level": record.get("level", "parent"),
            "count": int(record["count"]),
            "quotes": [
                {
                    "snippet_id": e["snippet_id"],
                    "quote": e["quote"],
                    "is_demo": bool(e.get("is_demo", True)),
                }
                for e in record["evidence"]
            ],
        }
        for name, record in tags.get("tags", {}).items()
    ]
    return sorted(out, key=lambda t: (-t["count"], t["tag"]))


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
        "nlp_tags": nlp_tags(engine, result["zip"]),
        "is_demo": result["is_demo"],
        "extractor_version": result["extractor_version"],
        "warning": result["warning"],
        "guidance": GUIDANCE,
        "data_version": {
            name: digest
            for name, digest in engine.data_version.items()
            if name == "crowd_text_snippets.csv"
        },
    }
