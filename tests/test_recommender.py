import csv
import json
import math
from pathlib import Path

import pytest

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ALL_FEATURES, ValidationError
from flow_neighborhoods.data import CENSUS_COLUMNS, DataError
from flow_neighborhoods.evaluate import evaluate


def request(**overrides):
    return dict(
        {
            "budget_max": 1500,
            "household": "alone",
            "housing_preference": "own_apartment",
            "tags": ["transit"],
            "k": 3,
        },
        **overrides,
    )


def area(zip_code, rent=1500, **features):
    return {
        "zip": zip_code,
        "median_rent_usd": rent,
        **{name: features.get(name, 0) for name in ALL_FEATURES},
    }


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def snapshot(tmp_path, areas, scorer="mean"):
    write_csv(
        tmp_path / "area_features_cleaned.csv", ["zip", "median_rent_usd", *ALL_FEATURES], areas
    )
    write_csv(
        tmp_path / "area_features.csv",
        ["zip", "area_name"],
        [{"zip": row["zip"], "area_name": f"Area {row['zip']}"} for row in areas],
    )
    write_csv(
        tmp_path / "crowd_text_snippets.csv", ["snippet_id", "zip", "source", "theme", "text"], []
    )
    return Recommender(tmp_path, scorer=scorer, feature_set="provided")


def test_budget_before_ranking_and_exact_boundary(tmp_path):
    engine = snapshot(
        tmp_path, [area("00001", 1501, transit=1), area("00002", 1500, transit=0.5, social=0.5)]
    )
    result = engine.recommend(request())
    assert [row["zip"] for row in result["results"]] == ["00002"]
    assert result["results"][0]["score"] == 0.5
    assert result["excluded_counts"]["over_budget"] == 1
    assert result["returned_count"] == 1


@pytest.mark.parametrize("rent", ["", "nan", "inf", 0, -666666666, -10])
def test_unknown_or_invalid_rent_never_qualifies(tmp_path, rent):
    result = snapshot(tmp_path, [area("00001", rent)]).recommend(request())
    assert result["status"] == "no_matches"
    assert result["excluded_counts"]["missing_rent"] == 1
    json.dumps(result, allow_nan=False)


def test_stable_ties_zero_vectors_and_duplicate_tags(tmp_path):
    engine = snapshot(tmp_path, [area("00003"), area("00002", transit=1), area("00001", transit=1)])
    baseline = engine.recommend(request())
    assert [row["zip"] for row in baseline["results"]] == ["00001", "00002", "00003"]
    assert baseline["results"][-1]["score"] == 0
    assert engine.recommend(request(tags=["transit", " Transit "])) == baseline
    for row in baseline["results"]:
        assert sum(x["contribution"] for x in row["matched_preferences"]) == pytest.approx(
            row["score"]
        )


def test_unrequested_strengths_do_not_lower_score(tmp_path):
    areas = [area("00001", transit=0.9, social=1, quiet=1), area("00002", transit=0.8)]
    result = snapshot(tmp_path, areas).recommend(request())
    assert [row["zip"] for row in result["results"]] == ["00001", "00002"]
    assert result["results"][0]["score"] == pytest.approx(0.9)
    assert result["feature_order"] == ["transit"]


def test_cosine_baseline_penalizes_unrequested_strengths(tmp_path):
    areas = [area("00001", transit=0.9, social=1, quiet=1), area("00002", transit=0.8)]
    result = snapshot(tmp_path, areas, scorer="cosine").recommend(request())
    assert [row["zip"] for row in result["results"]] == ["00002", "00001"]
    assert result["results"][1]["score"] == pytest.approx(0.9 / math.sqrt(0.81 + 2))
    assert result["model_version"] == "cosine-v1"


def test_mean_contributions_are_per_requested_feature(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=0.6, walkable=1), area("00002")])
    row = engine.recommend(request(tags=["transit", "walkable"]))["results"][0]
    assert row["score"] == pytest.approx(0.8)
    assert [x["contribution"] for x in row["matched_preferences"]] == pytest.approx([0.3, 0.5])


def test_uninformative_features_are_disclosed(tmp_path):
    engine = snapshot(tmp_path, [area("00001", pet_friendly=0.6), area("00002", pet_friendly=0.6)])
    result = engine.recommend(request(tags=["pet_friendly"]))
    assert any("pet_friendly is 0.6 for every ZIP" in text for text in result["warnings"])
    assert any("results are in ZIP order" in text for text in result["warnings"])
    cosine = Recommender(
        tmp_path, scorer="cosine", feature_set="provided"
    )  # pet_friendly is in its vector, unrequested
    assert not any("pet_friendly is" in text for text in cosine.recommend(request())["warnings"])


