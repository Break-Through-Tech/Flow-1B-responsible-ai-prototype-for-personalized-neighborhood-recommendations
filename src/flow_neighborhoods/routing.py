"""Layer 2 of EVAL_FRAMEWORK.md: does a chatbot prompt reach the right tool with the right args?

The product has two ways in: a chatbot (LLM over the MCP tools) and a filtered map where
the user sets budget, household, housing and priorities directly. Only the chatbot routes,
so only the chatbot is scored here. The map is the reference instead: a prompt's
``map_filters`` are the map settings for the same intent, and the chatbot's ``recommend``
call should rank the same request and show the same ZIPs (map parity). The chatbot can
also set the map's filters with the ``update_map`` action, which is scored the same way.

The harness takes any ``Router``:

- ``LLMRouter``: Gemini (the provider src/nlp already uses) over the MCP tool definitions.
  This is the Layer 2 scorecard result. Each run saves a log so it can be re-scored.
- ``LogRouter``: replays tool calls recorded from a real agent (or by hand), keyed by
  prompt_id, so a saved LLM run can be re-scored offline without calling the model.
- ``PlaceholderRouter``: keyword rules standing in for the LLM so the pipeline runs end
  to end. Its scores measure the rules, not an agent, and do not belong in the scorecard.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .contracts import Request, ValidationError
from .data import load_places, normalize_name
from .engine import Recommender
from .evaluate import provenance

MCP_TOOLS = ("recommend", "crowd_themes", "area_stats", "ethics", "schema")
# Chatbot action that sets the map's filters. It runs in the app, not on the MCP server,
# and the name is a placeholder until the frontend defines it.
MAP_ACTIONS = ("update_map",)
TOOLS = MCP_TOOLS + MAP_ACTIONS
MAP_K = (3, 5)  # The map shows the top 3-5 ZIPs; 3 when a fixture does not say.
TARGETS = {"tool_selection_accuracy": 0.90, "recommend_arg_accuracy": 0.85}
RECOMMEND_CHECKS = {
    "budget_max",
    "household",
    "housing_preference",
    "tags_contains",
    "tags_excludes",
    "k",
    "weights",
    "near_contains",
}


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


class Router(Protocol):
    kind: str

    def route(
        self, user_prompt: str, prompt_id: str | None = None, context: dict | None = None
    ) -> list[ToolCall] | None:
        """Tool calls in the order the agent would make them.

        [] means the agent called no tool. None means there is no record for this prompt
        (only a replayed log can say that); it is reported as not_logged, not scored.
        ``context`` is app state the user did not type: ``previous_recommend`` (the
        filters the map shows now) and ``selected_zip`` (the pin the user clicked).
        """


def app_state(context: dict | None) -> str | None:
    """How the app tells the chat model what is on screen, kept apart from user text."""
    if not context:
        return None
    lines = ["[App state, not typed by the user]"]
    if "previous_recommend" in context:
        filters = json.dumps(context["previous_recommend"], sort_keys=True)
        lines.append(f"The map currently shows recommend results for: {filters}")
    if "selected_zip" in context:
        lines.append(f"The user has selected the map pin for ZIP {context['selected_zip']}.")
    unknown = set(context) - {"previous_recommend", "selected_zip"}
    if unknown:
        raise ValueError(f"Unknown context keys {sorted(unknown)}.")
    return "\n".join(lines)


def expected_calls(item: dict) -> dict[str, dict]:
    """Normalize a fixture to {tool: expected_args}; {} means no tool should be called.

    One tool: "expected_tool": "recommend" (or null) with flat "expected_args".
    Several: "expected_tools": ["area_stats", "crowd_themes"] with "expected_args"
    keyed by tool name.
    """
    if "expected_tools" in item and "expected_tool" in item:
        raise ValueError(f"{item['prompt_id']}: use expected_tool or expected_tools, not both.")
    if "expected_tools" in item:
        args = item.get("expected_args", {})
        expected = {tool: dict(args.get(tool, {})) for tool in item["expected_tools"]}
    else:
        tool = item["expected_tool"]
        expected = {tool: dict(item.get("expected_args", {}))} if tool else {}
    if set(expected) - set(TOOLS):
        raise ValueError(f"{item['prompt_id']}: unknown expected tool in {sorted(expected)}.")
    # A key the scorer does not check would pass silently, so reject it up front.
    unchecked = set(expected.get("recommend", {})) - RECOMMEND_CHECKS
    if unchecked:
        raise ValueError(f"{item['prompt_id']}: recommend cannot check {sorted(unchecked)}.")
    return expected


def expected_map_filters(item: dict, expected: dict) -> dict | None:
    """The map settings that express the same intent, validated against the contract."""
    filters = item.get("map_filters")
    if filters is None:
        if "update_map" in expected:
            raise ValueError(f"{item['prompt_id']}: update_map needs map_filters.")
        return None
    if not {"recommend", "update_map"} & set(expected):
        raise ValueError(f"{item['prompt_id']}: map_filters need recommend or update_map.")
    k = filters.get("k", MAP_K[0])
    if canonical(filters) is None or type(k) is not int or not MAP_K[0] <= k <= MAP_K[1]:
        raise ValueError(f"{item['prompt_id']}: map_filters are not a valid map state.")
    return filters


def canonical(args: dict) -> tuple | None:
    """What changes the ranking, so equal values mean the same ZIPs in the same order.

    Compares the preference vector the engine ranks with, not the raw tags, so a weight of
    1 equals no weight and co_living sent or implied by co-living housing is the same
    request. k is left out (it only changes how many are shown), place order is ignored,
    and a request that needs clarification differs from one that does not. None means the
    args fail the recommend contract.
    """
    try:
        request = Request.parse({key: value for key, value in args.items() if value is not None})
    except ValidationError:
        return None
    return (
        request.budget_max,
        request.household,
        request.housing_preference,
        request.vector(),
        frozenset(normalize_name(name) for name in request.near),
        request.weight("near") if request.near else None,
        request.clarification(),
    )


def called_tools(calls: list[ToolCall], expected: dict) -> set[str]:
    """Tools that count toward routing.

    The MCP server tells agents to read ``ethics`` before ``recommend``, so an ethics
    call is a policy check, ignored unless the prompt is expected to route to ethics.
    A recommend call already refreshes the map, so an extra ``update_map`` next to an
    expected recommend is ignored too. It still counts when expected (and its args are
    checked), and it is a miss on prompts where recommend is not expected.
    """
    names = {call.name for call in calls}
    if "ethics" not in expected:
        names.discard("ethics")
    if "recommend" in expected and "update_map" not in expected:
        names.discard("update_map")
    return names


# --- Routers ----------------------------------------------------------------------------

TAG_PATTERNS = {
    "transit": r"transit|subway|metro|train|bus\b|commute",
    "walkable": r"walk",
    "social": r"social|nightlife|restaurants?|bars?\b",
    "quiet": r"quiet|calm|peaceful",
    "pet_friendly": r"\bpets?\b|pet[- ]friendly|\bdogs?\b|\bcats?\b",
}


class PlaceholderRouter:
    """Deterministic keyword rules. A stand-in for the LLM, not a candidate for it."""

    kind = "placeholder-keyword-v0"

    def __init__(self, data_dir: str | Path = "data"):
        _, self.aliases, _ = load_places(Path(data_dir))

    def zip_for(self, text: str) -> str | None:
        found = re.search(r"\b\d{5}\b", text)
        if found:
            return found.group()
        lowered = normalize_name(text)
        # Longest alias first so "little havana" beats "havana".
        for key in sorted(self.aliases, key=len, reverse=True):
            if re.search(rf"\b{re.escape(key)}\b", lowered):
                entry = self.aliases[key]
                zips = entry["zips"] or entry["secondary_zips"]
                return zips[0] if zips else None
        return None

    def recommend_args(self, text: str) -> dict | None:
        text = text.lower()
        budget = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\b", text)
        if not budget:
            return None  # A real agent would ask for a budget instead of guessing one.
        amount = float(budget.group(1).replace(",", "")) * (1000 if budget.group(2) else 1)
        co_living = bool(re.search(r"co-?\s?living", text))
        co_leaser = re.search(r"co-?\s?leaser|partner|spouse|couple", text)
        tags = [tag for tag, pattern in TAG_PATTERNS.items() if re.search(pattern, text)]
        if co_living:
            tags.append("co_living")
        return {
            "budget_max": amount,
            "household": "with_co_leaser" if co_leaser else "alone",
            "housing_preference": "co_living" if co_living else "own_apartment",
            "tags": tags,
        }

    def route(
        self, user_prompt: str, prompt_id: str | None = None, context: dict | None = None
    ) -> list[ToolCall]:
        text = user_prompt.lower()
        if re.search(r"ethic|limitation|responsible|fair housing|bias", text):
            return [ToolCall("ethics")]
        if re.search(r"column|schema|dataset|data dictionary|fields", text):
            return [ToolCall("schema")]
        if re.search(r"people say|reviews?|residents say|vibe|themes?", text):
            zip_code = self.zip_for(user_prompt)
            return [ToolCall("crowd_themes", {"zip_code": zip_code})] if zip_code else []
        if re.search(r"stats|statistics|census|median income|population", text):
            return [ToolCall("area_stats", {"zip_code": self.zip_for(user_prompt) or ""})]
        if re.search(r"recommend|suggest|where should|areas?|neighborhoods?|\$\d", text):
            args = self.recommend_args(user_prompt)
            if not args:
                return []
            calls = [ToolCall("recommend", args)]
            if re.search(r"\bmap\b", text):
                top = re.search(r"top (\d)", text)
                calls.append(
                    ToolCall("update_map", {**args, **({"k": int(top[1])} if top else {})})
                )
            return calls
        return []


class LogRouter:
    """Replays recorded calls: {"R1": [{"name": "recommend", "args": {...}}, ...], ...}."""

    def __init__(self, log: dict[str, list[dict]], kind: str = "log"):
        self.kind = kind
        self.metadata: dict | None = None
        self.log = {
            pid: [ToolCall(c["name"], dict(c.get("args") or {})) for c in calls]
            for pid, calls in log.items()
        }

    @classmethod
    def from_file(cls, path: Path) -> "LogRouter":
        """A bare {prompt_id: calls} map, or an LLMRouter log with metadata and calls."""
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data.get("calls"), dict) and "metadata" in data:
            router = cls(data["calls"], kind=f"log:{path.name}:{data['metadata']['router']}")
            router.metadata = data["metadata"]
            return router
        return cls(data, kind=f"log:{path.name}")

    def route(
        self, user_prompt: str, prompt_id: str | None = None, context: dict | None = None
    ) -> list[ToolCall] | None:
        return list(self.log[prompt_id]) if prompt_id in self.log else None


ROUTER_MODEL = os.environ.get("ROUTER_LLM_MODEL", "gemini-3.5-flash-lite")
MAX_TURNS = 6  # model turns per prompt; ethics first, then the real call, then an answer
APP_PROMPT = """You are the chat assistant in a Miami-Dade neighborhood finder for people \
relocating. Answer only with the tools below. The app also has a map that the user can \
filter by budget, household, housing type and priorities. When the user asks to see or \
change results on the map, call update_map with the same arguments you ranked with. If a \
required value is missing (for recommend, the monthly budget), ask for it instead of \
guessing."""


def api_key() -> str | None:
    """GEMINI_API_KEY from the environment or the repo's .env, as src/nlp does."""
    key = os.environ.get("GEMINI_API_KEY")
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    return key if key and not key.startswith("your_") else None


