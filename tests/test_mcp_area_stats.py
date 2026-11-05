import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from test_recommender import area, snapshot, write_csv

from flow_neighborhoods.contracts import ALL_FEATURES, ValidationError
from flow_neighborhoods.data import DataError
from flow_neighborhoods.tools.area_stats import PUBLIC_FILE, area_stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

PUBLIC_FIELDS = [
    "zip",
    "population",
    "B11016_001E",
    "B25003_002E",
    "B25003_003E",
    "median_rent_usd",
    "winsorized_B25077_001E",
    "winsorized_moved_different_house_pct",
]


def with_public(tmp_path, rows):
    # 00001 and 00002 are in the snapshot; only the rows given get public stats.
    engine = snapshot(tmp_path, [area("00001", 1500, transit=1, quiet=0.5), area("00002", None)])
    write_csv(tmp_path / PUBLIC_FILE, PUBLIC_FIELDS, [dict(zip(PUBLIC_FIELDS, r)) for r in rows])
    return engine


def full_row(zip_code="00001"):
    return (zip_code, "1000", "400", "100", "300", "1500", "250000", "0.12")


def test_returns_labeled_public_stats_and_separate_lifestyle_scores(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    result = area_stats(engine, tmp_path, " 00001 ")
    assert result["status"] == "ok"
    assert result["area_name"] == "Area 00001"
    assert result["public_stats"] == {
        "population": 1000.0,
        "households": 400.0,
        "owner_occupied_units": 100.0,
        "renter_occupied_units": 300.0,
        "median_rent_usd": 1500.0,
        "median_home_value_usd": 250000.0,
        "moved_different_house_pct": 0.12,
    }
    assert set(result["lifestyle_scores"]) == set(ALL_FEATURES)
    assert result["lifestyle_scores"]["transit"] == 1
    assert "placeholder" in result["guidance"]
    assert "cleaned" in result["warning"]
    json.dumps(result, allow_nan=False)


def test_constant_scores_are_flagged(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    # In this snapshot every feature is constant except transit and quiet.
    flagged = area_stats(engine, tmp_path, "00001")["constant_scores"]
    assert flagged == sorted(engine.constant_features)
    assert "transit" not in flagged


def test_blank_public_cell_is_null_not_zero(tmp_path):
    row = list(full_row())
    row[5] = ""
    engine = with_public(tmp_path, [tuple(row)])
    assert area_stats(engine, tmp_path, "00001")["public_stats"]["median_rent_usd"] is None


def test_known_zip_without_public_row_is_not_estimated(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    result = area_stats(engine, tmp_path, "00002")
    assert result["status"] == "no_public_stats"
    assert result["public_stats"] == {}
    assert result["area_name"] == "Area 00002"


def test_unknown_zip_is_distinct_from_no_public_stats(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    result = area_stats(engine, tmp_path, "99999")
    assert result["status"] == "unknown_area"
    assert result["area_name"] is None and result["public_stats"] == {}
    assert result["lifestyle_scores"] == {}


def test_blank_zip_lists_every_area(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    for blank in ("", "  "):
        result = area_stats(engine, tmp_path, blank)
        assert result["status"] == "all_areas"
        assert result["area_count"] == 2
        assert [a["zip"] for a in result["areas"]] == ["00001", "00002"]
        assert result["areas"][0]["population"] == 1000.0
        assert result["areas"][1]["population"] is None
        assert result["public_stats"] == {}


def test_default_argument_means_all_areas(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    assert area_stats(engine, tmp_path)["status"] == "all_areas"


@pytest.mark.parametrize("bad", ["Wynwood", "3313", "331270", "3312a", 33127, None])
def test_rejects_malformed_zip(tmp_path, bad):
    engine = with_public(tmp_path, [full_row()])
    with pytest.raises(ValidationError):
        area_stats(engine, tmp_path, bad)


def test_missing_public_file_names_file_not_path(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    (tmp_path / PUBLIC_FILE).unlink()
    with pytest.raises(DataError, match="public_features_cleaned.csv is missing") as info:
        area_stats(engine, tmp_path, "00001")
    assert str(tmp_path) not in str(info.value)


def test_missing_column_raises_data_error(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    write_csv(tmp_path / PUBLIC_FILE, ["zip", "population"], [{"zip": "00001", "population": "5"}])
    with pytest.raises(DataError, match="missing columns"):
        area_stats(engine, tmp_path, "00001")


def test_undecodable_public_file_raises_data_error(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    (tmp_path / PUBLIC_FILE).write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(DataError):
        area_stats(engine, tmp_path, "00001")


def test_returned_data_cannot_mutate_later_results(tmp_path):
    engine = with_public(tmp_path, [full_row()])
    area_stats(engine, tmp_path, "00001")["lifestyle_scores"]["transit"] = 99
    assert area_stats(engine, tmp_path, "00001")["lifestyle_scores"]["transit"] == 1


def test_repository_data_wynwood_and_missing_public_rows():
    from flow_neighborhoods import Recommender

    engine = Recommender(DATA)
    wynwood = area_stats(engine, DATA, "33127")
    assert wynwood["status"] == "ok" and wynwood["area_name"] == "Wynwood"
    assert wynwood["public_stats"]["population"] == 28306
    assert wynwood["public_stats"]["median_rent_usd"] == 1283
    assert "pet_friendly" in wynwood["constant_scores"]
    for zip_code in ("33039", "33101"):
        assert area_stats(engine, DATA, zip_code)["status"] == "no_public_stats"
    assert area_stats(engine, DATA, "")["area_count"] == 80


mcp = pytest.importorskip("mcp")


def test_server_registers_read_only_tool_with_optional_zip():
    from flow_neighborhoods.mcp_server import server

    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    tool = tools["area_stats"]
    assert not tool.input_schema.get("required")
    assert "zip_code" in tool.input_schema["properties"]
    assert tool.annotations.read_only_hint is True
    assert {"zip", "status", "public_stats", "guidance"} <= set(tool.output_schema["properties"])


def test_server_maps_bad_input_to_tool_error():
    from mcp.server.mcpserver.exceptions import ToolError

    from flow_neighborhoods.mcp_server import server

    with pytest.raises(ToolError, match="five-digit ZIP"):
        asyncio.run(server.call_tool("area_stats", {"zip_code": "Wynwood"}))


def test_stdio_round_trip_on_repository_data():
    """Starts the server the way an MCP client would and calls the tool (fixture R4)."""
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
            ok = await session.call_tool("area_stats", {"zip_code": "33127"})
            bad = await session.call_tool("area_stats", {"zip_code": "Wynwood"})
            return ok, bad

    ok, bad = asyncio.run(asyncio.wait_for(call(), timeout=60))
    assert not ok.is_error
    assert ok.structured_content["status"] == "ok"
    assert ok.structured_content["area_name"] == "Wynwood"
    assert bad.is_error
