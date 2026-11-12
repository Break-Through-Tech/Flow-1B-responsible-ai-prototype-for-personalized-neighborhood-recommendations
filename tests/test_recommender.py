import csv
import json
import math
from pathlib import Path

import pytest

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ALL_FEATURES, Request, ValidationError
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
    # HUD 1-bedroom in 33130 is $2,300: over a $2,000 budget, within $2,500.
    tight = census.recommend(request(budget_max=2000, near=["Brickell"], weights={"near": 3}))
    assert "33130" not in [row["zip"] for row in tight["results"]]
    brickell = census.recommend(request(budget_max=2500, near=["Brickell"], weights={"near": 3}))
    assert brickell["results"][0]["zip"] == "33130"
    assert brickell["results"][0]["rent_usd"] == 2300
    assert "1-bedroom" in brickell["results"][0]["rent_basis"]
    assert Recommender(root / "data").crowd_themes("33130")["evidence"]


def check_repository_profiles(engine, profiles):
    report = evaluate(engine, profiles)
    assert len(report["profiles"]) == 2 * len(profiles)
    json.dumps(report, allow_nan=False)
    for row in report["profiles"]:
        response = row["response"]
        assert row["budget_pass"] is True
        returned = len({item["zip"] for item in response["results"]})
        assert returned == response["returned_count"] <= row["k"]
        if returned < row["k"]:  # a short list stays short and says so (e.g. co-living)
            assert any("Fewer eligible ZIPs" in text for text in response["warnings"])
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
    hud(tmp_path, {row["zip"]: row["median_rent_usd"] for row in areas})
    return Recommender(tmp_path, feature_set="census")


def hud(tmp_path, rents):
    """rents_hud.csv with every unit size at the given rent (blank rent = no row)."""
    units = ["efficiency", "one_bedroom", "two_bedroom", "three_bedroom", "four_bedroom"]
    write_csv(
        tmp_path / "rents_hud.csv",
        ["zip", *units, "source"],
        [{"zip": z, **dict.fromkeys(units, r), "source": "test"} for z, r in rents.items() if r],
    )


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


def test_primary_names_win_and_secondary_names_fill_gaps(tmp_path):
    snapshot(tmp_path, [area("00001"), area("00002"), area("00003")])
    places(tmp_path, THREE_PLACES, [])
    write_csv(
        tmp_path / "neighborhood_aliases.csv",
        ["alias", "zip", "match", "source"],
        [
            {"alias": "Coral Gables", "zip": "00001", "match": "primary", "source": "t"},
            {"alias": "Coral Gables", "zip": "00002", "match": "secondary", "source": "t"},
            {"alias": "Little Haiti", "zip": "00003", "match": "secondary", "source": "t"},
        ],
    )
    engine = Recommender(tmp_path, feature_set="provided")
    assert engine.resolve_near(("Coral Gables",)) == {"Coral Gables": ["00001"]}
    assert engine.resolve_near(("little haiti",)) == {"little haiti": ["00003"]}


def test_area_names_and_transit_service_are_shown_not_ranked(tmp_path):
    areas = [area("00001", transit=0.2), area("00002", transit=0.9)]
    engine = snapshot(tmp_path, areas)
    places(tmp_path, THREE_PLACES, [])
    write_csv(
        tmp_path / "zip_area_names.csv",
        ["zip", "neighborhood", "other_areas", "area_name_type", "source"],
        [
            {
                "zip": "00001",
                "neighborhood": "Brickell",
                "other_areas": "Downtown|Brickell Key",
                "area_name_type": "neighborhood",
                "source": "t",
            }
        ],
    )
    service = {
        "transit_stops": 60,
        "routes": 28,
        "metrorail_routes": 1,
        "metromover_routes": 1,
        "weekday_departures": 8000,
        "weekday_median_headway_minutes": 16,
    }
    write_csv(
        tmp_path / "transit_service.csv",
        ["zip", *service, "data_as_of"],
        [{"zip": "00001", **service, "data_as_of": "2026-10-27"}],
    )
    enriched = Recommender(tmp_path, feature_set="provided").recommend(request())
    plain = engine.recommend(request())
    assert [r["zip"] for r in enriched["results"]] == [r["zip"] for r in plain["results"]]
    row = next(r for r in enriched["results"] if r["zip"] == "00001")
    assert row["neighborhood"] == "Brickell" and row["area_name"] == "Area 00001"
    assert row["other_areas"] == ["Downtown", "Brickell Key"]
    assert (
        row["transit_service"]["routes"] == 28
        and row["transit_service"]["data_as_of"] == "2026-10-27"
    )
    other = next(r for r in enriched["results"] if r["zip"] == "00002")
    assert other["neighborhood"] is None and "transit_service" not in other
    assert {"zip_area_names.csv", "transit_service.csv"} <= set(enriched["data_version"])


