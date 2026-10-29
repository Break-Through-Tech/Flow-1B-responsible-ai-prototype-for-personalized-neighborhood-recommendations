"""Budget-first, deterministic ranking with attributable demo evidence."""

import copy
import difflib
import math
import re
from pathlib import Path

from .contracts import ALL_FEATURES, Request, ValidationError
from .data import DataError, apply_census, load_places, load_snapshot, normalize_name

# "mean" averages the requested features (weighted by priority), so strengths
# the user did not ask for never lower a score. "cosine" is the original
# baseline, kept for comparison: it normalizes by the whole area vector, so e.g.
# a strong social score makes an area rank lower for a transit-only request.
SCORERS = {"mean": "mean-v1", "cosine": "cosine-v1"}
# "census" (default) replaces the starter proxies for transit, social, walkable
# and quiet with measured values (see data.apply_census). "provided" ranks on
# area_features_cleaned.csv as is, kept for comparison.
FEATURE_SETS = ("census", "provided")
# A name covering more ZIPs than this (e.g. "Miami") is too broad to mean "near".
MAX_NEAR_ZIPS = 10


def miles(a: dict, b: dict) -> float:
    """Great-circle distance between two ZIP internal points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 3958.8 * 2 * math.asin(math.sqrt(h))


class Recommender:
    def __init__(
        self, data_dir: str | Path = "data", scorer: str = "mean", feature_set: str = "census"
    ):
        if scorer not in SCORERS:
            raise ValueError(f"scorer must be one of {', '.join(SCORERS)}.")
        if feature_set not in FEATURE_SETS:
            raise ValueError(f"feature_set must be one of {', '.join(FEATURE_SETS)}.")
        self.scorer = scorer
        self.model_version = SCORERS[scorer]
        self.feature_set = feature_set
        directory = Path(data_dir)
        self.areas, self.evidence, self.data_version = load_snapshot(directory)
        self.geography, self.aliases, versions = load_places(directory)
        self.data_version.update(versions)
        if feature_set == "census":
            self.data_version.update(apply_census(directory, self.areas, self.geography))
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

    def resolve_near(self, names: tuple[str, ...]) -> dict[str, list[str]]:
        """Map each requested neighborhood name (or ZIP) to the ZIPs it covers."""
        if not names:
            return {}
        if not self.aliases:
            raise DataError(
                "Neighborhood lookup needs zcta_geography.csv and neighborhood_aliases.csv."
            )
        known = {area["zip"] for area in self.areas}
        resolved = {}
        for name in names:
            if re.fullmatch(r"[0-9]{5}", name):
                zips = [name] if name in known else []
            else:
                zips = self.aliases.get(normalize_name(name), {}).get("zips", [])
            zips = [z for z in zips if self.geography.get(z, {}).get("lat") is not None]
            if not zips:
                hint = difflib.get_close_matches(normalize_name(name), self.aliases, n=1)
                suggestion = f" Did you mean {self.aliases[hint[0]]['label']}?" if hint else ""
                raise ValidationError(f"Unknown neighborhood {name!r}.{suggestion}")
            if len(zips) > MAX_NEAR_ZIPS:
                raise ValidationError(
                    f"{name!r} covers {len(zips)} ZIPs; name a specific neighborhood instead."
                )
            resolved[name] = zips
        return resolved

    def proximity(self, resolved: dict[str, list[str]]) -> dict[str, tuple[float, float]]:
        """Miles to the nearest named ZIP and a 0-1 closeness (1 = in the named area)."""
        targets = [self.geography[z] for zips in resolved.values() for z in zips]
        distance = {
            area["zip"]: min(miles(self.geography[area["zip"]], t) for t in targets)
            for area in self.areas
            if self.geography.get(area["zip"], {}).get("lat") is not None
        }
        farthest = max(distance.values(), default=0) or 1
        return {z: (d, 1 - d / farthest) for z, d in distance.items()}

    def features(self, request: Request) -> tuple[tuple[str, ...], tuple[float, ...]]:
        features, user = request.vector()
        if self.scorer == "mean":
            selected = [(f, u) for f, u in zip(features, user) if u]
            features, user = tuple(f for f, _ in selected), tuple(u for _, u in selected)
        if request.near:
            features, user = (*features, "near"), (*user, float(request.weight("near")))
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
        near = self.proximity(self.resolve_near(request.near)) if request.near else {}
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
            vector = [
                near.get(area["zip"], (None, None))[1] if f == "near" else area[f] for f in features
            ]
            if any(value is None for value in vector):
                excluded["missing_features"] += 1
                continue
            contributions = self.score(vector, user)
            item = {
                "zip": area["zip"],
                "area_name": area["area_name"],
                "usps_city": self.geography.get(area["zip"], {}).get("usps_city"),
                "score": min(1.0, sum(contributions)),
                "score_method": self.model_version,
                "median_rent_usd": rent,
                "rent_source": "area_features_cleaned.csv",
                "source_period": None,
                "matched_preferences": [
                    {
                        "tag": "co_living" if f == "co_living_friendly" else f,
                        "priority": int(u),
                        "feature_value": x,
                        "contribution": c,
                    }
                    for f, x, u, c in zip(features, vector, user, contributions)
                    if u
                ],
            }
            if near:
                item["distance_miles"] = round(near[area["zip"]][0], 1)
            if "measures" in area:
                item["measures"] = dict(area["measures"])
            candidates.append(item)
        candidates.sort(key=lambda item: (-item["score"], item["zip"]))
        return candidates, excluded

    def recommend(self, payload: dict) -> dict:
        request = Request.parse(payload)
        co_leaser = request.household == "with_co_leaser"
        response = {
            "schema_version": "1",
            "model_version": self.model_version,
            "feature_set": self.feature_set,
            "data_version": self.data_version.copy(),
            "status": "ok",
            "results": [],
            "eligible_count": 0,
            "returned_count": 0,
            "excluded_counts": {"missing_rent": 0, "over_budget": 0, "missing_features": 0},
            "applied_filters": {
                "budget_max": request.budget_max,
                "budget_basis": "household_total_monthly_usd",
                "rent_field": "median_rent_usd",
                "household": request.household,
                "housing_preference": request.housing_preference,
                "weights": {tag: request.weight(tag) for tag in request.tags},
                "near": {},
            },
            "warnings": [
                "Rent is a snapshot area-level estimate; actual prices and availability are unverified.",
                "Lifestyle scores are starter proxies. All text evidence is demo content."
                if self.feature_set == "provided"
                else "transit and walkable are commute shares of residents (ACS 2018-22); social "
                "counts restaurants and bars by mailing ZIP (2021); quiet is modeled 2020 road "
                "and aviation noise (BTS), averaged per ZIP. They are proxies, not direct "
                "measures of service, nightlife or sound at an address. pet_friendly and "
                "co_living keep starter values. All text evidence is demo content.",
            ],
        }
        if co_leaser:
            response["warnings"].append(
                f"Budget is treated as the household's total: ${request.budget_max:,.0f} a month "
                "for you and your co-leaser combined, not each person's share. Median rent covers "
                "all unit sizes; a 2-bedroom usually costs more."
            )
        clarification = request.clarification()
        if clarification:
            response["status"] = "needs_clarification"
            response["warnings"].append(clarification)
            return response
        resolved = self.resolve_near(request.near)
        if resolved:
            response["applied_filters"]["near"] = resolved
            response["applied_filters"]["weights"]["near"] = request.weight("near")
            response["warnings"].append(
                "Distance is measured between ZIP centers (Census internal points), "
                "not exact addresses."
            )
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
