"""Read-only stdio MCP server exposing recommend and ethics; no model API needed."""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .contracts import ValidationError
from .data import DataError
from .engine import SCORERS
from .ethics import ethics
from .tools import RecommendationTools

LOGGER = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

RECOMMEND_SCHEMA = {
    "type": "object",
    "properties": {
        "budget_max": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "Total household monthly budget in USD, including co-leasers combined.",
        },
        "household": {"type": "string", "enum": ["alone", "with_co_leaser"]},
        "housing_preference": {"type": "string", "enum": ["own_apartment", "co_living"]},
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Lifestyle priorities: transit, social, quiet, pet_friendly, walkable, co_living. "
                "Case/whitespace are normalized and duplicates removed. Empty means clarify."
            ),
        },
        "k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
    },
    "required": ["budget_max", "household", "housing_preference", "tags"],
    "additionalProperties": False,
}
ETHICS_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "status"],
    "properties": {
        "schema_version": {"type": "string"},
        "status": {"enum": ["ok", "no_matches", "needs_clarification", "error"]},
    },
    "additionalProperties": True,
}


def result(payload: dict, *, is_error: bool = False) -> CallToolResult:
    """Serve structured JSON and matching text for older MCP clients."""
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, allow_nan=False))],
        structuredContent=payload,
        isError=is_error,
    )


def error(code: str, message: str) -> CallToolResult:
    return result(
        {"schema_version": "1", "status": "error", "error": {"code": code, "message": message}},
        is_error=True,
    )


def create_server(data_dir: str | Path = DEFAULT_DATA_DIR, scorer: str = "mean") -> Server:
    """Create a server without loading CSVs or contacting any external service."""
    backend = RecommendationTools(data_dir, scorer)
    server = Server(
        "flow-neighborhoods",
        instructions=(
            "Read ethics before use and enforce its policy before dispatching recommendations. "
            "Rankings come from Python. Preserve tool warnings, evidence labels and empty states. "
            "This server provides recommend and ethics only; no live listings or tenant scoring."
        ),
    )
    annotations = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
    tools = [
        Tool(
            name="recommend",
            description=(
                "Rank Miami-Dade ZIPs using total monthly budget, explicit household, housing "
                "preference and lifestyle tags. Apply hard budget filtering before ranking. "
                "Returns snapshot estimates and labeled demo evidence, never real listings. "
                "The agent must refuse prohibited requests before calling this tool."
            ),
            inputSchema=RECOMMEND_SCHEMA,
            outputSchema=OUTPUT_SCHEMA,
            annotations=annotations,
        ),
        Tool(
            name="ethics",
            description=(
                "Return the versioned responsible-use policy, prohibited uses, synthetic-data "
                "labels, data limitations and agent enforcement requirements. No arguments. "
                "Describes policy; does not classify a user prompt or enforce agent routing."
            ),
            inputSchema=ETHICS_SCHEMA,
            outputSchema=OUTPUT_SCHEMA,
            annotations=annotations,
        ),
    ]
    validators = {tool.name: Draft202012Validator(tool.inputSchema) for tool in tools}

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return tools

    # We validate against the published schema here to return one stable error envelope,
    # with no type coercion or silent dropping of demographic/unsupported arguments.
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        if name not in validators:
            return error("unknown_tool", "This server provides recommend and ethics only.")
        if not validators[name].is_valid(arguments):
            return error(
                "invalid_arguments",
                "Arguments must match the tool's inputSchema; unsupported fields are rejected.",
            )
        try:
            payload = backend.recommend(arguments) if name == "recommend" else ethics()
            return result(payload)
        except ValidationError as exc:
            return error("invalid_arguments", str(exc))
        except (DataError, OSError, UnicodeError):
            LOGGER.exception("Recommendation snapshot could not be loaded")
            return error(
                "data_unavailable",
                "The configured snapshot is missing, unreadable or invalid. "
                "Check --data-dir and the prepared CSV schemas; no rent fallback was used.",
            )
        except Exception:
            LOGGER.exception("Tool execution failed")
            return error("internal_error", "Tool execution failed; check the server's stderr log.")

    return server


async def serve(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="Flow recommend/ethics MCP server (stdio)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--scorer", choices=list(SCORERS), default="mean")
    args = parser.parse_args()
    # Never print diagnostics to stdout: it belongs exclusively to the MCP transport.
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(serve(create_server(args.data_dir, args.scorer)))


if __name__ == "__main__":
    main()
