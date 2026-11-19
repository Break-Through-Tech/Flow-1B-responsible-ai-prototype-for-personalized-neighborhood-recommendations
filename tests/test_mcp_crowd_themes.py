import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from test_recommender import area, snapshot, write_csv

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ValidationError
from flow_neighborhoods.data import DataError
from flow_neighborhoods.tools.crowd_themes import crowd_themes

ROOT = Path(__file__).resolve().parents[1]


def with_snippets(tmp_path, rows):
    snapshot(tmp_path, [area("00001"), area("00002")])
    write_csv(
        tmp_path / "crowd_text_snippets.csv",
        ["snippet_id", "zip", "source", "theme", "text"],
        [dict(zip(("snippet_id", "zip", "source", "theme", "text"), row)) for row in rows],
    )
    return Recommender(tmp_path, feature_set="provided")


def test_returns_evidence_counts_and_grounding_rules(tmp_path):
    engine = with_snippets(
        tmp_path,
        [
            ("T1", "00001", "demo", "quiet", "Not quiet at night."),
            ("T2", "00001", "demo", "transit", "Bus stop outside."),
            ("T3", "00001", "demo", "quiet", "Calm streets."),
        ],
    )
    result = crowd_themes(engine, " 00001 ")
    assert result["status"] == "ok"
    assert result["area_name"] == "Area 00001"
    assert result["theme_counts"] == {"quiet": 2, "transit": 1}
    assert [e["evidence_id"] for e in result["evidence"]] == ["T1", "T2", "T3"]
    assert all(e["is_demo"] for e in result["evidence"])
    polarity = {e["evidence_id"]: e["polarity"] for e in result["evidence"]}
    assert polarity["T1"] == "negative" and polarity["T3"] == "positive"  # NLP sentiment
    assert result["theme_polarity"]["quiet"] == {"negative": 1, "positive": 1}
    assert result["nlp_tags"] == []  # no data/nlp index in this fixture
    assert "evidence against quiet" in result["guidance"]
    assert list(result["data_version"]) == ["crowd_text_snippets.csv"]
    json.dumps(result, allow_nan=False)


def test_safety_mentions_are_flagged_not_scored(tmp_path):
    engine = with_snippets(
        tmp_path, [("T1", "00001", "demo", "social", "I felt unsafe walking home at night.")]
    )
    evidence = crowd_themes(engine, "00001")["evidence"][0]
    assert evidence["needs_review"] is True and evidence["polarity"] == "needs_review"
    assert "safe or unsafe" in crowd_themes(engine, "00001")["guidance"]


def test_without_nlp_polarity_stays_unknown(tmp_path, monkeypatch):
    from flow_neighborhoods import nlp_bridge

    monkeypatch.setattr(nlp_bridge, "analyze", None)
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "quiet", "Not quiet at night.")])
    result = crowd_themes(engine, "00001")
    assert result["evidence"][0]["polarity"] == "unknown"
    assert result["extractor_version"] == "provided-label-lookup-v1"


def test_repository_nlp_tags_are_verified_quotes():
    from flow_neighborhoods import Recommender as Engine

    engine = Engine(ROOT / "data")
    result = crowd_themes(engine, "33130")
    assert result["theme_polarity"]["quiet"] == {"negative": 1}  # "Busy area; street noise..."
    texts = {e["evidence_id"]: e["text"].lower() for e in engine.crowd_themes("33130")["evidence"]}
    tags = {t["tag"]: t for t in result["nlp_tags"]}
    assert "noisy" in tags
    for tag in result["nlp_tags"]:
        for quote in tag["quotes"]:
            assert quote["quote"].lower() in texts[quote["snippet_id"]], quote


def test_distinguishes_no_evidence_from_unknown_area(tmp_path):
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "social", "Lively.")])
    assert crowd_themes(engine, "00002")["status"] == "no_evidence"
    unknown = crowd_themes(engine, "99999")
    assert unknown["status"] == "unknown_area"
    assert unknown["area_name"] is None and unknown["evidence"] == []


@pytest.mark.parametrize("bad", ["Brickell", "3313", "331300", "", 33130, None])
def test_rejects_malformed_zip(tmp_path, bad):
    engine = with_snippets(tmp_path, [])
    with pytest.raises(ValidationError, match="five-digit ZIP"):
        crowd_themes(engine, bad)


def test_returned_evidence_cannot_mutate_engine(tmp_path):
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "social", "Lively.")])
    crowd_themes(engine, "00001")["evidence"][0]["text"] = "changed"
    assert crowd_themes(engine, "00001")["evidence"][0]["text"] == "Lively."


def write_index(tmp_path, locations):
    directory = tmp_path / "nlp"
    directory.mkdir(exist_ok=True)
    path = directory / "location_tags.json"
    path.write_text(json.dumps({"locations": locations}), encoding="utf-8")
    return path


def indexed_tag(*evidence):
    return {"level": "parent", "count": 999, "evidence": list(evidence)}