def test_unknown_scorer_rejected(tmp_path):
    with pytest.raises(ValueError):
        snapshot(tmp_path, [area("00001")], scorer="dot")


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_max": True},
        {"budget_max": float("nan")},
        {"budget_max": float("inf")},
        {"budget_max": -1},
        {"budget_max": "1500"},
        {"k": True},
        {"k": 6},
        {"k": 0},
        {"tags": "transit"},
        {"tags": [None]},
        {"tags": ["unknown"]},
        {"household": "couple"},
        {"housing_preference": "house"},
        {"age": 30},
    ],
)
def test_invalid_requests_are_distinct_from_no_matches(tmp_path, changes):
    engine = snapshot(tmp_path, [area("00001", transit=1)])
    with pytest.raises(ValidationError):
        engine.recommend(request(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"tags": []},
        {"tags": ["co_living"]},
        {"household": "with_co_leaser", "housing_preference": "co_living"},
    ],
)
def test_ambiguous_inputs_request_clarification(tmp_path, changes):
    result = snapshot(tmp_path, [area("00001")]).recommend(request(**changes))
    assert result["status"] == "needs_clarification"
    assert result["results"] == []


def test_coliving_dimension_only_affects_coliving(tmp_path):
    engine = snapshot(
        tmp_path, [area("00001", transit=1), area("00002", transit=1, co_living_friendly=1)]
    )
    assert engine.recommend(request())["results"][0]["zip"] == "00001"
    shared = engine.recommend(request(housing_preference="co_living"))
    assert shared["results"][0]["zip"] == "00002"
    assert any("room prices" in text for text in shared["warnings"])
    assert (
        engine.recommend(request(household="with_co_leaser"))["results"]
        == engine.recommend(request())["results"]
    )


def test_missing_features_excluded_only_in_active_mode(tmp_path):
    engine = snapshot(
        tmp_path, [area("00001", transit=1, co_living_friendly=""), area("00002", transit="")]
    )
    assert engine.recommend(request())["returned_count"] == 1
    result = engine.recommend(request(housing_preference="co_living"))
    assert result["excluded_counts"]["missing_features"] == 2


@pytest.mark.parametrize(
    "areas",
    [
        [area("00001"), area("00001")],
        [area("1234")],
        [area("00001", transit=2)],
        [area("00001", transit="oops")],
    ],
)
def test_bad_source_data_fails_explicitly(tmp_path, areas):
    with pytest.raises(DataError):
        snapshot(tmp_path, areas)


def test_missing_required_column(tmp_path):
    snapshot(tmp_path, [area("00001")])
    (tmp_path / "area_features_cleaned.csv").write_text("zip\n00001\n", encoding="utf-8")
    with pytest.raises(DataError):
        Recommender(tmp_path, feature_set="provided")


def test_demo_evidence_preserved_without_sentiment_claim(tmp_path):
    snapshot(tmp_path, [area("00001", transit=1)])
    write_csv(
        tmp_path / "crowd_text_snippets.csv",
        ["snippet_id", "zip", "source", "theme", "text"],
        [
            {
                "snippet_id": "T1",
                "zip": "00001",
                "source": "demo",
                "theme": "quiet",
                "text": "Not quiet at night.",
            }
        ],
    )
    engine = Recommender(tmp_path, feature_set="provided")
    evidence = engine.crowd_themes("00001")["evidence"][0]
    assert evidence["text"] == "Not quiet at night."
    assert evidence["is_demo"] and evidence["polarity"] == "unknown"
    assert evidence["evidence_id"] == "T1"
    evidence["text"] = "mutated"
    assert engine.crowd_themes("00001")["evidence"][0]["text"] == "Not quiet at night."
    assert engine.crowd_themes("99999")["status"] == "no_evidence"
    with pytest.raises(ValidationError):
        engine.crowd_themes(1)  # pyright: ignore[reportArgumentType] -- intentional invalid input


def test_evaluation_empty_results_and_precision_denominator(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=1)])
    profile = dict(request(), profile_id="test", expected_relevant_zips=["00001"])
    report = evaluate(engine, [profile])
    assert report["summary"]["3"]["precision"] == pytest.approx(1 / 3)
    assert report["summary"]["5"]["precision"] == 0.2
    assert report["summary"]["3"]["mrr"] == 1
    profile["budget_max"] = 1
    empty = evaluate(engine, [profile])["summary"]["3"]
    assert empty["empty_profiles"] == 1
    assert empty["budget_pass_rate_nonempty"] is None
    assert empty["demo_theme_coverage"] is None


