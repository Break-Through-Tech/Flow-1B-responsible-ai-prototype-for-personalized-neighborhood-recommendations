import csv
import json
import math
from pathlib import Path

import pytest

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ALL_FEATURES, ValidationError
from flow_neighborhoods.data import DataError
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
    return Recommender(tmp_path, scorer=scorer)


def density_snapshot(tmp_path, areas, population, land):
    snapshot(tmp_path, areas)
    write_csv(
        tmp_path / "public_features_cleaned.csv",
        ["zip", "population"],
        [{"zip": z, "population": p} for z, p in population.items()],
    )
    write_csv(
        tmp_path / "zcta_land_area.csv",
        ["zip", "land_sqmi"],
        [{"zip": z, "land_sqmi": s} for z, s in land.items()],
    )
    return Recommender(tmp_path, feature_set="density")


def test_density_replaces_population_size_proxies(tmp_path):
    # 00001 is a large, sparse ZIP: the provided proxies call it the most social.
    areas = [area("00001", social=1), area("00002", social=0.5), area("00003", social=0.2)]
    engine = density_snapshot(
        tmp_path,
        areas,
        population={"00001": 50000, "00002": 20000, "00003": 10000},
        land={"00001": 50, "00002": 1, "00003": 2},
    )
    social = engine.recommend(request(tags=["social"]))
    assert [row["zip"] for row in social["results"]] == ["00002", "00003", "00001"]
    assert [row["score"] for row in social["results"]] == [1, 0.5, 0]
    assert social["feature_set"] == "density"
    assert any("population density" in text for text in social["warnings"])
    assert {"public_features_cleaned.csv", "zcta_land_area.csv"} <= set(social["data_version"])
    quiet = engine.recommend(request(tags=["quiet"]))
    assert [row["zip"] for row in quiet["results"]] == ["00001", "00003", "00002"]
    walkable = engine.recommend(request(tags=["walkable"]))
    assert [row["zip"] for row in walkable["results"]] == ["00002", "00003", "00001"]


def test_density_missing_inputs_exclude_only_when_requested(tmp_path):
    engine = density_snapshot(
        tmp_path,
        [area("00001", transit=1), area("00002", transit=0.5), area("00003", transit=0.2)],
        population={"00001": 100, "00002": 100, "00003": 0},
        land={"00001": 1, "00003": 2},
    )
    assert engine.recommend(request(tags=["social"]))["excluded_counts"]["missing_features"] == 2
    assert engine.recommend(request())["returned_count"] == 3


def test_unknown_feature_set_rejected(tmp_path):
    snapshot(tmp_path, [area("00001")])
    with pytest.raises(ValueError):
        Recommender(tmp_path, feature_set="census")


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
    cosine = Recommender(tmp_path, scorer="cosine")  # pet_friendly is in its vector, unrequested
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
        Recommender(tmp_path)


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
    engine = Recommender(tmp_path)
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
    density = Recommender(root / "data", feature_set="density")
    check_repository_profiles(density, profiles)
    social = density.recommend(request(budget_max=10000, tags=["social"]))
    assert social["excluded_counts"]["missing_features"] == 0
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
