"""Shared SDK 2.x MCP server: thin wrappers around tools/<name>.py logic."""

import argparse
import logging
import os
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

from jsonschema import Draft202012Validator
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, StrictStr

from .contracts import Request, ValidationError
from .data import DataError
from .engine import SCORERS, Recommender
from .tools.area_stats import AreaStats
from .tools.area_stats import area_stats as area_stats_logic
from .tools.crowd_themes import CrowdThemes
from .tools.crowd_themes import crowd_themes as crowd_themes_logic
from .tools.ethics import Ethics
from .tools.ethics import ethics as ethics_logic
from .tools.recommend import Recommendation
from .tools.recommend import recommend as recommend_logic
from .tools.schema import Schema
from .tools.schema import schema as schema_logic

LOGGER = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
Budget = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Count = Annotated[int, Field(strict=True, ge=1, le=5)]


class NeighborhoodServer(MCPServer):
    """Validate raw arguments before the SDK can coerce or discard them.

    MCPServer's generated argument models accept extra keys and parse JSON inside
    strings. Reject those for these tools, especially demographic/screening fields.
    Use public list_tools/call_tool hooks, not SDK private registration internals.
    """

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.input_schema["additionalProperties"] = False
        return tools

    async def call_tool(self, name, arguments, context=None):
        tools = {tool.name: tool for tool in await self.list_tools()}
        if name not in tools:
            raise ToolError(f"unknown_tool: {name}")
        if not Draft202012Validator(tools[name].input_schema).is_valid(arguments):
            raise ToolError("invalid_arguments: Arguments must match the tool's input schema.")
        if name == "recommend":
            try:
                Request.parse(arguments)
            except ValidationError as exc:
                raise ToolError(f"invalid_arguments: {exc}") from exc
        return await super().call_tool(name, arguments, context)


def data_dir() -> Path:
    """Om's FLOW_DATA_DIR convention, otherwise the checkout's prepared data."""
    return Path(os.environ.get("FLOW_DATA_DIR", DEFAULT_DATA_DIR)).expanduser().resolve()


def create_server(directory: str | Path | None = None, scorer: str = "mean") -> MCPServer:
    if scorer not in SCORERS:
        raise ValueError(f"scorer must be one of {', '.join(SCORERS)}.")
    configured = Path(directory).expanduser().resolve() if directory is not None else None
    app = NeighborhoodServer(
        "flow-neighborhoods",
        instructions=(
            "Tools over a Miami-Dade ZIP snapshot. Read ethics and enforce its policy before "
            "calling recommend. Rank and quote only from tool output; preserve warnings, "
            "evidence labels and empty states. Never invent rents, listings or reviews."
        ),
    )

    @cache
    def engine() -> Recommender:
        return Recommender(configured if configured is not None else data_dir(), scorer=scorer)

    def files() -> Path:
        return configured if configured is not None else data_dir()

    def run(logic, *args):
        try:
            return logic(engine(), *args)
        except ValidationError as exc:
            raise ToolError(f"invalid_arguments: {exc}") from exc
        except (DataError, OSError, UnicodeError) as exc:
            LOGGER.exception("Recommendation snapshot could not be loaded")
            raise ToolError(
                "data_unavailable: Neighborhood data is missing, unreadable or invalid; "
                "check FLOW_DATA_DIR or --data-dir. No rent fallback was used."
            ) from exc

    @app.tool(annotations=READ_ONLY, structured_output=True)
    def crowd_themes(zip_code: str) -> CrowdThemes:
        """What people say about a ZIP: demo snippets, evidence IDs and theme counts.

        zip_code is a five-digit string. Labels are topics, not sentiment. Preserve
        demo labels and follow the returned grounding guidance.
        """
        return run(crowd_themes_logic, zip_code)

    @app.tool(annotations=READ_ONLY, structured_output=True)
    def recommend(
        budget_max: Budget,
        household: Literal["alone", "with_co_leaser"],
        housing_preference: Literal["own_apartment", "co_living"],
        tags: list[StrictStr],
        k: Count = 3,
    ) -> Recommendation:
        """Rank ZIPs with a hard total household monthly USD budget; never live listings.

        Tags: transit, social, quiet, pet_friendly, walkable, co_living. Ranking is
        performed by Python. Preserve warnings, demo labels and empty/clarification
        states. The agent must refuse prohibited requests before calling this tool.
        """
        return run(recommend_logic, budget_max, household, housing_preference, tags, k)

    @app.tool(annotations=READ_ONLY, structured_output=True)
    def ethics() -> Ethics:
        """Return responsible-use policy, prohibited uses and snapshot limitations.

        No arguments or dataset required. This describes policy; the agent must
        enforce refusals before calling recommend. It does not classify chat messages.
        """
        return ethics_logic()

    @app.tool(annotations=READ_ONLY, structured_output=True)
    def schema() -> Schema:
        """Describe the data files: each file's columns, a plain-English note per column,
        row counts, and whether the data is real, derived, placeholder or synthetic.

        No arguments. Describe only what is returned; a column with no note must not be
        guessed at. For a ZIP's actual values use area_stats.
        """
        return run(schema_logic, files())

    @app.tool(annotations=READ_ONLY, structured_output=True)
    def area_stats(zip_code: str = "") -> AreaStats:
        """Public statistics for one Miami-Dade ZIP, or a short list of every ZIP if blank.

        zip_code: five-digit ZIP, e.g. "33127" (look up the ZIP for a neighborhood name
        first), or blank for all ZIPs. Returns public Census-style figures plus separate
        placeholder lifestyle scores. Follow the returned guidance; never present
        lifestyle scores as facts.
        """
        return run(area_stats_logic, files(), zip_code)

    return app


server = create_server()


def main() -> None:
    parser = argparse.ArgumentParser(description="Flow neighborhood MCP server (SDK 2.x, stdio)")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--scorer", choices=list(SCORERS), default="mean")
    args = parser.parse_args()
    create_server(args.data_dir, args.scorer).run()


if __name__ == "__main__":
    main()
