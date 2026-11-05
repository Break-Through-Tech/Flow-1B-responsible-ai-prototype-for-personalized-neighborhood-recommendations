"""crowd_themes tool: review snippets and theme labels for one ZIP."""

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


class CrowdThemes(TypedDict):
    zip: str
    area_name: str | None
    status: Literal["ok", "no_evidence", "unknown_area"]
    theme_counts: dict[str, int]
    evidence: list[Evidence]
    is_demo: bool
    extractor_version: str
    warning: str
    guidance: str
    data_version: dict[str, str]


GUIDANCE = (
    "Quote snippet text exactly and cite its evidence_id. These are demo snippets, not "
    "authentic reviews: say so. A theme label is a topic, not a sentiment ('quiet' can tag "
    "'Not quiet at night.'). Do not generalize beyond these snippets or invent others; "
    "if status is no_evidence or unknown_area, say there are no snippets for this ZIP."
)


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
        "evidence": result["evidence"],
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
