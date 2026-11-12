import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from test_recommender import area, snapshot, write_csv

from flow_neighborhoods import Recommender
from flow_neighborhoods.contracts import ValidationError
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
    assert all(e["is_demo"] and e["polarity"] == "unknown" for e in result["evidence"])
    assert "not a sentiment" in result["guidance"]
    assert list(result["data_version"]) == ["crowd_text_snippets.csv"]
    json.dumps(result, allow_nan=False)


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
