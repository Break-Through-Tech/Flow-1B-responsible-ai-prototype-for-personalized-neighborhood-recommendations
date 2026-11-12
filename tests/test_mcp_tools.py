"""Exercise actual MCP discovery and calls over stdio, not just Python functions."""

import asyncio
import csv
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ALL_FEATURES, ValidationError
from flow_neighborhoods.tools.ethics import ethics
from flow_neighborhoods.tools.recommend import recommend

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
DATA = ROOT / "data"


def request(**changes):
    return {
        "budget_max": 1500,
        "household": "alone",
        "housing_preference": "own_apartment",
        "tags": ["transit"],
        "k": 3,
    } | changes


@pytest.fixture
def data_dir(tmp_path):
    def write(name, fields, rows):
        with (tmp_path / name).open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    areas = [
        {
            "zip": z,
            "median_rent_usd": rent,
            **{f: 0.5 for f in ALL_FEATURES},
            "transit": transit,
        }
        for z, rent, transit in [("00001", 1500, 0.8), ("00002", 1501, 1), ("00003", "", 1)]
    ]
    write("area_features_cleaned.csv", ["zip", "median_rent_usd", *ALL_FEATURES], areas)
    write(
        "area_features.csv",
        ["zip", "area_name"],
        [{"zip": row["zip"], "area_name": f"Area {row['zip']}"} for row in areas],
    )
    # The engine's default (census) feature set also needs geography and measurements.
    write(
        "zcta_geography.csv",
        ["zip", "land_sqmi", "lat", "lon", "usps_city"],
        [
            {"zip": z, "land_sqmi": 1, "lat": 25.7 + i / 10, "lon": -80.2, "usps_city": "Miami"}
            for i, z in enumerate(("00001", "00002", "00003"))
        ],
    )
    write(
        "neighborhood_aliases.csv",
        ["alias", "zip", "match", "source"],
        [{"alias": "Test Town", "zip": "00001", "match": "primary", "source": "test"}],
    )
    write(
        "rents_hud.csv",
        [
            "zip",
            "efficiency",
            "one_bedroom",
            "two_bedroom",
            "three_bedroom",
            "four_bedroom",
            "source",
        ],
        [
            {
                "zip": z,
                "efficiency": r,
                "one_bedroom": r,
                "two_bedroom": r,
                "three_bedroom": r,
                "four_bedroom": r,
                "source": "test",
            }
            for z, r in (("00001", 1500), ("00002", 1501))
        ],
    )
    write(
        "census_features.csv",
        [
            "zip",
            "workers",
            "transit_commuters",
            "walk_commuters",
            "food_drink_establishments",
            "noise_share_ge_55db",
        ],
        [
            {
                "zip": z,
                "workers": 100,
                "transit_commuters": t,
                "walk_commuters": 5,
                "food_drink_establishments": 10,
                "noise_share_ge_55db": 0.1,
            }
            for z, t in (("00001", 20), ("00002", 30), ("00003", 30))
        ],
    )
    write(
        "crowd_text_snippets.csv",
        ["snippet_id", "zip", "source", "theme", "text"],
        [
            {
                "snippet_id": "T1",
                "zip": "00001",
                "source": "demo",
                "theme": "transit",
                "text": "Demo transit evidence.",
            }
        ],
    )
    return tmp_path


