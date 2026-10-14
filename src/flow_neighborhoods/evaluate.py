"""Reproducible Layer 1 fixture metrics; no training or weight tuning."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from .contracts import Request
from .engine import FEATURE_SETS, SCORERS, Recommender


def evaluate(engine: Recommender, profiles: list[dict]) -> dict:
    if not profiles:
        raise ValueError("Evaluation needs at least one profile.")
    rows = []
    for profile in profiles:
        relevant = set(profile["expected_relevant_zips"])
        payload = {
            key: profile[key] for key in ("budget_max", "household", "housing_preference", "tags")
        }
        # Rank over every eligible area, not just the top k, so improvements
        # below the cut-off are still visible.
        ranking = [item["zip"] for item in engine.rank(Request.parse(payload))[0]]
        relevant_ranks = {z: ranking.index(z) + 1 if z in ranking else None for z in relevant}
        found = [rank for rank in relevant_ranks.values() if rank]
        for k in (3, 5):
            response = engine.recommend(dict(payload, k=k))
            results = response["results"]
            covered = sum(
                any(e["theme"] in profile["tags"] for e in item["themes"]) for item in results
            )
            rows.append(
                {
                    "profile_id": profile["profile_id"],
                    "k": k,
                    "precision": sum(item["zip"] in relevant for item in results) / k,
                    "label_ceiling": min(k, len(relevant)) / k,
                    "reciprocal_rank": 1 / min(found) if found else 0.0,
                    "relevant_ranks": dict(sorted(relevant_ranks.items())),
                    "mean_score": mean(item["score"] for item in results) if results else None,
                    "budget_pass": all(
                        0 < item["median_rent_usd"] <= profile["budget_max"] for item in results
                    )
                    if results
                    else None,
                    "demo_theme_coverage": covered / len(results) if results else None,
                    "response": response,
                }
            )
    summary = {}
    for k in (3, 5):
        selected = [row for row in rows if row["k"] == k]
        nonempty = [row for row in selected if row["response"]["returned_count"]]
        summary[str(k)] = {
            "precision": mean(row["precision"] for row in selected),
            "mrr": mean(row["reciprocal_rank"] for row in selected),
            "mean_score": mean(row["mean_score"] for row in nonempty) if nonempty else None,
            "budget_pass_rate_nonempty": mean(row["budget_pass"] for row in nonempty)
            if nonempty
            else None,
            "demo_theme_coverage": mean(row["demo_theme_coverage"] for row in nonempty)
            if nonempty
            else None,
            "empty_profiles": len(selected) - len(nonempty),
        }
    return {"summary": summary, "profiles": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--profiles", type=Path, default=Path("eval/recommendation_profiles.json"))
    parser.add_argument("--scorer", choices=list(SCORERS), default="mean")
    parser.add_argument("--features", choices=FEATURE_SETS, default="provided")
    parser.add_argument(
        "--output", type=Path, help="default: outputs/recommender_<scorer>_<features>.json"
    )
    args = parser.parse_args()
    args.output = args.output or Path(f"outputs/recommender_{args.scorer}_{args.features}.json")
    engine = Recommender(args.data_dir, scorer=args.scorer, feature_set=args.features)
    report = evaluate(engine, json.loads(args.profiles.read_text(encoding="utf-8")))
    code_paths = sorted(Path(__file__).parent.glob("*.py"))
    report["metadata"] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": engine.model_version,
        "feature_set": engine.feature_set,
        "data_sha256": engine.data_version,
        "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths},
        "profiles_sha256": hashlib.sha256(args.profiles.read_bytes()).hexdigest(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "git_status": subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.splitlines(),
        "aggregation": "Macro average per profile, separately for k=3 and k=5.",
        "limitations": "Five starter fixtures; demo evidence only; no held-out generalization claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
