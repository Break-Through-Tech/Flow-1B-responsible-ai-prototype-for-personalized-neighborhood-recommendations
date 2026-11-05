# recommend and ethics MCP tools

The shared server follows Om's `om-mcp-crowd-themes` branch at `deeeb53`.
It exposes `crowd_themes`, `recommend` and `ethics` over stdio, with the existing
engine left unchanged. No LLM, network service,
API key, live scrape, or listing feed is required.

## Install and run

From the repository root, using Python 3.11+:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[mcp]" --group dev
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m flow_neighborhoods.mcp_server --data-dir ./data
```

If pip does not support `--group`, install `-e ".[mcp]"` and `pytest ruff` separately.
The optional `mcp` extra installs SDK 2.x (`mcp>=2.2,<3`), matching Om's server.
SDK 1.x is no longer supported by this implementation. The offline engine still
imports and runs without installing the extra. Tool logic lives in
`tools/recommend.py` and `tools/ethics.py`, alongside Om's `tools/crowd_themes.py`;
the server registers thin typed wrappers with generated output schemas.

The equivalent installed entry point is `flow-neighborhoods-mcp`. The server waits
for an MCP client on stdin/stdout; do not enter ordinary chat messages into it.
Only MCP protocol messages go to stdout. Diagnostics go to stderr.

When running an editable checkout, the default data path is the checkout's `data/`
directory, independent of the client's working directory. Set an explicit absolute
`--data-dir` for a wheel installation, a moved dataset, or a client configuration.
The server also honors Om's `FLOW_DATA_DIR` environment variable. Explicit
`--data-dir` takes precedence over that variable; otherwise the checkout default
is used. Relative paths resolve against the launch directory.
`--scorer mean` is the default; `--scorer cosine` selects the retained baseline.

## Connect an MCP client

Replace both example paths with absolute paths on your machine. Point `command`
at the same virtual environment where the package and MCP extra were installed.

```json
{
  "mcpServers": {
    "flow-neighborhoods": {
      "command": "C:/path/to/project/.venv/Scripts/python.exe",
      "args": [
        "-m", "flow_neighborhoods.mcp_server",
        "--data-dir", "C:/path/to/project/data"
      ]
    }
  }
}
```

Discover tools using `tools/list`, then call them with `tools/call`. Both tool
definitions publish input/output JSON schemas and read-only annotations. There is
no HTTP listener or public deployment in this change.

## recommend

Example arguments:

```json
{
  "budget_max": 2500,
  "household": "with_co_leaser",
  "housing_preference": "own_apartment",
  "tags": ["transit", "walkable"],
  "k": 3
}
```

`budget_max`, `household`, `housing_preference`, and `tags` are required. `k` is
optional and defaults to 3, with a range of 1-5. Budget is positive, finite, total
household monthly USD; it is never automatically divided or multiplied for
co-leasers. Housing and household values are exactly those in the example or
`co_living` and `alone`, respectively. Supported tags are `transit`, `social`,
`quiet`, `pet_friendly`, `walkable`, and `co_living`. The engine normalizes tag
case/whitespace and deduplicates tags.

Unknown keys are rejected, including demographic filters, tenant scores, screening
criteria and unsupported priority/location fields. Numeric strings and booleans
are not coerced into budgets or k. Engine validation remains authoritative after
JSON-schema validation, including rejecting integral floats for k and nonfinite
budgets. The transport schema requires an object; malformed protocol messages are
handled by the SDK rather than treated as ordinary tool calls.

Successful `structuredContent` is the engine's result unchanged. It includes
`schema_version`, `model_version`, data hashes, `status`, ranked `results`, counts,
applied filters, warnings and feature contributions. MCP `content[0].text` contains
the same JSON for clients that read text content only. No score is a probability
of satisfaction, and snapshot rents do not establish available units.

- `ok`: rankings, including shorter-than-k lists when necessary.
- `no_matches`: a valid request with an empty result list; the budget stays fixed.
- `needs_clarification`: empty lifestyle tags or conflicting/undefined housing
  combinations. Ask the user instead of inventing or silently changing preferences.

These three are successful tool calls (`isError=false`). Missing/nonpositive rent
never qualifies. Original demo snippets, evidence IDs, source labels and warnings
are preserved; this implementation does not adopt PR #15's NLP index or claim
authentic review coverage.

The snapshot is loaded lazily on the first valid recommendation or crowd-themes
request, shared by those tools, and retained for
the server process. Restart after changing files to load a new version. Failed
loads are not cached, so correcting the data can recover without disabling ethics.

## ethics

Input: `{}` or omitted arguments. Extra fields are rejected. Output includes:

- A policy version, allowed exploration uses and prohibited uses.
- Explicit rules against tenant screening, demographic steering, hidden screening
  criteria, invented/live listings and presentation of synthetic cards as real.
- Limitations of area rent estimates, feature proxies and demo text, plus the
  required synthetic-card disclaimer.
- Agent requirements for grounded narration, honest empty states and refusals.
- Explicit enforcement metadata: `natural_language_gate_implemented=false`.

The policy is returned even if CSV files are missing or corrupt. Each call creates
a fresh JSON object rather than returning mutable shared policy state.

### Policy description versus enforcement

Calling `ethics` does not run a classifier or prove that an agent refuses harmful
prompts. The `recommend` schema blocks unsupported structured criteria; it cannot
detect hidden intent if an agent converts a prohibited user message into an
otherwise allowed budget/tag object. The agent must inspect the original user
request and gate it before calling `recommend`.

The starter prohibited fixtures specify no `recommend` call for X1, X2, X4 and X5.
X3 permits refusal or clarification that only synthetic/snapshot information is
available. This change documents those requirements but does not claim a measured
100% agent refusal rate. Full natural-language routing, injection resistance and
claim-level grounding remain agent integration work.

## Tool errors

Execution failures follow Om's SDK 2.x `ToolError` convention. On the wire,
`isError=true` and text content contains a readable error; there is no structured
success payload on an error. In the Python 2.x client these attributes are
`is_error` and `structured_content` (tool metadata uses `input_schema` and
`output_schema`). The previous SDK 1.x JSON error envelope has been retired.

Validation errors include `invalid_arguments`; unavailable snapshot errors include
`data_unavailable`; unknown tool names include `unknown_tool`. Unexpected failures
are handled by the SDK without exposing the original exception. Snapshot errors
expose neither filesystem paths nor raw source records to the caller; diagnostics
stay on stderr. Error text must not be narrated as a recommendation.

The shared server subclasses public `MCPServer.list_tools` / `call_tool` hooks to
publish `additionalProperties=false` and validate raw arguments before the SDK's
permissive argument models can drop unknown fields or parse JSON embedded inside
strings. Engine validation runs before loading data for recommend. This preserves
strict rejection of demographic fields and type coercion while keeping Om's
registration pattern. `schema` and `area_stats` remain unimplemented.

## Integration with pending branch work

At implementation time, main is `fdd2c9a`. Om's pushed recommender branch
(`73f38a1`) adds Census features, priorities (`weights`) and neighborhood proximity
(`near`); Joana's branch (`405e12c`) restructures data and adds updated sources.
The newer MCP-only branch `om-mcp-crowd-themes` (`deeeb53`) is integrated here.
The separate `Om` engine branch and Joana's data branch are not merged. The adapter uses the existing
`Recommender(...).recommend(payload)` interface, so new internal scoring can be
consumed after its merge without duplicating ranking logic. Expanding the public
tool schema for `weights` and `near` is a separate, explicit contract change.
If data files move, configure a directory containing the engine's three required
CSV names, or update the engine's loader in a coordinated change. Do not restore
eligibility with imputed rent from a new table without reviewing its provenance.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
```

`tests/test_mcp_tools.py` launches real stdio server subprocesses and initializes
an official SDK client. It checks tool discovery, all five repository profiles at
k=3/5 under both scorers, exact engine parity, a hand-checkable budget boundary,
short/empty lists, clarification, original demo evidence, rejection of demographic
and unsupported fields/type coercion, recovery after errors, data failures, and
operation from a different working directory. Existing engine tests remain part
of the same suite. No Gemini API or real listing service is used.

The original SDK 1.x implementation passed 50 tests on 2026-11-03 but was not
compatible with Om's subsequently discovered SDK 2.x MCP server. It has been
replaced with the shared SDK 2.x implementation. Verification now includes Om's
crowd-themes tests, all three tools registered on one server, environment-variable
and CLI data-directory selection, shared snapshot caching, and the original
recommendation checks. See `docs/om_mcp_compatibility.md` for current results.