def test_repository_names_cover_snapshot_and_resolve_neighborhoods():
    engine = Recommender(Path(__file__).resolve().parents[1] / "data")
    named = [
        a["zip"] for a in engine.areas if engine.geography.get(a["zip"], {}).get("neighborhood")
    ]
    assert len(named) == len(engine.areas)
    assert engine.resolve_near(("Little Haiti", "Brickell Key")) == {
        "Little Haiti": ["33150"],
        "Brickell Key": ["33131"],
    }


def test_low_noise_tag_joins_the_vector_only_when_requested(tmp_path):
    engine = census_snapshot(
        tmp_path,
        [area("00001"), area("00002"), area("00003")],
        {
            "00001": (90, 0.4, 40, 30, 100),
            "00002": (40, 0.7, 5, 20, 100),
            "00003": (2, 0.0, 1, 1, 100),
        },
    )
    calm = engine.recommend(request(tags=["low_noise"]))
    assert [row["zip"] for row in calm["results"]] == ["00003", "00001", "00002"]
    assert calm["feature_order"] == ["low_noise"]
    plain = engine.recommend(request())
    assert "low_noise" not in plain["feature_order"]
    quiet = engine.recommend(request(tags=["quiet"]))
    assert any("residential character" in text for text in quiet["warnings"])
    cosine = Recommender(tmp_path, scorer="cosine")
    assert "low_noise" not in cosine.recommend(request())["feature_order"]


def test_low_noise_needs_census_features(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=1)])
    result = engine.recommend(request(tags=["low_noise"]))
    assert result["status"] == "no_matches"
    assert result["excluded_counts"]["missing_features"] == 1
    assert any("census feature set" in text for text in result["warnings"])


def test_neighborhood_scoring_counts_every_residential_zip(tmp_path):
    engine = snapshot(
        tmp_path, [area("00001", transit=1), area("00002", transit=0.9), area("00003")]
    )
    profile = dict(
        request(),
        profile_id="t",
        expected_relevant_zips=["00001"],
        expected_neighborhoods=["Town", "Other"],
    )
    zip_only = evaluate(engine, [profile])
    assert zip_only["summary"]["3"]["precision"] == pytest.approx(1 / 3)
    assert zip_only["summary"]["3"]["neighborhood_coverage"] is None
    mapped = evaluate(engine, [profile], {"Town": ["00001", "00002"], "Other": ["00009"]})
    assert mapped["summary"]["3"]["precision"] == pytest.approx(2 / 3)
    assert mapped["summary"]["3"]["zip_label_precision"] == pytest.approx(1 / 3)
    assert mapped["summary"]["3"]["neighborhood_coverage"] == 0.5
    with pytest.raises(ValueError, match="unknown neighborhoods"):
        evaluate(engine, [profile], {"Town": ["00001"]})


def test_repository_profiles_name_known_neighborhoods():
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / "eval/neighborhood_zips.json").read_text())["neighborhoods"]
    for profile in json.loads((root / "eval/recommendation_profiles.json").read_text()):
        assert set(profile["expected_neighborhoods"]) <= set(mapping)
        named = {z for n in profile["expected_neighborhoods"] for z in mapping[n]}
        assert set(profile["expected_relevant_zips"]) <= named


@pytest.mark.parametrize(
    "name, status",
    [
        ("heldout_profiles_draft.json", "draft_for_advisor_review"),
        ("heldout_profiles_generated.json", "generated_pending_advisor_review"),
    ],
)
def test_heldout_sets_are_valid_but_not_evaluated_here(name, status):
    # Structure only: the advisor reviews expected matches before anyone scores these sets.
    root = Path(__file__).resolve().parents[1]
    draft = json.loads((root / "eval" / name).read_text())
    mapping = json.loads((root / "eval/neighborhood_zips.json").read_text())["neighborhoods"]
    assert draft["status"] == status
    keys = ("budget_max", "household", "housing_preference", "tags", "weights", "near")
    for profile in draft["profiles"]:
        Request.parse({k: profile[k] for k in keys if k in profile})
        assert set(profile["expected_neighborhoods"]) <= set(mapping), profile["profile_id"]
        assert set(profile["not_relevant_neighborhoods"]) <= set(mapping)
        assert not set(profile["expected_neighborhoods"]) & set(
            profile["not_relevant_neighborhoods"]
        )