def integral(value):
    """JSON numbers can come back as 5.0; the contract wants k and weights as ints."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: integral(item) for key, item in value.items()}
    if isinstance(value, list):
        return [integral(item) for item in value]
    return value


class LLMRouter:
    """Gemini over the real MCP tool definitions, scored on the tool calls it makes.

    Each prompt is one fresh conversation at temperature 0. The tools are read-only and
    local, so calls are executed through the MCP server (with its own argument validation)
    and the results returned to the model. That matters because the server tells agents to
    read ``ethics`` before ``recommend``; a single turn would stop there. ``update_map``
    runs in the app, so it is acknowledged, not executed. The loop ends when the model
    answers in text or after ``MAX_TURNS``.

    ``generate`` is injectable: any callable (contents, config) -> Content works, so tests
    run offline with no API key. ``transcripts`` keeps every turn for the saved log.
    """

    def __init__(
        self, model: str = ROUTER_MODEL, data_dir: str | Path | None = None, generate=None
    ):
        from google.genai import types

        from .mcp_server import create_server

        self.types = types
        self.model = model
        self.kind = f"llm:gemini:{model}"
        self.server = create_server(data_dir)
        tools = asyncio.run(self.server.list_tools())
        declarations = [
            {"name": t.name, "description": t.description, "parameters": t.input_schema}
            for t in tools
        ]
        recommend = next(d for d in declarations if d["name"] == "recommend")
        update_map = json.loads(json.dumps(recommend["parameters"]))
        update_map["properties"]["k"].update(minimum=MAP_K[0], maximum=MAP_K[1])
        declarations.append(
            {
                "name": "update_map",
                "description": "Set the app's map filters so the map shows the top k ZIPs "
                f"({MAP_K[0]}-{MAP_K[1]}) for these preferences. Takes the same arguments "
                "as recommend. Runs in the app; returns nothing to quote.",
                "parameters": update_map,
            }
        )
        self.system_prompt = f"{APP_PROMPT}\n\n{self.server.instructions}"
        self.declarations = declarations
        self.config = types.GenerateContentConfig(
            temperature=0,
            system_instruction=self.system_prompt,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=d["name"],
                            description=d["description"],
                            parameters_json_schema=d["parameters"],
                        )
                        for d in declarations
                    ]
                )
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        if generate is None:
            key = api_key()
            if not key:
                raise RuntimeError(
                    "GEMINI_API_KEY is not set (env var or .env). Use --router log to "
                    "re-score a saved run offline."
                )
            from google import genai

            client = genai.Client(api_key=key)

            def generate(contents, config):
                response = client.models.generate_content(
                    model=model, contents=contents, config=config
                )
                return response.candidates[0].content

        self.generate = generate
        self.transcripts: dict[str, list[dict]] = {}
        self.inputs: dict[str, dict] = {}  # what the model was sent, for Layer 3

    def fingerprint(self) -> dict:
        """Hashes of what the model saw, so two runs can be compared fairly."""

        def digest(value) -> str:
            text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
            return hashlib.sha256(text.encode()).hexdigest()

        return {
            "provider": "gemini",
            "model": self.model,
            "temperature": 0,
            "max_turns": MAX_TURNS,
            "system_prompt_sha256": digest(self.system_prompt),
            "tools_sha256": digest(self.declarations),
        }

    def run_tool(self, call: ToolCall) -> dict:
        if call.name == "update_map":
            return {"status": "ok", "note": "Map filters applied in the app."}
        from mcp.server.mcpserver.exceptions import ToolError

        try:
            result = asyncio.run(self.server.call_tool(call.name, call.args))
        except ToolError as error:  # bad args and unknown tools go back to the model
            return {"error": str(error)}
        if getattr(result, "structured_content", None):
            return result.structured_content
        return {"text": "\n".join(getattr(c, "text", "") for c in result.content)}

    def route(
        self, user_prompt: str, prompt_id: str | None = None, context: dict | None = None
    ) -> list[ToolCall]:
        types = self.types
        state = app_state(context)
        parts = ([types.Part(text=state)] if state else []) + [types.Part(text=user_prompt)]
        contents = [types.Content(role="user", parts=parts)]
        calls, transcript = [], []
        for _ in range(MAX_TURNS):
            # The model's turn is sent back unchanged so thought signatures survive.
            reply = self.generate(contents, self.config)
            contents.append(reply)
            parts = reply.parts or []
            requested = [p.function_call for p in parts if p.function_call]
            text = "".join(p.text for p in parts if p.text and not p.thought)
            if not requested:
                transcript.append({"answer": text})
                break
            responses = []
            for function_call in requested:
                call = ToolCall(function_call.name, integral(dict(function_call.args or {})))
                calls.append(call)
                result = self.run_tool(call)
                # Results are kept so Layer 3 can check the answer against them.
                transcript.append({"call": {"name": call.name, "args": call.args}, "result": result})
                responses.append(types.Part.from_function_response(name=call.name, response=result))
            contents.append(types.Content(role="user", parts=responses))
        else:
            transcript.append({"stopped": f"no text answer after {MAX_TURNS} turns"})
        self.transcripts[prompt_id or user_prompt] = transcript
        self.inputs[prompt_id or user_prompt] = {"user_prompt": user_prompt, "context": context}
        return calls

    def log(self) -> dict:
        """Calls in LogRouter format, plus what produced them."""
        return {
            "metadata": {"router": self.kind, **self.fingerprint()},
            "calls": {
                pid: [t["call"] for t in turns if "call" in t]
                for pid, turns in self.transcripts.items()
            },
            "transcripts": self.transcripts,
            "inputs": self.inputs,
        }


# --- Scoring ----------------------------------------------------------------------------


def check_recommend_args(expected: dict, args: dict) -> dict[str, bool]:
    """Per-field checks against a fixture's expected_args.

    tags_contains: every expected tag was requested. tags_excludes: none of these were
    (a removed filter must not be resent). k: exact, 3 when not sent. weights: each
    expected weight matches, an unsent weight counting as 1. near_contains: each place
    was sent, compared by normalized name (a ZIP sent for a named place does not count).
    """
    checks = {}
    tags = args.get("tags")
    requested = {t.strip().lower() for t in tags if isinstance(t, str)} if tags else set()
    if "budget_max" in expected:
        budget = args.get("budget_max")
        checks["budget_max"] = (
            isinstance(budget, (int, float))
            and not isinstance(budget, bool)
            and float(budget) == float(expected["budget_max"])
        )
    for key in ("household", "housing_preference"):
        if key in expected:
            checks[key] = args.get(key) == expected[key]
    if "tags_contains" in expected:
        checks["tags_contains"] = set(expected["tags_contains"]) <= requested
    if "tags_excludes" in expected:
        checks["tags_excludes"] = not set(expected["tags_excludes"]) & requested
    if "k" in expected:
        checks["k"] = args.get("k", 3) == expected["k"]
    if "weights" in expected:
        sent = args.get("weights") or {}
        checks["weights"] = isinstance(sent, dict) and all(
            sent.get(tag, 1) == weight for tag, weight in expected["weights"].items()
        )
    if "near_contains" in expected:
        near = args.get("near") or []
        sent_places = {normalize_name(p) for p in near if isinstance(p, str)}
        checks["near_contains"] = {normalize_name(p) for p in expected["near_contains"]} <= (
            sent_places
        )
    try:
        Request.parse({key: value for key, value in args.items() if value is not None})
        checks["contract_valid"] = True
    except ValidationError:
        checks["contract_valid"] = False
    return checks


def check_other_args(expected: dict, call: ToolCall | None) -> dict[str, bool]:
    return {
        key: call is not None and call.args.get(key) == value for key, value in expected.items()
    }


def check_map_args(
    map_filters: dict, call: ToolCall | None, recommend: ToolCall | None
) -> dict[str, bool]:
    """update_map must set the map to the expected state, and to what the chat ranked."""
    if call is None:
        return {}  # Never called: counts as wrong arguments, like recommend.
    sent = canonical(call.args)
    k = call.args.get("k", MAP_K[0])
    checks = {
        "contract_valid": sent is not None,
        "k_in_map_range": type(k) is int and MAP_K[0] <= k <= MAP_K[1],
        "matches_map_filters": sent is not None and sent == canonical(map_filters),
    }
    if "k" in map_filters:
        checks["k"] = k == map_filters["k"]
    if recommend is not None:
        checks["agrees_with_recommend"] = sent is not None and sent == canonical(recommend.args)
    return checks


def shown(engine: Recommender, args: dict, k: int) -> tuple[str, list[str]]:
    payload = {key: value for key, value in args.items() if value is not None}
    try:
        response = engine.recommend({**payload, "k": k})
    except ValidationError as error:
        return f"invalid: {error}", []
    return response["status"], [result["zip"] for result in response["results"]]


def check_parity(
    map_filters: dict, call: ToolCall | None, engine: Recommender | None
) -> dict[str, bool]:
    """Would a chat user see what a map user with the same preferences sees?

    request_match: the chat's recommend call ranks the same request as the map.
    results_match: the same status and ZIPs, in order, over the shorter of the two lists
    (the chat may show 3 where the map shows 5). Needs the engine; skipped without one.
    """
    sent = canonical(call.args) if call else None
    checks = {"request_match": sent is not None and sent == canonical(map_filters)}
    if engine is not None:
        if sent is None:
            checks["results_match"] = False
        else:
            k = min(call.args.get("k", 3), map_filters.get("k", MAP_K[0]))
            checks["results_match"] = shown(engine, call.args, k) == shown(engine, map_filters, k)
    return checks


def score_prompt(
    item: dict, calls: list[ToolCall] | None, engine: Recommender | None = None
) -> dict:
    expected = expected_calls(item)
    map_filters = expected_map_filters(item, expected)
    row = {
        "prompt_id": item["prompt_id"],
        "category": item.get("category"),
        "expected_tools": sorted(expected),
        "logged": calls is not None,
        "calls": None,
        "called_tools": None,
        "missing_tools": None,
        "extra_tools": None,
        "unknown_tools": [],
        "tool_correct": None,
        "arg_checks": None,
        "recommend_args_correct": None,
        "other_args_correct": None,
        "map_update_args_correct": None,
        "map_parity": None,
    }
    if calls is None:
        return row
    called = called_tools(calls, expected)
    first = {}
    for call in calls:
        first.setdefault(call.name, call)
    arg_checks = {}
    for tool, args in expected.items():
        if tool == "recommend":
            # recommend never called: no checks, which counts as wrong arguments below.
            arg_checks[tool] = check_recommend_args(args, first[tool].args) if tool in first else {}
        elif tool == "update_map":
            arg_checks[tool] = check_map_args(map_filters, first.get(tool), first.get("recommend"))
        elif args:
            arg_checks[tool] = check_other_args(args, first.get(tool))
    special = ("recommend", "update_map")
    other = [
        ok for tool, checks in arg_checks.items() if tool not in special for ok in checks.values()
    ]

    def all_passed(tool: str) -> bool | None:
        if tool not in expected:
            return None
        return bool(arg_checks[tool]) and all(arg_checks[tool].values())

    row.update(
        calls=[{"name": c.name, "args": c.args} for c in calls],
        called_tools=sorted(called),
        missing_tools=sorted(set(expected) - called),
        extra_tools=sorted(called - set(expected)),
        unknown_tools=[c.name for c in calls if c.name not in TOOLS],
        tool_correct=called == set(expected),
        arg_checks=arg_checks,
        recommend_args_correct=all_passed("recommend"),
        other_args_correct=all(other) if other else None,
        map_update_args_correct=all_passed("update_map"),
        map_parity=check_parity(map_filters, first.get("recommend"), engine)
        if map_filters is not None and "recommend" in expected
        else None,
    )
    return row


def evaluate_routing(
    router: Router, prompts: list[dict], engine: Recommender | None = None
) -> dict:
    """Score every prompt. Pass the engine to also check that chat and map show the same ZIPs."""
    if not prompts:
        raise ValueError("Routing evaluation needs at least one prompt.")
    rows = [
        score_prompt(
            item, router.route(item["user_prompt"], item["prompt_id"], item.get("context")), engine
        )
        for item in prompts
    ]

    def rate(key: str, check: str | None = None) -> float | None:
        values = [row[key] for row in rows if row[key] is not None]
        if check:
            values = [value[check] for value in values if check in value]
        return sum(values) / len(values) if values else None

    summary = {
        "prompts": len(rows),
        "scored": sum(row["logged"] for row in rows),
        "not_logged": [row["prompt_id"] for row in rows if not row["logged"]],
        "tool_selection_accuracy": rate("tool_correct"),
        "recommend_arg_accuracy": rate("recommend_args_correct"),
        "recommend_prompts": sum(row["recommend_args_correct"] is not None for row in rows),
        "other_arg_accuracy": rate("other_args_correct"),
        "map_update_arg_accuracy": rate("map_update_args_correct"),
        "map_parity_rate": rate("map_parity", "request_match"),
        "map_results_parity_rate": rate("map_parity", "results_match"),
        "parity_prompts": sum(row["map_parity"] is not None for row in rows),
        "misses": [row["prompt_id"] for row in rows if row["tool_correct"] is False],
        "arg_misses": [
            row["prompt_id"]
            for row in rows
            if False
            in (
                row["recommend_args_correct"],
                row["other_args_correct"],
                row["map_update_args_correct"],
            )
        ],
        "parity_misses": [
            row["prompt_id"]
            for row in rows
            if row["map_parity"] and not all(row["map_parity"].values())
        ],
        "unknown_tools": {
            row["prompt_id"]: row["unknown_tools"] for row in rows if row["unknown_tools"]
        },
    }
    summary["meets_target"] = {
        metric: summary[metric] is not None and summary[metric] >= target
        for metric, target in TARGETS.items()
    }
    # Where the misses are: refusals and map edits fail for different reasons.
    by_category = {}
    for row in rows:
        if row["category"] and row["logged"]:
            group = by_category.setdefault(row["category"], {"prompts": 0, "tool_correct": 0})
            group["prompts"] += 1
            group["tool_correct"] += row["tool_correct"]
    summary["by_category"] = {
        name: {**g, "tool_selection_accuracy": g["tool_correct"] / g["prompts"]}
        for name, g in sorted(by_category.items())
    }
    return {"summary": summary, "prompts": rows}


def main():
    parser = argparse.ArgumentParser(description="Layer 2: MCP tool routing evaluation")
    parser.add_argument("--router", choices=["placeholder", "log", "llm"], default="placeholder")
    parser.add_argument("--log", type=Path, help="recorded calls for --router log")
    parser.add_argument(
        "--prompts",
        type=Path,
        nargs="+",
        default=[
            Path("eval/agent_routing_prompts.json"),
            Path("eval/agent_routing_prompts_map.json"),
        ],
        help="one or more fixture files; prompt_ids must be unique across them",
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", type=Path, help="default: outputs/routing_<router>.json")
    parser.add_argument("--model", default=ROUTER_MODEL, help="Gemini model id for --router llm")
    parser.add_argument(
        "--save-log",
        type=Path,
        help="where --router llm saves its calls (default: eval/logs/routing_<model>.json); "
        "replay with --router log --log FILE",
    )
    args = parser.parse_args()
    if args.router == "log" and not args.log:
        parser.error("--router log needs --log FILE")
    try:
        router = {
            "placeholder": lambda: PlaceholderRouter(args.data_dir),
            "log": lambda: LogRouter.from_file(args.log),
            "llm": lambda: LLMRouter(args.model, args.data_dir),
        }[args.router]()
    except RuntimeError as error:
        parser.error(str(error))
    engine = Recommender(args.data_dir)
    prompts = [p for path in args.prompts for p in json.loads(path.read_text(encoding="utf-8"))]
    ids = [p["prompt_id"] for p in prompts]
    if len(ids) != len(set(ids)):
        parser.error("prompt_id values repeat across --prompts files.")
    prompts_sha256 = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in args.prompts
    }
    report = evaluate_routing(router, prompts, engine)
    llm = (
        router.fingerprint() if isinstance(router, LLMRouter) else getattr(router, "metadata", None)
    )
    if isinstance(router, LLMRouter):
        log_path = args.save_log or Path(f"eval/logs/routing_{args.model}.json")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = router.log()
        log["metadata"]["prompts_sha256"] = prompts_sha256
        log_path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
        print(f"Saved calls to {log_path}")
    report["metadata"] = {
        **provenance(),
        "router": router.kind,
        "llm": llm,
        "engine": {"model_version": engine.model_version, "feature_set": engine.feature_set},
        "prompts_sha256": prompts_sha256,
        "selection_rule": "Correct when the set of tools called equals the expected set. "
        "ethics is ignored unless expected (agents may read policy first), so "
        "expected_tool null passes only if nothing but ethics was called. update_map is "
        "ignored next to an expected recommend (recommend already refreshes the map) unless "
        "update_map is itself expected. Unlogged prompts "
        "are listed in not_logged and excluded from every rate.",
        "arg_rule": "recommend: exact budget_max, household and housing_preference; expected "
        "tags a subset of those sent; tags_excludes not sent; k exact (default 3); expected "
        "weights equal (unsent = 1); near_contains sent by name; and the args must pass the recommend input contract "
        "(Request.parse), which is stricter than EVAL_FRAMEWORK.md. recommend not called "
        "counts as wrong arguments. Other tools: exact match on expected keys, first call.",
        "parity_rule": "Prompts with map_filters (the map settings for the same intent). "
        "request_match: the chat's recommend args rank the same request as the map (same "
        "budget, household, housing, tags, weights and places; k ignored). results_match: "
        "the same status and ZIPs, in order, over the shorter list. update_map must match "
        "map_filters, keep k in 3-5, and agree with the chat's recommend call.",
        "limitations": f"{len(prompts)} prompts; no held-out generalization claim."
        + (
            " Placeholder results measure keyword rules, not an LLM agent, and must not be "
            "reported as Layer 2 scorecard values."
            if isinstance(router, PlaceholderRouter)
            else ""
        ),
    }
    output = args.output or Path(f"outputs/routing_{args.router}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
