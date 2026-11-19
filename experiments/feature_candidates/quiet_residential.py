"""Advisor feedback: quiet = residential character; transportation noise becomes low_noise.

Run from the repo root:  python experiments/feature_candidates/quiet_residential.py
Scores with the advisor's neighborhood -> ZIP mapping (eval/neighborhood_zips.json).
Candidates use housing form (place), not resident demographics; fixed before running.
Rule as before: adopt if MRR rises >= 0.02 and no profile's reciprocal rank falls.
"""

import csv
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, "src")
from flow_neighborhoods import Recommender  # noqa: E402
from flow_neighborhoods.data import percentiles  # noqa: E402
from flow_neighborhoods.evaluate import evaluate  # noqa: E402

HERE = Path(__file__).parent
profiles = json.load(open("eval/recommendation_profiles.json"))
neighborhoods = json.load(open("eval/neighborhood_zips.json"))["neighborhoods"]
base = Recommender("data")
ZIPS = [a["zip"] for a in base.areas]
units = {}
with open(HERE / "census/b25024.dat") as f:
    for r in csv.DictReader(f, delimiter="|"):
        units[r["GEO_ID"][-5:]] = {k: float(v) for k, v in r.items() if "_E" in k}


def share(z, *cols, total="B25024_E001", invert=False):
    u = units.get(z)
    if not u or u[total] <= 0:
        return None
    value = sum(u[c] for c in cols) / u[total]
    return 1 - value if invert else value


pct = lambda d: percentiles({z: d.get(z) for z in ZIPS})  # noqa: E731
QUIET = {
    "current: low transportation noise": {a["zip"]: a["quiet"] for a in base.areas},
    "single-unit homes share (detached+attached)": pct(
        {z: share(z, "B25024_E002", "B25024_E003") for z in ZIPS}
    ),
    "low-rise share (not 10+ unit buildings)": pct(
        {z: share(z, "B25024_E007", "B25024_E008", "B25024_E009", invert=True) for z in ZIPS}
    ),
}
QUIET["single-unit + low-rise"] = {
    z: None if None in (QUIET["single-unit homes share (detached+attached)"][z], QUIET["low-rise share (not 10+ unit buildings)"][z])
    else (QUIET["single-unit homes share (detached+attached)"][z] + QUIET["low-rise share (not 10+ unit buildings)"][z]) / 2
    for z in ZIPS
}


def run(option):
    engine = Recommender("data")
    for a in engine.areas:
        a["quiet"] = QUIET[option][a["zip"]]
    rep = evaluate(engine, profiles, neighborhoods)
    rr = {r["profile_id"][:2]: r["reciprocal_rank"] for r in rep["profiles"] if r["k"] == 3}
    p4 = next(r for r in rep["profiles"] if r["k"] == 5 and r["profile_id"].startswith("P4"))
    return rep["summary"], rr, p4, engine


names = {a["zip"]: (a["area_name"] if not a["area_name"].startswith("ZCTA5") else a["zip"]) for a in base.areas}
b_summary, b_rr, _, _ = run(list(QUIET)[0])
print(f"{'quiet definition':44} {'P@3':>5} {'P@5':>5} {'MRR':>6} {'cov@5':>6}  P4 top 5 (neighborhood hit = *)          verdict")
for option in QUIET:
    s, rr, p4, engine = run(option)
    worse = [k for k in b_rr if rr[k] < b_rr[k] - 1e-9]
    gain = s["3"]["mrr"] - b_summary["3"]["mrr"]
    verdict = "baseline" if option == list(QUIET)[0] else ("ADOPT" if gain >= 0.02 and not worse else ("worse" if gain < 0 or worse else "tie"))
    rel = {z for n in ("Coconut Grove", "Coral Gables", "Pinecrest") for z in neighborhoods[n]}
    top = ", ".join(names[x["zip"]] + ("*" if x["zip"] in rel else "") for x in p4["response"]["results"])
    print(f"{option:44} {s['3']['precision']:5.2f} {s['5']['precision']:5.2f} {s['3']['mrr']:6.3f} {s['5']['neighborhood_coverage']:6.2f}  {top:42} {verdict}")
    print(f"{'':44} per-profile RR: " + " ".join(f"{k}:{v:.2f}" for k, v in rr.items()))


# ---------------------------------------------------------------------------
# Ranking-only comparison with a feasible budget (advisor review, Nov 12).
# At $2,200 P4 cannot afford any ZIP in its neighborhoods under HUD two-bedroom
# rents, so no quiet definition could improve it. A $3,300 development budget
# covers 8 of its 9 neighborhood ZIPs (all but 33146). P4 itself, the original
# profiles and the held-out sets are NOT changed; this only compares rankings.
DEV_BUDGET = 3300
p4 = next(p for p in profiles if p["profile_id"].startswith("P4"))
p4_dev = dict(p4, profile_id="P4_dev_budget", budget_max=DEV_BUDGET)
relevant = {z for n in p4["expected_neighborhoods"] for z in neighborhoods[n]}
print(f"\nP4 at a ${DEV_BUDGET} development budget (ranking comparison only; P4 unchanged)")
print(f"{'quiet definition':44} {'P@3':>5} {'P@5':>5} {'RR':>5}  expected-neighborhood ZIP ranks   top 5")
for option in QUIET:
    engine = Recommender("data")
    for a in engine.areas:
        a["quiet"] = QUIET[option][a["zip"]]
    row = {r["k"]: r for r in evaluate(engine, [p4_dev], neighborhoods)["profiles"]}
    ranks = sorted(v for v in row[5]["relevant_ranks"].values() if v)
    top = ", ".join(names[x["zip"]] + ("*" if x["zip"] in relevant else "") for x in row[5]["response"]["results"])
    print(f"{option:44} {row[3]['precision']:5.2f} {row[5]['precision']:5.2f} {row[3]['reciprocal_rank']:5.2f}  {str(ranks[:6]):32} {top}")