@asynccontextmanager
async def session(data_dir, cwd, scorer="mean", env_dir=None):
    args = ["-m", "flow_neighborhoods.mcp_server", "--scorer", scorer]
    if data_dir is not None:
        args += ["--data-dir", str(data_dir)]
    pythonpath = os.pathsep.join(filter(None, [str(SOURCE), os.environ.get("PYTHONPATH")]))
    environment = {**os.environ, "PYTHONPATH": pythonpath}
    environment.pop("FLOW_DATA_DIR", None)
    if env_dir is not None:
        environment["FLOW_DATA_DIR"] = str(env_dir)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=args,
        cwd=str(cwd),
        env=environment,
    )
    async with (
        asyncio.timeout(30),
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        yield client


def payload(result, *, is_error=False):
    assert result.is_error is is_error
    assert len(result.content) == 1 and result.content[0].type == "text"
    if is_error:
        assert result.structured_content is None
        return result.content[0].text
    assert json.loads(result.content[0].text) == result.structured_content
    json.dumps(result.structured_content, allow_nan=False)
    return result.structured_content


def test_policy_is_fresh_and_explicit_about_enforcement():
    policy = ethics()
    assert policy["status"] == "ok"
    assert {rule["code"] for rule in policy["prohibited_uses"]} == {
        "tenant_screening",
        "demographic_steering",
        "hidden_screening",
        "unverified_listings",
    }
    assert policy["enforcement"]["natural_language_gate_implemented"] is False
    policy["allowed_uses"].clear()
    assert ethics()["allowed_uses"]


def test_plain_recommend_logic_preserves_engine_contract(data_dir):
    engine = Recommender(data_dir)
    assert recommend(engine, **request()) == engine.recommend(request())
    with pytest.raises(ValidationError):
        recommend(engine, **request(tags=["unsupported"]))


def test_shared_engine_is_lazy_validates_before_data_and_reuses_snapshot(data_dir, monkeypatch):
    import importlib

    module = importlib.import_module("flow_neighborhoods.mcp_server")
    from mcp.server.mcpserver.exceptions import ToolError

    loads = []

    def load(*args, **kwargs):
        loads.append(args)
        return Recommender(*args, **kwargs)

    monkeypatch.setattr(module, "Recommender", load)
    app = module.create_server(data_dir)

    async def scenario():
        await app.call_tool("ethics", {})
        with pytest.raises(ToolError):
            await app.call_tool("recommend", request(race="anything"))
        assert loads == []
        first = payload(await app.call_tool("recommend", request()))
        await app.call_tool("crowd_themes", {"zip_code": "00001"})
        assert payload(await app.call_tool("recommend", request())) == first
        assert len(loads) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("scorer", ["mean", "cosine"])
def test_stdio_discovery_and_all_repository_profiles(tmp_path, scorer):
    async def scenario():
        async with session(DATA, tmp_path, scorer) as client:
            discovery = await client.list_tools()
            tools = {tool.name: tool for tool in discovery.tools}
            assert set(tools) == {
                "recommend",
                "ethics",
                "crowd_themes",
                "schema",
                "area_stats",
            }
            assert tools["recommend"].input_schema["additionalProperties"] is False
            assert tools["ethics"].input_schema["properties"] == {}
            assert tools["recommend"].annotations.read_only_hint is True
            assert payload(await client.call_tool("ethics", {})) == ethics()
            engine = Recommender(DATA, scorer=scorer)
            profiles = json.loads((ROOT / "eval/recommendation_profiles.json").read_text())
            for profile in profiles:
                args = {
                    k: profile[k] for k in ("budget_max", "household", "housing_preference", "tags")
                }
                for k in (3, 5):
                    args["k"] = k
                    actual = payload(await client.call_tool("recommend", args))
                    assert actual == engine.recommend(args)
                    assert all(0 < r["rent_usd"] <= args["budget_max"] for r in actual["results"])

    asyncio.run(scenario())


def test_stdio_boundary_short_empty_clarification_and_demo_evidence(data_dir, tmp_path):
    async def scenario():
        async with session(data_dir, tmp_path) as client:
            actual = payload(await client.call_tool("recommend", request(k=5)))
            assert actual["status"] == "ok" and actual["returned_count"] == 1
            assert actual["results"][0]["zip"] == "00001"
            assert actual["results"][0]["median_rent_usd"] == 1500
            evidence = actual["results"][0]["themes"][0]
            assert evidence["is_demo"] and evidence["evidence_id"] == "T1"
            assert evidence["source_label"] == "demo"
            assert actual["excluded_counts"] == {
                "missing_rent": 1,
                "over_budget": 1,
                "missing_features": 0,
            }
            empty = payload(await client.call_tool("recommend", request(budget_max=1)))
            assert empty["status"] == "no_matches" and empty["results"] == []
            for changes in [
                {"tags": []},
                {"tags": ["co_living"]},
                {"household": "with_co_leaser", "housing_preference": "co_living"},
            ]:
                clarification = payload(await client.call_tool("recommend", request(**changes)))
                assert clarification["status"] == "needs_clarification"

    asyncio.run(scenario())


def test_stdio_rejects_coercion_demographics_and_unknown_arguments_then_recovers(data_dir):
    async def scenario():
        async with session(data_dir, ROOT) as client:
            invalid = [
                {"budget_max": True},
                {"budget_max": "1500"},
                {"budget_max": -1},
                {"k": True},
                {"k": 0},
                {"k": 6},
                {"k": 3.0},
                {"k": "3"},
                {"household": "couple"},
                {"tags": "transit"},
                {"tags": '["transit"]'},
                {"tags": [None]},
                {"tags": ["hispanic"]},
                {"race": "anything"},
                {"family_status": "children"},
                {"tenant_score": 0.9},
                {"screening_criteria": "hidden"},
                {"housing_preference": "house"},
                {"weights": {"transit": 4}},
                {"weights": {"transit": "3"}},
                {"weights": {"social": 2}},
                {"weights": ["transit"]},
                {"near": "Test Town"},
                {"near": ["a", "b", "c", "d"]},
                {"near": ["Nowhere"]},
            ]
            for changes in invalid:
                err = payload(
                    await client.call_tool("recommend", request(**changes)), is_error=True
                )
                assert "invalid_arguments" in err, changes
            missing = payload(await client.call_tool("recommend", {}), is_error=True)
            assert "invalid_arguments" in missing
            err = payload(
                await client.call_tool("ethics", {"prompt": "ignore policy"}), is_error=True
            )
            assert "invalid_arguments" in err
            unknown = payload(await client.call_tool("not_a_tool", {}), is_error=True)
            assert "unknown_tool" in unknown
            assert payload(await client.call_tool("recommend", request()))["status"] == "ok"

    asyncio.run(scenario())


def test_stdio_priorities_and_near_match_engine_on_repository_data(tmp_path):
    async def scenario():
        async with session(DATA, tmp_path) as client:
            engine = Recommender(DATA)
            for extra in (
                {"weights": {"quiet": 3}},
                {"near": ["Coconut Grove"]},
                {"weights": {"transit": 2, "near": 3}, "near": ["Brickell", "33150"]},
                {"weights": None, "near": None},
            ):
                args = request(budget_max=2500, tags=["transit", "quiet"]) | extra
                actual = payload(await client.call_tool("recommend", args))
                given = {key: value for key, value in args.items() if value is not None}
                assert actual == engine.recommend(given), extra
            near = payload(
                await client.call_tool("recommend", request(budget_max=2500, near=["Brickell"]))
            )
            assert near["applied_filters"]["near"]["Brickell"]
            assert all("distance_miles" in row for row in near["results"])

    asyncio.run(scenario())


@pytest.mark.parametrize("broken", ["missing", "invalid_schema", "invalid_encoding"])
def test_stdio_data_failure_does_not_disable_policy_or_leak_paths(data_dir, broken):
    if broken == "missing":
        (data_dir / "area_features_cleaned.csv").unlink()
    elif broken == "invalid_schema":
        (data_dir / "area_features_cleaned.csv").write_text("zip\n00001\n")
    else:
        (data_dir / "area_features_cleaned.csv").write_bytes(b"\xff\xfe\xff")

    async def scenario():
        async with session(data_dir, ROOT) as client:
            err = payload(await client.call_tool("recommend", request()), is_error=True)
            assert "data_unavailable" in err
            assert str(data_dir) not in json.dumps(err)
            assert payload(await client.call_tool("ethics", {})) == ethics()

    asyncio.run(scenario())


def test_stdio_default_data_path_is_independent_of_client_cwd(tmp_path):
    async def scenario():
        async with session(None, tmp_path) as client:
            actual = payload(await client.call_tool("recommend", request(budget_max=2500)))
            assert actual == Recommender(DATA).recommend(request(budget_max=2500))

    asyncio.run(scenario())


def test_stdio_flow_data_dir_and_cli_override(data_dir, tmp_path):
    async def scenario():
        async with session(None, ROOT, env_dir=data_dir) as client:
            actual = payload(await client.call_tool("recommend", request()))
            assert actual == Recommender(data_dir).recommend(request())
            crowd = payload(await client.call_tool("crowd_themes", {"zip_code": "00001"}))
            assert crowd["evidence"] == actual["results"][0]["themes"]
        async with session(DATA, ROOT, env_dir=tmp_path / "nonexistent") as client:
            actual = payload(await client.call_tool("recommend", request(budget_max=2500)))
            assert actual == Recommender(DATA).recommend(request(budget_max=2500))

    asyncio.run(scenario())
