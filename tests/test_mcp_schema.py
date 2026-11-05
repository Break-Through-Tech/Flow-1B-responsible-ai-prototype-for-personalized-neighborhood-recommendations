import asyncio
import csv
import json
import os
import sys
from pathlib import Path

import pytest

from flow_neighborhoods import Recommender
from flow_neighborhoods.data import DataError
from flow_neighborhoods.tools.schema import DATASETS, NO_NOTE, schema

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def copy_data(tmp_path):
    for name in DATASETS:
        (tmp_path / name).write_bytes((DATA / name).read_bytes())
    return tmp_path


def unused_engine():
    # schema reads files directly; the engine argument only keeps the signature uniform.
    return None


def test_describes_every_known_file_on_repository_data():
    result = schema(unused_engine(), DATA)
    assert result["status"] == "ok"
    assert [f["file"] for f in result["files"]] == list(DATASETS)
    for entry in result["files"]:
        assert entry["row_count"] > 0 and entry["columns"]
    json.dumps(result, allow_nan=False)


def test_columns_match_real_file_headers_and_all_have_notes():
    result = schema(unused_engine(), DATA)
    for entry in result["files"]:
        with (DATA / entry["file"]).open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        assert [c["name"] for c in entry["columns"]] == header
        assert all(c["note"] and c["note"] != NO_NOTE for c in entry["columns"]), entry["file"]
    assert result["warnings"] == []


def test_data_types_and_synthetic_label_are_explicit():
    files = {f["file"]: f for f in schema(unused_engine(), DATA)["files"]}
    assert files["area_options_cleaned.csv"]["data_type"] == "synthetic"
    assert "NOT REAL LISTINGS" in files["area_options_cleaned.csv"]["description"]
    assert files["area_features_cleaned.csv"]["data_type"] == "placeholder"
    assert files["public_features_cleaned.csv"]["data_type"] == "real"
    notes = {c["name"]: c["note"] for c in files["area_features.csv"]["columns"]}
    assert "-666666666" in notes["median_rent_usd"]


def test_row_counts_match_files():
    files = {f["file"]: f for f in schema(unused_engine(), DATA)["files"]}
    assert files["public_features_cleaned.csv"]["row_count"] == 78
    assert files["crowd_text_snippets.csv"]["row_count"] == 20


def test_undocumented_column_is_flagged_not_guessed(tmp_path):
    data = copy_data(tmp_path)
    path = data / "crowd_text_snippets.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] += ",mystery"
    lines[1:] = [line + ",x" for line in lines[1:]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = schema(unused_engine(), data)
    entry = next(f for f in result["files"] if f["file"] == "crowd_text_snippets.csv")
    assert entry["columns"][-1] == {"name": "mystery", "note": NO_NOTE}
    assert result["warnings"] == [
        "crowd_text_snippets.csv: column 'mystery' has no description yet"
    ]


def test_header_only_file_has_zero_rows(tmp_path):
    data = copy_data(tmp_path)
    path = data / "crowd_text_snippets.csv"
    path.write_text(path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    files = {f["file"]: f for f in schema(unused_engine(), data)["files"]}
    assert files["crowd_text_snippets.csv"]["row_count"] == 0


def test_missing_file_names_file_not_path(tmp_path):
    data = copy_data(tmp_path)
    (data / "area_features.csv").unlink()
    with pytest.raises(DataError, match="area_features.csv is missing") as info:
        schema(unused_engine(), data)
    assert str(tmp_path) not in str(info.value)


@pytest.mark.parametrize("content", [b"", b"\xff\xfe\x00bad"])
def test_empty_or_undecodable_file_raises_data_error(tmp_path, content):
    data = copy_data(tmp_path)
    (data / "area_features.csv").write_bytes(content)
    with pytest.raises(DataError, match="area_features.csv"):
        schema(unused_engine(), data)


mcp = pytest.importorskip("mcp")


def test_server_registers_read_only_tool_without_arguments():
    from flow_neighborhoods.mcp_server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    tool = tools["schema"]
    assert not tool.input_schema.get("required")
    assert tool.annotations.read_only_hint is True
    assert {"status", "files", "warnings", "guidance"} <= set(tool.output_schema["properties"])


def test_server_maps_missing_data_to_tool_error(tmp_path, monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    from flow_neighborhoods import mcp_server

    monkeypatch.setenv("FLOW_DATA_DIR", str(tmp_path))
    mcp_server.engine.cache_clear()
    monkeypatch.setattr(mcp_server, "engine", lambda: Recommender.__new__(Recommender))
    with pytest.raises(ToolError, match="Neighborhood data is unavailable"):
        asyncio.run(mcp_server.server.call_tool("schema", {}))


def test_stdio_round_trip_on_repository_data():
    """Starts the server the way an MCP client would and calls the tool (fixture R2)."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "flow_neighborhoods.mcp_server"],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "FLOW_DATA_DIR": str(DATA)},
        cwd=str(ROOT),
    )

    async def call():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("schema", {})

    result = asyncio.run(asyncio.wait_for(call(), timeout=60))
    assert not result.is_error
    names = [f["file"] for f in result.structured_content["files"]]
    assert "public_features_cleaned.csv" in names
    assert result.structured_content["warnings"] == []