def test_index_quotes_are_checked_against_the_active_zip_and_counts_rebuilt(tmp_path):
    engine = with_snippets(
        tmp_path,
        [
            ("T1", "00001", "demo", "transit", "Bus stop outside."),
            ("T2", "00002", "demo", "quiet", "Calm streets."),
        ],
    )
    valid = {"snippet_id": "T1", "quote": "Bus stop outside.", "is_demo": False}
    write_index(
        tmp_path,
        {
            "00001": {
                "tags": {
                    "transit": indexed_tag(
                        valid,
                        valid,
                        {"snippet_id": "T1", "quote": "Invented quote"},
                        {"snippet_id": "T1", "quote": " \t "},
                        {"snippet_id": "T2", "quote": "Calm streets."},
                        {"snippet_id": "missing", "quote": "Bus stop outside."},
                    ),
                    "quiet": indexed_tag({"snippet_id": "T1", "quote": "Peaceful streets."}),
                }
            }
        },
    )
    result = crowd_themes(engine, "00001")
    assert result["nlp_tags"] == [
        {
            "tag": "transit",
            "level": "parent",
            "count": 1,
            "quotes": [{"snippet_id": "T1", "quote": "Bus stop outside.", "is_demo": True}],
        }
    ]
    assert "unsupported by the current ZIP/snippet snapshot were omitted" in result["warning"]


def test_refreshing_snippets_cannot_publish_old_index_quotes(tmp_path):
    with_snippets(tmp_path, [("T1", "00001", "demo", "transit", "Bus stop outside.")])
    write_index(
        tmp_path,
        {
            "00001": {
                "tags": {
                    "transit": indexed_tag({"snippet_id": "T1", "quote": "Bus stop outside."}),
                }
            }
        },
    )
    write_csv(
        tmp_path / "crowd_text_snippets.csv",
        ["snippet_id", "zip", "source", "theme", "text"],
        [
            {
                "snippet_id": "T1",
                "zip": "00001",
                "source": "demo",
                "theme": "quiet",
                "text": "Replacement review.",
            }
        ],
    )
    result = crowd_themes(Recommender(tmp_path, feature_set="provided"), "00001")
    assert result["evidence"][0]["text"] == "Replacement review."
    assert result["nlp_tags"] == []
    assert "rebuild the NLP index" in result["warning"]


def test_index_hash_identifies_the_exact_file_that_supplied_tags(tmp_path):
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "transit", "Bus stop outside.")])
    locations = {
        "00001": {
            "tags": {"transit": indexed_tag({"snippet_id": "T1", "quote": "Bus stop outside."})}
        }
    }
    path = write_index(tmp_path, locations)
    first = crowd_themes(engine, "00001")
    assert (
        first["data_version"]["nlp/location_tags.json"]
        == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    locations["00001"]["tags"]["transit"]["level"] = "specific"
    write_index(tmp_path, locations)
    second = crowd_themes(engine, "00001")
    assert (
        first["data_version"]["crowd_text_snippets.csv"]
        == second["data_version"]["crowd_text_snippets.csv"]
    )
    assert (
        first["data_version"]["nlp/location_tags.json"]
        != second["data_version"]["nlp/location_tags.json"]
    )


@pytest.mark.parametrize("zip_code,status", [("00002", "no_evidence"), ("99999", "unknown_area")])
def test_index_cannot_supply_evidence_for_another_zip(tmp_path, zip_code, status):
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "quiet", "Calm streets.")])
    write_index(
        tmp_path,
        {
            zip_code: {
                "tags": {
                    "quiet": indexed_tag({"snippet_id": "T1", "quote": "Calm streets."}),
                }
            }
        },
    )
    result = crowd_themes(engine, zip_code)
    assert result["status"] == status and result["nlp_tags"] == []


@pytest.mark.parametrize("content", ["{bad", "[]", '{"locations": []}'])
def test_malformed_index_is_an_explicit_data_error(tmp_path, content):
    engine = with_snippets(tmp_path, [("T1", "00001", "demo", "quiet", "Calm streets.")])
    path = write_index(tmp_path, {})
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DataError, match="NLP tag index"):
        crowd_themes(engine, "00001")


def test_server_registers_read_only_tool_with_schema():
    from flow_neighborhoods.mcp_server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    tool = tools["crowd_themes"]
    assert tool.input_schema["required"] == ["zip_code"]
    assert tool.annotations.read_only_hint is True
    assert {"zip", "status", "evidence", "guidance"} <= set(tool.output_schema["properties"])


def test_server_maps_bad_input_to_tool_error():
    from mcp.server.mcpserver.exceptions import ToolError

    from flow_neighborhoods.mcp_server import server

    with pytest.raises(ToolError, match="five-digit ZIP"):
        asyncio.run(server.call_tool("crowd_themes", {"zip_code": "Brickell"}))


def test_stdio_round_trip_on_repository_data():
    """Starts the server the way an MCP client would and calls the tool (fixture R3)."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flow_neighborhoods.mcp_server"],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "FLOW_DATA_DIR": str(ROOT / "data")},
        cwd=str(ROOT),
    )

    async def call():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            ok = await session.call_tool("crowd_themes", {"zip_code": "33130"})
            bad = await session.call_tool("crowd_themes", {"zip_code": "Brickell"})
            return ok, bad

    ok, bad = asyncio.run(asyncio.wait_for(call(), timeout=60))
    assert not ok.is_error
    assert ok.structured_content["area_name"] == "Brickell"
    assert ok.structured_content["theme_counts"]["transit"] >= 1
    assert bad.is_error
