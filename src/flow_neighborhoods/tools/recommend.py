"""Recommendation tool logic; ranking stays in the existing Python engine."""

from typing import Any, Literal, NotRequired, TypedDict

from ..engine import Recommender


class Recommendation(TypedDict):
    schema_version: str
    model_version: str
    data_version: dict[str, str]
    status: Literal["ok", "no_matches", "needs_clarification"]
    results: list[dict[str, Any]]
    eligible_count: int
    returned_count: int
    excluded_counts: dict[str, int]
    applied_filters: dict[str, Any]
    warnings: list[str]
    feature_order: NotRequired[list[str]]
    preference_vector: NotRequired[list[float]]
    feature_set: NotRequired[str]
    also_consider: NotRequired[list[dict[str, Any]]]


def recommend(
    engine: Recommender,
    budget_max: float,
    household: str,
    housing_preference: str,
    tags: list[str],
    k: int = 3,
    weights: dict[str, int] | None = None,
    near: list[str] | None = None,
) -> Recommendation:
    """Return the engine's result unchanged, including warnings and empty states.

    weights (priority 1-3 per requested tag, or "near") and near (up to 3 neighborhood
    names or ZIPs) are optional; omitted means equal priorities and no location.
    """
    payload = {
        "budget_max": budget_max,
        "household": household,
        "housing_preference": housing_preference,
        "tags": tags,
        "k": k,
    }
    if weights is not None:
        payload["weights"] = weights
    if near is not None:
        payload["near"] = near
    return engine.recommend(payload)
