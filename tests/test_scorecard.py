import hashlib
import json
from argparse import Namespace
from pathlib import Path

import pytest

from flow_neighborhoods import scorecard

ROOT = Path(__file__).resolve().parents[1]


def args(tmp_path, routing=None, responses=None):
    return Namespace(
        data_dir=ROOT / "data",
        profiles=ROOT / "eval/recommendation_profiles.json",
        neighborhoods=ROOT / "eval/neighborhood_zips.json",
        routing=routing or tmp_path / "missing_routing.json",
        responses=responses or tmp_path / "missing_responses.json",
    )


def row(card, metric):
    return next(r for r in card["rows"] if r[1] == metric)


def write(path, report):
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_layer1_rows_are_computed_and_llm_rows_pending(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    card = scorecard.build(args(tmp_path))
    assert row(card, "Precision@3")[3] != "pending"
    assert row(card, "Budget filter pass rate")[5] == "✅"
    assert row(card, "Theme coverage @3")[0] == "NLP"
    for metric in ("Tool selection accuracy", "Tool grounding rate", "Refusal rate (prohibited)"):
        assert row(card, metric)[3] == "pending" and "no Layer" in row(card, metric)[6]


def test_placeholder_report_is_not_a_scorecard_value(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    report = {
        "summary": {"tool_selection_accuracy": 1.0, "recommend_arg_accuracy": 1.0},
        "metadata": {"router": "placeholder-keyword-v0"},
    }
    card = scorecard.build(args(tmp_path, routing=write(tmp_path / "r.json", report)))
    assert row(card, "Tool selection accuracy")[3] == "pending"
    assert "not an LLM run" in row(card, "Tool selection accuracy")[6]


def test_llm_reports_fill_rows_and_judge_targets(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    prompts = "eval/agent_routing_prompts.json"
    digest = hashlib.sha256((ROOT / prompts).read_bytes()).hexdigest()
    routing = {
        "summary": {"tool_selection_accuracy": 0.95, "recommend_arg_accuracy": 0.80, "scored": 57},
        "metadata": {
            "router": "log:x.json:llm:gemini:m",
            "llm": {"model": "m"},
            "prompts_sha256": {prompts: digest},
        },
    }
    responses = {
        "summary": {
            "grounding_rate": 0.96,
            "refusal_rate": 0.9,
            "disclosure_rate": 1.0,
            "grounding_responses": 50,
            "refusal_prompts": 11,
            "disclosure_responses": 20,
        },
        "metadata": {"llm": {"router": "llm:gemini:m"}},
    }
    card = scorecard.build(
        args(tmp_path, write(tmp_path / "r.json", routing), write(tmp_path / "s.json", responses))
    )
    assert row(card, "Tool selection accuracy")[3:6] == ["95%", "≥ 90%", "✅"]
    assert row(card, "recommend arg accuracy")[5] == "❌"
    assert row(card, "Refusal rate (prohibited)")[3:6] == ["90%", "100%", "❌"]
    assert row(card, "Disclosure rate")[5] == "✅"


def test_report_on_old_prompts_is_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    report = {
        "summary": {},
        "metadata": {
            "router": "llm:gemini:m",
            "prompts_sha256": {"eval/agent_routing_prompts.json": "0" * 64},
        },
    }
    card = scorecard.build(args(tmp_path, routing=write(tmp_path / "r.json", report)))
    assert "older agent_routing_prompts.json" in row(card, "Tool selection accuracy")[6]


def test_update_docs_replaces_only_the_block(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text(f"intro\n{scorecard.START}\nold\n{scorecard.END}\noutro\n", encoding="utf-8")
    scorecard.update_docs(doc, "| new |\n")
    assert doc.read_text() == f"intro\n{scorecard.START}\n| new |\n{scorecard.END}\noutro\n"
    doc.write_text("no markers", encoding="utf-8")
    with pytest.raises(SystemExit):
        scorecard.update_docs(doc, "x")


def test_framework_doc_has_the_scorecard_block():
    text = (ROOT / "EVAL_FRAMEWORK.md").read_text(encoding="utf-8")
    assert scorecard.START in text and scorecard.END in text


def test_replayed_log_from_older_prompts_is_stale(tmp_path, monkeypatch):
    """Replaying an old run on today's files must not look fresh."""
    monkeypatch.chdir(ROOT)
    prompts = "eval/agent_routing_prompts.json"
    digest = hashlib.sha256((ROOT / prompts).read_bytes()).hexdigest()
    report = {
        "summary": {},
        "metadata": {
            "router": "log:llm_m.json:llm:gemini:m",
            "prompts_sha256": {prompts: digest},
            "llm": {"model": "m", "prompts_sha256": {prompts: "0" * 64}},
        },
    }
    card = scorecard.build(args(tmp_path, routing=write(tmp_path / "r.json", report)))
    assert "older agent_routing_prompts.json" in row(card, "Tool selection accuracy")[6]


def test_one_saved_run_fills_layers_2_and_3(tmp_path, monkeypatch):
    """Fake-model run over every fixture -> one log -> both reports -> scorecard rows."""
    pytest.importorskip("google.genai")
    pytest.importorskip("mcp")
    from google.genai import types

    from flow_neighborhoods import routing

    monkeypatch.chdir(ROOT)
    answer = types.Content(role="model", parts=[types.Part(text="I can't help with that.")])
    router = routing.LLMRouter("fake", ROOT / "data", generate=lambda c, cfg: answer)
    prompts, hashes = routing.load_prompts(routing.ALL_PROMPTS)
    log = routing.run_llm(router, prompts, hashes, tmp_path / "llm_fake.json")
    run = Namespace(
        **vars(args(tmp_path, tmp_path / "routing.json", tmp_path / "responses.json")),
        run_llm=False,
        log=tmp_path / "llm_fake.json",
        model="fake",
    )
    scorecard.score_llm_run(run)
    card = scorecard.build(run)
    assert row(card, "Tool selection accuracy")[3] not in ("pending", "—")
    assert row(card, "Refusal rate (prohibited)")[3] == "100%"
    assert row(card, "Disclosure rate")[3:6] == ["—", "100%", "—"]  # nothing to judge
    routing_report = json.loads((tmp_path / "routing.json").read_text())
    assert routing_report["summary"]["scored"] == len(routing_report["prompts"]) == 57
    assert len(log["transcripts"]) == len(prompts)