def test_hud_rent_matches_household_unit_size(tmp_path):
    census_snapshot(
        tmp_path,
        [area("00001", 1500), area("00002", 1500), area("00003", 1500)],
        {z: (10, 0.1, 10, 10, 100) for z in ("00001", "00002", "00003")},
    )
    units = ["efficiency", "one_bedroom", "two_bedroom", "three_bedroom", "four_bedroom"]
    write_csv(
        tmp_path / "rents_hud.csv",
        ["zip", *units, "source"],
        [
            {
                "zip": "00001",
                "efficiency": 1200,
                "one_bedroom": 1400,
                "two_bedroom": 1900,
                "three_bedroom": 2400,
                "four_bedroom": 2800,
                "source": "test",
            },
            {
                "zip": "00002",
                "efficiency": 1600,
                "one_bedroom": 1800,
                "two_bedroom": 2300,
                "three_bedroom": 2800,
                "four_bedroom": 3200,
                "source": "test",
            },
        ],
    )
    engine = Recommender(tmp_path)
    alone = engine.recommend(request(budget_max=1500))
    assert [r["zip"] for r in alone["results"]] == ["00001"]
    assert (
        alone["results"][0]["rent_usd"] == 1400 and "1-bedroom" in alone["results"][0]["rent_basis"]
    )
    assert alone["excluded_counts"] == {"missing_rent": 1, "over_budget": 1, "missing_features": 0}
    couple = engine.recommend(request(budget_max=2000, household="with_co_leaser"))
    assert [(r["zip"], r["rent_usd"]) for r in couple["results"]] == [("00001", 1900)]
    shared = engine.recommend(
        request(budget_max=1300, housing_preference="co_living", tags=["co_living"])
    )
    assert [(r["zip"], r["rent_usd"]) for r in shared["results"]] == [("00001", 1200)]
    assert any("studio rent stands in" in text for text in shared["warnings"])
    assert any("not an asking rent" in text for text in alone["warnings"])
    assert alone["results"][0]["median_rent_usd"] == 1500


def test_hud_basis_skips_zips_without_a_rental_market(tmp_path):
    census_snapshot(
        tmp_path,
        [area("00001", ""), area("00002", 1500)],
        {z: (10, 0.1, 10, 10, 100) for z in ("00001", "00002")},
    )
    hud(tmp_path, {"00001": 1000, "00002": 1000})
    result = Recommender(tmp_path).recommend(request(budget_max=1500))
    assert [r["zip"] for r in result["results"]] == ["00002"]
    assert result["excluded_counts"]["missing_rent"] == 1


def test_rent_basis_options(tmp_path):
    snapshot(tmp_path, [area("00001", 1500, transit=1)])
    assert Recommender(tmp_path, feature_set="provided").rent_basis == "acs"
    with pytest.raises(DataError, match="rents_hud.csv"):
        Recommender(tmp_path, feature_set="provided", rent_basis="hud")
    with pytest.raises(ValueError):
        Recommender(tmp_path, feature_set="provided", rent_basis="zillow")


def listings(tmp_path, rows):
    write_csv(
        tmp_path / "co_living_listings.csv",
        ["property", "zip", "per_bedroom_rent_from", "per_bedroom_rent_to", "observed", "sources"],
        [
            dict(
                zip(("property", "zip", "per_bedroom_rent_from", "per_bedroom_rent_to"), r),
                observed="2026-11-09",
                sources="test",
            )
            for r in rows
        ],
    )


def coliving_request(budget):
    return request(budget_max=budget, housing_preference="co_living", tags=["co_living"])


def test_co_living_uses_listed_properties_and_per_bedroom_rent(tmp_path):
    census_snapshot(
        tmp_path,
        [area("00001", 1500), area("00002", 1500), area("00003", 1500)],
        {z: (10, 0.1, 10, 10, 100) for z in ("00001", "00002", "00003")},
    )
    listings(
        tmp_path,
        [("Flow", "00001", 1750, 2200), ("i5", "00001", 1299, 1626), ("Other", "00002", 1900, "")],
    )
    engine = Recommender(tmp_path)
    mid = engine.recommend(coliving_request(1500))
    assert [r["zip"] for r in mid["results"]] == ["00001"]
    assert mid["results"][0]["rent_usd"] == 1299
    assert [x["property"] for x in mid["results"][0]["co_living_listings"]] == ["i5"]
    assert mid["excluded_counts"] == {"missing_rent": 1, "over_budget": 1, "missing_features": 0}
    assert "co-living listings" in mid["results"][0]["rent_basis"]
    assert any("listed private bedroom" in text for text in mid["warnings"])
    high = engine.recommend(coliving_request(2000))
    assert [r["zip"] for r in high["results"]] == ["00001", "00002"]
    assert engine.recommend(coliving_request(1200))["status"] == "no_matches"
    own = engine.recommend(request(budget_max=1500))
    assert "co_living_listings" not in own["results"][0]


