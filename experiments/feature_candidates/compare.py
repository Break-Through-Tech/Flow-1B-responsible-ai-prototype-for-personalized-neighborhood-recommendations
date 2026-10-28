"""Compare feature sets and the household budget rule on the 5 profiles (run from repo root)."""

import copy
import json
import sys

sys.path.insert(0, "src")
from flow_neighborhoods import Recommender  # noqa: E402
from flow_neighborhoods.evaluate import evaluate  # noqa: E402

profiles = json.load(open("eval/recommendation_profiles.json"))
total_budget = copy.deepcopy(profiles)  # old rule: budget is the household total
for p in total_budget:
    p["household"] = "alone"  # household never changed the score, only the budget basis

print(f"{'features':9} {'budget rule':18} {'P@3':>5} {'P@5':>5} {'MRR':>5}  per-profile P@3 / expected ranks")
for fs in ("provided", "census"):
    engine = Recommender("data", feature_set=fs)
    for label, ps in (("household total", total_budget), ("per-person share", profiles)):
        rep = evaluate(engine, ps)
        s = rep["summary"]
        rows = [r for r in rep["profiles"] if r["k"] == 3]
        detail = " ".join(
            f"{r['profile_id'][:2]}:{r['precision']:.2f}/{','.join(str(v) for v in r['relevant_ranks'].values())}"
            for r in rows
        )
        print(f"{fs:9} {label:18} {s['3']['precision']:5.2f} {s['5']['precision']:5.2f} {s['3']['mrr']:5.2f}  {detail}")

print("\nP5 (Brickell focus) with near=['Brickell'] and different priorities, census features:")
engine = Recommender("data", feature_set="census")
p5 = next(p for p in profiles if p["profile_id"].startswith("P5"))
base = {k: p5[k] for k in ("budget_max", "household", "housing_preference", "tags")}
for extra in ({}, {"near": ["Brickell"]}, {"near": ["Brickell"], "weights": {"near": 3}}):
    r = engine.recommend(dict(base, k=3, **extra))
    print(f"  {json.dumps(extra):45} ->", [(x["zip"], x["area_name"], x.get("distance_miles")) for x in r["results"]])

print("\nPriorities, census features, $1,800 alone, transit + quiet:")
for weights in ({}, {"transit": 3}, {"quiet": 3}):
    r = engine.recommend({"budget_max": 1800, "household": "alone", "housing_preference": "own_apartment",
                          "tags": ["transit", "quiet"], "weights": weights, "k": 3})
    print(f"  {json.dumps(weights):18} ->", [(x["zip"], x["area_name"], round(x["score"], 2)) for x in r["results"]])
