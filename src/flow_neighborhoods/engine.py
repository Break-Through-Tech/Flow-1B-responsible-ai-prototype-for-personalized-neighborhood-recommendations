"""Budget-first, deterministic ranking with attributable demo evidence."""

import copy
import math
import re
from pathlib import Path

from .contracts import ALL_FEATURES, Request, ValidationError
from .data import load_snapshot

# "mean" averages the requested features, so strengths the user did not ask for
# never lower a score. "cosine" is the original baseline, kept for comparison:
# it normalizes by the whole area vector, so e.g. a strong social score makes an
# area rank lower for a transit-only request.
SCORERS = {"mean": "mean-v1", "cosine": "cosine-v1"}


class Recommender:
    def __init__(self, data_dir: str | Path = "data", scorer: str = "mean"):
        if scorer not in SCORERS:
            raise ValueError(f"scorer must be one of {', '.join(SCORERS)}.")
        self.scorer = scorer
        self.model_version = SCORERS[scorer]
        self.areas, self.evidence, self.data_version = load_snapshot(Path(data_dir))
        self.constant_features = {}
        for feature in ALL_FEATURES:
            values = {area[feature] for area in self.areas if area[feature] is not None}
            if len(self.areas) > 1 and len(values) == 1:
                self.constant_features[feature] = values.pop()

    def crowd_themes(self, zip_code: str) -> dict:
        if not isinstance(zip_code, str) or not re.fullmatch(r"[0-9]{5}", zip_code):
            raise ValidationError("ZIP must be a five-digit string.")
        known = any(area["zip"] == zip_code for area in self.areas)
        evidence = copy.deepcopy(self.evidence.get(zip_code, []))
        return {
            "zip": zip_code,
            "status": "ok" if evidence else "no_evidence",
            "known_area": known,
            "evidence": evidence,
            "is_demo": True,
            "extractor_version": "provided-label-lookup-v1",
            "warning": "Demo text, not authentic reviews. Topic labels do not imply sentiment.",
        }

    def features(self, request: Request) -> tuple[tuple[str, ...], tuple[float, ...]]:
        features, user = request.vector()
        if self.scorer == "mean":
            selected = [(f, u) for f, u in zip(features, user) if u]
            return tuple(f for f, _ in selected), tuple(u for _, u in selected)
        return features, user

    def score(self, vector: list[float], user: tuple[float, ...]) -> list[float]:
        """Per-feature contributions; their sum is the area's score."""
        if self.scorer == "mean":
            return [x * u / sum(user) for x, u in zip(vector, user)]
        denominator = math.sqrt(sum(x * x for x in vector) * sum(u * u for u in user))
        return [x * u / denominator if denominator else 0.0 for x, u in zip(vector, user)]

    def rank(self, request: Request) -> tuple[list[dict], dict]:
        """All eligible areas, best first, plus mutually exclusive exclusion counts."""
        features, user = self.features(request)
        excluded = {"missing_rent": 0, "over_budget": 0, "missing_features": 0}
        candidates = []
        for area in self.areas:
            rent = area["median_rent_usd"]
            if rent is None:
                excluded["missing_rent"] += 1
                continue
            if rent > request.budget_max:
                excluded["over_budget"] += 1
                continue
            vector = [area[f] for f in features]
            if any(value is None for value in vector):
                excluded["missing_features"] += 1
                continue
            contributions = self.score(vector, user)
            candidates.append(
                {
                    "zip": area["zip"],
                    "area_name": area["area_name"],
                    "score": min(1.0, sum(contributions)),
                    "score_method": self.model_version,
                    "median_rent_usd": rent,
                    "rent_source": "area_features_cleaned.csv",
                    "source_period": None,
                    "matched_preferences": [
                        {
                            "tag": "co_living" if f == "co_living_friendly" else f,
                            "feature_value": x,
                            "contribution": c,
                        }
                        for f, x, u, c in zip(features, vector, user, contributions)
                        if u
                    ],
                }
            )
        candidates.sort(key=lambda item: (-item["score"], item["zip"]))
        return candidates, excluded

    def recommend(self, payload: dict) -> dict:
        request = Request.parse(payload)
        response = {
            "schema_version": "1",
            "model_version": self.model_version,
            "data_version": self.data_version.copy(),
            "status": "ok",
            "results": [],
            "eligible_count": 0,
            "returned_count": 0,
            "excluded_counts": {"missing_rent": 0, "over_budget": 0, "missing_features": 0},
            "applied_filters": {
                "budget_max": request.budget_max,
                "budget_basis": "total_monthly_usd",
                "rent_field": "median_rent_usd",
                "household": request.household,
                "housing_preference": request.housing_preference,
            },
            "warnings": [
                "Rent is a snapshot area-level estimate; actual prices and availability are unverified.",
                "Lifestyle scores are starter proxies. All text evidence is demo content.",
            ],
        }
        clarification = request.clarification()
        if clarification:
            response["status"] = "needs_clarification"
            response["warnings"].append(clarification)
            return response
        features, user = self.features(request)
        response["feature_order"] = list(features)
        response["preference_vector"] = list(user)
        if request.housing_preference == "co_living":
            response["warnings"].append(
                "Co-living room prices are unavailable; area rent is a proxy."
            )
        for feature, weight in zip(features, user):
            if weight and feature in self.constant_features:
                response["warnings"].append(
                    f"{feature} is {self.constant_features[feature]} for every ZIP in this "
                    "snapshot, so it cannot distinguish areas."
                )
        candidates, excluded = self.rank(request)
        results = candidates[: request.k]
        for rank, item in enumerate(results, 1):
            item["rank"] = rank
            item["themes"] = self.crowd_themes(item["zip"])["evidence"]
        response.update(
            results=results,
            eligible_count=len(candidates),
            returned_count=len(results),
            excluded_counts=excluded,
        )
        if not results:
            response["status"] = "no_matches"
        if len(results) < request.k:
            response["warnings"].append(
                "Fewer eligible ZIPs than requested; budget was not relaxed."
            )
        if len(candidates) > 1 and len({item["score"] for item in candidates}) == 1:
            response["warnings"].append(
                "Requested priorities do not distinguish eligible areas; results are in ZIP order."
            )
        return response