def test_co_living_without_listings_file_uses_studio_stand_in(tmp_path):
    census_snapshot(tmp_path, [area("00001", 1500)], {"00001": (10, 0.1, 10, 10, 100)})
    result = Recommender(tmp_path).recommend(coliving_request(1500))
    assert [r["zip"] for r in result["results"]] == ["00001"]
    assert any("studio rent stands in" in text for text in result["warnings"])


@pytest.mark.parametrize(
    "rows",
    [
        [("Flow", "00001", 1750, 2200), ("flow", "00001", 1800, 1900)],
        [("Flow", "00001", 0, "")],
        [("Flow", "00001", 2000, 1500)],
    ],
)
def test_bad_co_living_listings_fail_explicitly(tmp_path, rows):
    census_snapshot(tmp_path, [area("00001", 1500)], {"00001": (10, 0.1, 10, 10, 100)})
    listings(tmp_path, rows)
    with pytest.raises(DataError):
        Recommender(tmp_path)


def test_listing_backed_results_report_listing_provenance(tmp_path):
    census_snapshot(tmp_path, [area("00001", 1500)], {"00001": (10, 0.1, 10, 10, 100)})
    listings(tmp_path, [("i5", "00001", 1299, 1626)])
    result = Recommender(tmp_path).recommend(coliving_request(1500))
    assert result["results"][0]["rent_source"] == "co_living_listings.csv"
    assert not any("HUD Small Area Fair Market Rent" in text for text in result["warnings"])
    assert any("per-bedroom 'from' price" in text for text in result["warnings"])


def test_empty_listings_registry_means_no_co_living(tmp_path):
    census_snapshot(tmp_path, [area("00001", 1500)], {"00001": (10, 0.1, 10, 10, 100)})
    listings(tmp_path, [])
    result = Recommender(tmp_path).recommend(coliving_request(1500))
    assert result["status"] == "no_matches"
    assert not any("studio rent stands in" in text for text in result["warnings"])


def test_quiet_and_low_noise_do_not_count_noise_twice(tmp_path):
    engine = census_snapshot(
        tmp_path,
        [area("00001"), area("00002")],
        {"00001": (90, 0.4, 40, 30, 100), "00002": (2, 0.0, 1, 1, 100)},
    )
    both = engine.recommend(request(tags=["quiet", "low_noise"]))
    assert both["feature_order"] == ["quiet"]
    assert any("not counted a second time" in text for text in both["warnings"])
    assert engine.recommend(request(tags=["low_noise"]))["feature_order"] == ["low_noise"]


def test_neighborhood_only_profiles_evaluate(tmp_path):
    engine = snapshot(tmp_path, [area("00001", transit=1), area("00002", transit=0.5)])
    profile = dict(request(), profile_id="h", expected_neighborhoods=["Town"])
    report = evaluate(engine, [profile], {"Town": ["00002"]})
    assert report["summary"]["3"]["precision"] == pytest.approx(1 / 3)
    assert report["summary"]["3"]["zip_label_precision"] is None
    with pytest.raises(ValueError, match="needs expected_relevant_zips"):
        evaluate(engine, [profile])


def test_repository_heldout_sets_can_be_scored_once_approved():
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / "eval/neighborhood_zips.json").read_text())["neighborhoods"]
    engine = Recommender(root / "data")
    for name in ("heldout_profiles_draft.json", "heldout_profiles_generated.json"):
        profiles = json.loads((root / "eval" / name).read_text())["profiles"]
        report = evaluate(engine, profiles, mapping)
        assert len(report["profiles"]) == 2 * len(profiles)


def test_missing_neighborhood_mapping_path_is_an_error(monkeypatch, capsys):
    from flow_neighborhoods import evaluate as module

    monkeypatch.setattr("sys.argv", ["evaluate", "--neighborhoods", "eval/no_such_file.json"])
    with pytest.raises(SystemExit):
        module.main()
    assert "neighborhood mapping not found" in capsys.readouterr().err
