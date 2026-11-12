# Compatibility with Om's MCP pattern

Checked November 4, 2026 after fetching the latest GitHub branches.

The earlier recommendation-engine compatibility check was valid, but did not
establish compatibility with Om's newer MCP server. His MCP branch is
`om-mcp-crowd-themes` at `deeeb53`; it uses SDK 2.x, `MCPServer`, typed plain tool
functions in a `tools/` package, and `ToolError` failures. The original Daniel
branch at `fc3991e` instead used SDK 1.x, a low-level server and `tools.py`.
Those implementations could not be combined unchanged.

## Integrated implementation

Om's MCP branch is merged into this branch, preserving his crowd-themes logic
and tests. The recommendation engine and ranking calculations remain unchanged.

- All three tools register on one SDK 2.x `MCPServer`.
- Recommendation logic lives in `tools/recommend.py`; policy lives in
  `tools/ethics.py`, beside Om's `tools/crowd_themes.py`.
- Typed return values publish output schemas; Python client fields use snake_case.
- Thin wrappers delegate to plain functions. Data tools share a lazily cached
  `Recommender`; ethics does not construct it.
- `FLOW_DATA_DIR` works as Om documented. Optional `--data-dir` overrides it;
  the checkout default is independent of the client's current directory.
- `ToolError` failures replace the previous structured JSON error envelope.
  Snapshot failures are sanitized for clients and logged on stderr.
- Public server hooks reject extra fields and validate raw recommendation inputs
  before SDK coercion. This avoids silently dropping demographic criteria or
  accepting JSON strings in place of typed arguments.

The factory `create_server()` scopes the cache to each server for isolation.
The module still exports `server` for Om's discovery/call tests. New tool wrappers
belong inside the factory; see `docs/mcp_server.md` for the updated example.

## Verification

- **SDK 2.3.0:** all 64 tests pass, including all of Om's crowd-themes tests and
  real stdio client/server round trips.
- **SDK 2.2.0:** the same 64 tests pass, checking the dependency range's minimum
  version with both the client and subprocess server using that version.
- **Ruff lint and formatting:** pass.
- **Separate engine compatibility:** on Om's `73f38a1` engine branch, all 55
  existing engine tests plus both all-profile MCP tests pass: **57 passed**.
  The protocol tests exercise all five profiles, k=3/5 and mean/cosine scorers;
  results, warnings and Census metadata equal direct engine output.

Update (November 5): the Census engine branch has merged (PR #17), and `recommend`
now publishes its `weights` and `near` inputs. Test fixtures include the census and
geography files the default feature set needs.
The three-tool server does not implement `schema` or `area_stats`, and the ethics
endpoint remains a policy description rather than a natural-language refusal gate.