def test_repository_snapshot_and_all_profiles():
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads((root / "eval/recommendation_profiles.json").read_text())
    for scorer in ("mean", "cosine"):
        check_repository_profiles(Recommender(root / "data", scorer=scorer), profiles)
    check_repository_profiles(Recommender(root / "data", feature_set="provided"), profiles)
    census = Recommender(root / "data")
    assert census.feature_set == "census"
    check_repository_profiles(census, profiles)
    airport = census.recommend(request(budget_max=10000, tags=["quiet"], k=5))
    assert "33122" not in [row["zip"] for row in airport["results"]]
    social = census.recommend(request(budget_max=10000, tags=["social", "walkable", "transit"]))
    assert social["excluded_counts"]["missing_features"] == 0
    brickell = census.recommend(request(budget_max=2000, near=["Brickell"], weights={"near": 3}))
    assert brickell["results"][0]["zip"] == "33130"
    assert Recommender(root / "data").crowd_themes("33130")["evidence"]


def check_repository_profiles(engine, profiles):
    report = evaluate(engine, profiles)
    assert len(report["profiles"]) == 2 * len(profiles)
    json.dumps(report, allow_nan=False)
    for row in report["profiles"]:
        response = row["response"]
        assert row["budget_pass"] is True
        assert len({item["zip"] for item in response["results"]}) == row["k"]
        assert response["eligible_count"] + sum(response["excluded_counts"].values()) == len(
            engine.areas
        )


def places(tmp_path, geography, aliases):
    write_csv(
        tmp_path / "zcta_geography.csv",
        ["zip", "land_sqmi", "lat", "lon", "usps_city"],
        [
            {"zip": z, "land_sqmi": s, "lat": la, "lon": lo, "usps_city": c}
            for z, (s, la, lo, c) in geography.items()
        ],
    )
    write_csv(
        tmp_path / "neighborhood_aliases.csv",
        ["alias", "zip", "source"],
        [{"alias": a, "zip": z, "source": "test"} for a, z in aliases],
    )


THREE_PLACES = {
    "00001": (1, 25.76, -80.19, "Miami"),
    "00002": (1, 25.80, -80.19, "Miami"),
    "00003": (1, 25.60, -80.40, "Homestead"),
}


def test_priorities_weight_the_mean(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=1), area("00002", walkable=1)])
    equal = engine.recommend(request(tags=["transit", "walkable"]))
    assert [row["score"] for row in equal["results"]] == [0.5, 0.5]
    weighted = engine.recommend(request(tags=["transit", "walkable"], weights={"walkable": 3}))
    assert [row["zip"] for row in weighted["results"]] == ["00002", "00001"]
    assert weighted["results"][0]["score"] == pytest.approx(0.75)
    first = weighted["results"][0]["matched_preferences"]
    assert [(x["tag"], x["priority"]) for x in first] == [("transit", 1), ("walkable", 3)]
    assert sum(x["contribution"] for x in first) == pytest.approx(0.75)
    assert weighted["applied_filters"]["weights"] == {"transit": 1, "walkable": 3}


@pytest.mark.parametrize(
    "weights",
    [
        {"social": 2},
        {"transit": 0},
        {"transit": 4},
        {"transit": True},
        {"transit": "2"},
        ["transit"],
    ],
)
def test_invalid_priorities_rejected(tmp_path, weights):
    engine = snapshot(tmp_path, [area("00001", transit=1)])
    with pytest.raises(ValidationError):
        engine.recommend(request(weights=weights))


def test_co_leaser_budget_is_household_total(tmp_path):
    engine = snapshot(tmp_path, [area("00001", 1500, transit=1), area("00002", 1600, transit=1)])
    alone = engine.recommend(request())
    shared = engine.recommend(request(household="with_co_leaser"))
    assert [row["zip"] for row in shared["results"]] == ["00001"]
    assert shared["results"] == alone["results"]
    assert shared["applied_filters"]["budget_basis"] == "household_total_monthly_usd"
    assert any("household's total" in text for text in shared["warnings"])
    assert not any("household's total" in text for text in alone["warnings"])


