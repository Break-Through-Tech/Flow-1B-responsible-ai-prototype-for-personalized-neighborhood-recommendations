"""MCP server for the neighborhood tools. Run: python -m flow_neighborhoods.mcp_server

Requires mcp 2.x (`pip install -e ".[mcp]"`). In 2.x, FastMCP is named MCPServer.
Each tool's logic lives in flow_neighborhoods/tools/<name>.py; register it below
with a thin wrapper that maps engine errors to ToolError.

Data directory: $FLOW_DATA_DIR, else the repository's data/ folder.
"""

import os
from functools import cache
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .contracts import ValidationError
from .data import DataError
from .engine import Recommender
from .tools.crowd_themes import CrowdThemes
from .tools.crowd_themes import crowd_themes as crowd_themes_logic

server = MCPServer(
    "flow-neighborhoods",
    instructions=(
        "Tools over a Miami-Dade ZIP snapshot. Rank and quote only from tool output; "
        "never invent rents, listings, reviews or neighborhoods."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def data_dir() -> Path:
    if os.environ.get("FLOW_DATA_DIR"):
        return Path(os.environ["FLOW_DATA_DIR"])
    return Path(__file__).resolve().parents[2] / "data"


@cache
def engine() -> Recommender:
    return Recommender(data_dir())


def run(logic, *args):
    try:
        return logic(engine(), *args)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc
    except (DataError, OSError) as exc:
        raise ToolError(f"Neighborhood data is unavailable: {exc}") from exc


@server.tool(annotations=READ_ONLY, structured_output=True)
def crowd_themes(zip_code: str) -> CrowdThemes:
    """What people say about a Miami-Dade ZIP: review snippets and their theme labels.

    zip_code: five-digit ZIP, e.g. "33130". Returns snippets with evidence IDs, theme
    counts, and status ok / no_evidence / unknown_area. Snippets are demo text and
    theme labels are topics, not sentiment; follow the returned guidance.
    """
    return run(crowd_themes_logic, zip_code)


if __name__ == "__main__":
    server.run()
