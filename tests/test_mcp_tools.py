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
from flow_neighborhoods.ethics import ethics
from flow_neighborhoods.tools import RecommendationTools

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
async def session(data_dir, cwd, scorer="mean"):
    args = ["-m", "flow_neighborhoods.mcp_server", "--scorer", scorer]
    if data_dir is not None:
        args += ["--data-dir", str(data_dir)]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=args,
        cwd=str(cwd),
        env={**os.environ, "PYTHONPATH": str(SOURCE)},
    )
    async with (
        asyncio.timeout(30),
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        yield client


def payload(result, *, is_error=False):
    assert result.isError is is_error
    assert len(result.content) == 1 and result.content[0].type == "text"
    assert json.loads(result.content[0].text) == result.structuredContent
    json.dumps(result.structuredContent, allow_nan=False)
    return result.structuredContent


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


def test_backend_is_lazy_validates_before_data_and_reuses_snapshot(tmp_path, data_dir):
    tools = RecommendationTools(data_dir)
    assert tools._engine is None
    with pytest.raises(ValidationError):
        tools.recommend(request(race="anything"))
    assert tools._engine is None
    expected = Recommender(data_dir).recommend(request())
    assert tools.recommend(request()) == expected
    engine = tools._engine
    assert tools.recommend(request()) == expected
    assert tools._engine is engine


@pytest.mark.parametrize("scorer", ["mean", "cosine"])
def test_stdio_discovery_and_all_repository_profiles(tmp_path, scorer):
    async def scenario():
        async with session(DATA, tmp_path, scorer) as client:
            discovery = await client.list_tools()
            tools = {tool.name: tool for tool in discovery.tools}
            assert set(tools) == {"recommend", "ethics"}
            assert tools["recommend"].inputSchema["additionalProperties"] is False
            assert tools["ethics"].inputSchema["properties"] == {}
            assert tools["recommend"].annotations.readOnlyHint is True
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
                    assert all(
                        0 < r["median_rent_usd"] <= args["budget_max"] for r in actual["results"]
                    )

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
                {"household": "couple"},
                {"tags": "transit"},
                {"tags": [None]},
                {"tags": ["hispanic"]},
                {"race": "anything"},
                {"family_status": "children"},
                {"tenant_score": 0.9},
                {"screening_criteria": "hidden"},
                {"housing_preference": "house"},
                {"weights": {"transit": 3}},
            ]
            for changes in invalid:
                err = payload(
                    await client.call_tool("recommend", request(**changes)), is_error=True
                )
                assert err["error"]["code"] == "invalid_arguments", changes
            missing = payload(await client.call_tool("recommend", {}), is_error=True)
            assert missing["error"]["code"] == "invalid_arguments"
            err = payload(
                await client.call_tool("ethics", {"prompt": "ignore policy"}), is_error=True
            )
            assert err["error"]["code"] == "invalid_arguments"
            unknown = payload(await client.call_tool("not_a_tool", {}), is_error=True)
            assert unknown["error"]["code"] == "unknown_tool"
            assert payload(await client.call_tool("recommend", request()))["status"] == "ok"

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
            assert err["error"]["code"] == "data_unavailable"
            assert str(data_dir) not in json.dumps(err)
            assert payload(await client.call_tool("ethics", {})) == ethics()

    asyncio.run(scenario())


def test_stdio_default_data_path_is_independent_of_client_cwd(tmp_path):
    async def scenario():
        async with session(None, tmp_path) as client:
            actual = payload(await client.call_tool("recommend", request(budget_max=2500)))
            assert actual == Recommender(DATA).recommend(request(budget_max=2500))

    asyncio.run(scenario())