def test_near_scores_distance_to_named_neighborhood(tmp_path):
    snapshot(
        tmp_path, [area("00001", transit=1), area("00002", transit=1), area("00003", transit=1)]
    )
    places(tmp_path, THREE_PLACES, [("Brickell", "00001"), ("Homestead", "00003")])
    engine = Recommender(tmp_path, feature_set="provided")
    result = engine.recommend(request(near=["brickell"], weights={"near": 2}))
    assert [row["zip"] for row in result["results"]] == ["00001", "00002", "00003"]
    assert result["results"][0]["distance_miles"] == 0
    assert result["results"][-1]["matched_preferences"][-1]["feature_value"] == 0
    assert result["applied_filters"]["near"] == {"brickell": ["00001"]}
    assert result["results"][0]["usps_city"] == "Miami"
    assert result["results"][0]["area_name"] == "Area 00001"
    by_zip = engine.recommend(request(near=["00003"]))
    assert by_zip["results"][0]["zip"] == "00003"


def test_near_rejects_unknown_and_overly_broad_names(tmp_path):
    zips = [f"{i:05d}" for i in range(1, 13)]
    snapshot(tmp_path, [area(z, transit=1) for z in zips])
    places(
        tmp_path,
        {z: (1, 25.7, -80.2, "Miami") for z in zips},
        [("Brickell", "00001"), *(("Miami", z) for z in zips)],
    )
    engine = Recommender(tmp_path, feature_set="provided")
    with pytest.raises(ValidationError, match="Did you mean Brickell"):
        engine.recommend(request(near=["Brickel"]))
    with pytest.raises(ValidationError, match="specific neighborhood"):
        engine.recommend(request(near=["Miami"]))
    with pytest.raises(ValidationError):
        engine.recommend(request(near=["a", "b", "c", "d"]))


def test_near_without_place_data_is_a_data_error(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=1)])
    with pytest.raises(DataError):
        engine.recommend(request(near=["Brickell"]))


def census_snapshot(tmp_path, areas, rows):
    snapshot(tmp_path, areas)
    places(tmp_path, THREE_PLACES, [])
    fields = sorted(CENSUS_COLUMNS - {"zip"})
    write_csv(
        tmp_path / "census_features.csv",
        ["zip", *fields],
        [dict(zip=z, **dict(zip(fields, values))) for z, values in rows.items()],
    )
    return Recommender(tmp_path, feature_set="census")


def test_census_features_measure_distinct_things(tmp_path):
    # Sorted columns: food_drink_establishments, noise_share_ge_55db,
    # transit_commuters, walk_commuters, workers
    engine = census_snapshot(
        tmp_path,
        [area("00001"), area("00002"), area("00003")],
        {
            "00001": (90, 0.4, 40, 30, 100),  # downtown: venues, transit, some noise
            "00002": (40, 0.7, 5, 20, 100),  # beside a highway: loudest
            "00003": (2, 0.0, 1, 1, 100),  # rural
        },
    )
    social = engine.recommend(request(tags=["social"]))
    assert [row["zip"] for row in social["results"]] == ["00001", "00002", "00003"]
    quiet = engine.recommend(request(tags=["quiet"]))
    assert [row["zip"] for row in quiet["results"]] == ["00003", "00001", "00002"]
    both = engine.recommend(request(tags=["social", "quiet"]))
    assert len({row["score"] for row in both["results"]}) == 3
    assert both["results"][0]["measures"]["noise_share_ge_55db"] == 0.4
    assert both["feature_set"] == "census"
    assert "census_features.csv" in both["data_version"]
    assert any("road and aviation noise" in text for text in both["warnings"])


def test_census_missing_inputs_exclude_only_when_requested(tmp_path):
    engine = census_snapshot(
        tmp_path,
        [area("00001", transit=1), area("00002", transit=1)],
        {"00001": (10, 0.1, 10, 10, 100), "00002": (10, 0.1, 10, 10, 0)},
    )
    transit = engine.recommend(request())
    assert transit["excluded_counts"]["missing_features"] == 1
    social = engine.recommend(request(tags=["social"]))
    assert social["returned_count"] == 2


def test_census_rejects_invalid_noise_share(tmp_path):
    with pytest.raises(DataError):
        census_snapshot(tmp_path, [area("00001")], {"00001": (1, 1.5, 1, 1, 10)})


def test_census_needs_geography(tmp_path):
    snapshot(tmp_path, [area("00001")])
    with pytest.raises(DataError):
        Recommender(tmp_path, feature_set="census")
