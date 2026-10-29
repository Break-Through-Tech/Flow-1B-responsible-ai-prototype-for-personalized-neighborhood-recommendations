"""Validation and explicit preference dimensions for the baseline."""

import math
from dataclasses import dataclass

FEATURES = ("transit", "social", "quiet", "pet_friendly", "walkable")
ALL_FEATURES = (*FEATURES, "co_living_friendly")
TAGS = (*FEATURES, "co_living")
# 1 = nice to have, 2 = important, 3 = top priority. Unweighted tags count as 1.
PRIORITIES = (1, 2, 3)
MAX_NEAR = 3


class ValidationError(ValueError):
    """Invalid user input; separate from a valid request with no matches."""


@dataclass(frozen=True)
class Request:
    budget_max: float
    household: str
    housing_preference: str
    tags: tuple[str, ...]
    k: int
    weights: tuple[tuple[str, int], ...] = ()
    near: tuple[str, ...] = ()

    @classmethod
    def parse(cls, payload: dict) -> "Request":
        allowed = {"budget_max", "household", "housing_preference", "tags", "k", "weights", "near"}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValidationError("Expected an object containing only supported request fields.")
        budget = payload.get("budget_max")
        if isinstance(budget, bool) or not isinstance(budget, (int, float)):
            raise ValidationError("budget_max must be a positive finite number in monthly USD.")
        if not math.isfinite(budget) or budget <= 0:
            raise ValidationError("budget_max must be a positive finite number in monthly USD.")
        household = payload.get("household")
        housing = payload.get("housing_preference")
        if household not in ("alone", "with_co_leaser"):
            raise ValidationError("household must be alone or with_co_leaser.")
        if housing not in ("own_apartment", "co_living"):
            raise ValidationError("housing_preference must be own_apartment or co_living.")
        tags = payload.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValidationError("tags must be a list of strings.")
        normalized = tuple(dict.fromkeys(tag.strip().lower() for tag in tags))
        if set(normalized) - set(TAGS):
            raise ValidationError(f"Supported tags: {', '.join(TAGS)}.")
        k = payload.get("k", 3)
        if type(k) is not int or not 1 <= k <= 5:
            raise ValidationError("k must be an integer between 1 and 5.")
        near = payload.get("near", [])
        if (
            not isinstance(near, list)
            or len(near) > MAX_NEAR
            or any(not isinstance(name, str) or not name.strip() for name in near)
        ):
            raise ValidationError(f"near must be a list of up to {MAX_NEAR} neighborhood names.")
        near = tuple(dict.fromkeys(name.strip() for name in near))
        weights = payload.get("weights", {})
        if not isinstance(weights, dict):
            raise ValidationError("weights must map requested tags (or near) to 1, 2 or 3.")
        parsed = {}
        for tag, weight in weights.items():
            key = tag.strip().lower() if isinstance(tag, str) else tag
            if key not in normalized and not (key == "near" and near):
                raise ValidationError(f"weights may only include requested tags or near: {tag!r}.")
            if type(weight) is not int or weight not in PRIORITIES:
                raise ValidationError(
                    "Each weight must be 1 (nice to have), 2 or 3 (top priority)."
                )
            parsed[key] = weight
        return cls(
            float(budget), household, housing, normalized, k, tuple(sorted(parsed.items())), near
        )

    def weight(self, key: str) -> int:
        return dict(self.weights).get(key, 1)

    def clarification(self) -> str | None:
        if not self.tags:
            return "Choose at least one lifestyle priority."
        if self.housing_preference == "own_apartment" and "co_living" in self.tags:
            return "Confirm own_apartment or co_living; the supplied preferences conflict."
        if self.housing_preference == "co_living" and self.household == "with_co_leaser":
            return (
                "Co-living with a co-leaser is not defined in this baseline; clarify housing needs."
            )
        return None

    def vector(self) -> tuple[tuple[str, ...], tuple[float, ...]]:
        features = ALL_FEATURES if self.housing_preference == "co_living" else FEATURES
        values = tuple(
            float(self.weight("co_living"))
            if f == "co_living_friendly"
            else float(self.weight(f))
            if f in self.tags
            else 0.0
            for f in features
        )
        return features, values
