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


def recommend(
    engine: Recommender,
    budget_max: float,
    household: str,
    housing_preference: str,
    tags: list[str],
    k: int = 3,
) -> Recommendation:
    """Return the engine's result unchanged, including warnings and empty states."""
    return engine.recommend(
        {
            "budget_max": budget_max,
            "household": household,
            "housing_preference": housing_preference,
            "tags": tags,
            "k": k,
        }
    )
