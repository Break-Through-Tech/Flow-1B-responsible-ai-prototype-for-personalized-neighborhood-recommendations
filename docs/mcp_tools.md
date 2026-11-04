# recommend and ethics MCP tools

Implemented against main at `fdd2c9a`, with the existing engine left unchanged.
The server exposes exactly two read-only tools over stdio. No LLM, network service,
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
The optional `mcp` extra installs the tested SDK version, `mcp==1.30.0`; this is the
SDK v1 API. Do not remove the pin and silently switch to SDK v2. The offline engine
still imports and runs without installing the extra.

The equivalent installed entry point is `flow-neighborhoods-mcp`. The server waits
for an MCP client on stdin/stdout; do not enter ordinary chat messages into it.
Only MCP protocol messages go to stdout. Diagnostics go to stderr.

When running an editable checkout, the default data path is the checkout's `data/`
directory, independent of the client's working directory. Set an explicit absolute
`--data-dir` for a wheel installation, a moved dataset, or a client configuration.
Relative paths supplied on the command line resolve against the launch directory.
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

The snapshot is loaded lazily on the first valid recommendation and retained for
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

Execution errors return `isError=true` with both text and structured JSON:

```json
{
  "schema_version": "1",
  "status": "error",
  "error": {
    "code": "invalid_arguments",
    "message": "Arguments must match the tool's inputSchema; unsupported fields are rejected."
  }
}
```

Codes: `invalid_arguments` for schema/engine input errors; `data_unavailable` for
missing, unreadable or invalid snapshot files; `unknown_tool` for names not served;
`internal_error` for unexpected execution failures. Data errors expose neither
filesystem paths nor raw source records to the caller. Full diagnostics stay on
stderr. Error payloads must not be narrated as recommendations. Existing `schema`,
`area_stats`, and `crowd_themes` names are not registered as placeholder tools.

## Integration with pending branch work

At implementation time, main is `fdd2c9a`. Om's pushed recommender branch
(`73f38a1`) adds Census features, priorities (`weights`) and neighborhood proximity
(`near`); Joana's branch (`405e12c`) restructures data and adds updated sources.
Neither branch is silently merged here. The adapter uses the existing
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

Verified on 2026-11-03: all 50 tests pass on the main-based implementation, with
Ruff lint and formatting checks passing. The two all-profile protocol tests also
pass against a separate checkout of Om's `73f38a1` branch (mean and cosine), using
that branch's data and default feature selection. That confirms the shared engine
interface; it does not validate every new branch option or integrate its changes.
