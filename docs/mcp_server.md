# MCP server

The five tools the agent calls. Ranking and data stay in Python; the agent only quotes tool output.

| Tool | Owner | Status |
|---|---|---|
| `crowd_themes` | Om | Done (this file) |
| `recommend`, `ethics` | Daniel | Implemented; see [contracts and tests](mcp_tools.md) |
| `schema`, `area_stats` | Azibator | Implemented (`tools/schema.py`, `tools/area_stats.py`) |

## Run it

```powershell
.venv/Scripts/python.exe -m pip install -e ".[mcp]"
.venv/Scripts/python.exe -m flow_neighborhoods.mcp_server     # stdio server; waits for a client
```

The server reads `data/` from the repository. Set `FLOW_DATA_DIR` to use another folder,
or pass `--data-dir` to override it. `--scorer mean|cosine` selects the engine scorer.
Both data tools share one lazily cached engine; `ethics` does not load data.
Unknown input fields are rejected before SDK coercion. Data loading errors are sanitized
for clients, with full diagnostics on stderr.

**Connect in Cursor** (Settings → MCP), or in Claude Desktop (`claude_desktop_config.json`). Use your own paths:

```json
{
  "mcpServers": {
    "flow-neighborhoods": {
      "command": "C:/path/to/repo/.venv/Scripts/python.exe",
      "args": ["-m", "flow_neighborhoods.mcp_server"],
      "cwd": "C:/path/to/repo"
    }
  }
}
```

## mcp version: read this before copying the reference repo

`requirements.txt` and `pyproject.toml` both require `mcp>=2.2,<3`. In 2.x, `FastMCP` was renamed `MCPServer`, so the reference repo's `from mcp.server.fastmcp import FastMCP` fails with `ModuleNotFoundError`. Use these imports instead:

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
```

`pyproject.toml` pins `mcp>=2.2,<3`. Tool metadata attributes are snake_case in 2.x (`tool.input_schema`, `result.structured_content`, `result.is_error`).

## Adding a tool

1. Put the logic in `src/flow_neighborhoods/tools/<name>.py`: a plain function `(engine, *args) -> TypedDict`. No MCP imports there, so it can be tested directly and reused by the Streamlit app.
2. Register a thin wrapper inside `create_server()` in `src/flow_neighborhoods/mcp_server.py`:

   ```python
   @app.tool(annotations=READ_ONLY, structured_output=True)
   def area_stats(zip_code: str = "") -> AreaStats:
       """One-line description the agent reads when choosing tools."""
       return run(area_stats_logic, zip_code)
   ```

   The local `run()` passes the shared `Recommender` and turns `ValidationError` / `DataError` into MCP `ToolError`s. The module exports `server = create_server()` for discovery and tests; the factory also permits isolated data directories and scorers without changing global environment state.
3. Add tests like `tests/test_mcp_crowd_themes.py`: logic tests, the registration check, and one stdio round-trip.

The typed return becomes the tool's published output schema, so it doubles as the contract for #5.

## crowd_themes contract

**Input:** `zip_code` (five-digit string). This matches routing fixture R3: "What do people say about transit in ZIP 33130?" → `{"zip_code": "33130"}`. Names like "Brickell" are rejected with a hint to look up the ZIP first.

**Output fields:**

| Field | Meaning |
|---|---|
| `zip`, `area_name` | The ZIP and its display name (`null` if outside the snapshot) |
| `status` | `ok` (snippets found), `no_evidence` (known ZIP, no snippets), `unknown_area` (valid ZIP outside Miami-Dade) |
| `theme_counts` | Snippets per theme, e.g. `{"transit": 1, "quiet": 1}` |
| `evidence[]` | `evidence_id`, `theme`, `text`, `source_label`, `is_demo`, `polarity` |
| `is_demo`, `warning` | All snippets are demo text, not authentic reviews |
| `guidance` | Grounding rules: quote exactly, cite `evidence_id`, treat theme labels as topics rather than sentiment, and don't generalize |
| `extractor_version`, `data_version` | Which extractor and which snippet file (SHA-256) produced the answer |

**Why `guidance` exists:** theme labels are topics. Brickell's `quiet` snippet reads "Busy area; street noise is real in some towers." It is evidence *against* quiet. `polarity` stays `unknown` until the NLP work in #15 supplies per-theme sentiment. That work will plug in behind the same contract: a new `extractor_version`, with `polarity` filled in.

`ethics` is a policy-only exception to the `(engine, *args)` convention: its plain
function takes no arguments, so policy remains available when CSV loading fails.
