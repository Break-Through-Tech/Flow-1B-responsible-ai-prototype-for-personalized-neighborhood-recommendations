"""Compare candidate data sources per lifestyle tag.

Run from the repo root with the repo venv:
    python features_experiment.py <census_dir>
Every candidate is scaled the same way (percentile among snapshot ZIPs), so only
the underlying measurement differs. Definitions were fixed before evaluation.
"""

import bisect
import csv
import itertools
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "src")
from flow_neighborhoods import Recommender  # noqa: E402
from flow_neighborhoods.contracts import Request  # noqa: E402
from flow_neighborhoods.evaluate import evaluate  # noqa: E402

census = Path(sys.argv[1])
base = Recommender("data", feature_set="provided")
ZIPS = [a["zip"] for a in base.areas]
NAMES = {a["zip"]: a["area_name"] for a in base.areas}


def acs(table):
    with (census / f"{table}.dat").open() as f:
        rows = csv.DictReader(f, delimiter="|")
        return {r["GEO_ID"][-5:]: {k: float(v) for k, v in r.items() if "_E" in k} for r in rows}


b08301, b08201, b25024 = acs("b08301"), acs("b08201"), acs("b25024")
estab = {}
with (census / "zbp_miami.csv").open() as f:
    for r in csv.DictReader(f):
        estab.setdefault(r["zip"], {})[r["naics"]] = int(r["est"])
land = {r["zip"]: float(r["land_sqmi"]) for r in csv.DictReader(open("data/zcta_geography.csv"))}
pop = {r["zip"]: float(r["population"]) for r in csv.DictReader(open("data/public_features_cleaned.csv"))}
tenure = {r["zip"]: (float(r["B25003_002E"]), float(r["B25003_003E"]))
          for r in csv.DictReader(open("data/public_features_cleaned.csv"))}


def share(num, den):
    return num / den if num is not None and den else None


def per_sqmi(z, *codes):
    if z not in land or not land[z]:
        return None
    return sum(estab.get(z, {}).get(c, 0) for c in codes) / land[z]


RAW = {
    # transit: what people actually do / need
    "transit_commute": lambda z: share(b08301[z]["B08301_E010"], b08301[z]["B08301_E001"]),
    "no_car": lambda z: share(b08201[z]["B08201_E002"], b08201[z]["B08201_E001"]),
    # social: places to go
    "food_drink_density": lambda z: per_sqmi(z, "722///"),
    "food_drink_arts_density": lambda z: per_sqmi(z, "722///", "71----"),
    "bar_density": lambda z: per_sqmi(z, "7224//"),
    "pop_density": lambda z: share(pop.get(z), land.get(z)),
    # walkable: daily needs reachable on foot
    "walk_commute": lambda z: share(b08301[z]["B08301_E019"], b08301[z]["B08301_E001"]),
    "errands_density": lambda z: per_sqmi(z, "4451//", "446///"),
    # quiet: settled, low-rise residential
    "single_family": lambda z: share(b25024[z]["B25024_E002"], b25024[z]["B25024_E001"]),
    "owner_occupied": lambda z: share(tenure[z][0], sum(tenure[z])) if z in tenure else None,
    "low_rise": lambda z: share(b25024[z]["B25024_E001"] - sum(b25024[z][f"B25024_E00{i}"] for i in (7, 8, 9)),
                                b25024[z]["B25024_E001"]),
}


def percentile(values):
    known = {z: v for z, v in values.items() if v is not None}
    ordered = sorted(known.values())
    return {z: (bisect.bisect_left(ordered, known[z]) / (len(ordered) - 1) if z in known else None)
            for z in values}


P = {name: percentile({z: fn(z) if z in b08301 else None for z in ZIPS}) for name, fn in RAW.items()}
P["transit_commute+no_car"] = {z: None if None in (P["transit_commute"][z], P["no_car"][z])
                               else (P["transit_commute"][z] + P["no_car"][z]) / 2 for z in ZIPS}
P["walk_commute+errands"] = {z: None if None in (P["walk_commute"][z], P["errands_density"][z])
                             else (P["walk_commute"][z] + P["errands_density"][z]) / 2 for z in ZIPS}
for name in ("pop_density", "bar_density"):
    P["1-" + name] = {z: None if v is None else 1 - v for z, v in P[name].items()}
PROVIDED = {f: {a["zip"]: a[f] for a in base.areas} for f in ("transit", "social", "walkable", "quiet")}

CANDIDATES = {
    "transit": ["provided", "transit_commute", "no_car", "transit_commute+no_car"],
    "social": ["provided", "food_drink_density", "food_drink_arts_density", "bar_density", "pop_density"],
    "walkable": ["provided", "walk_commute", "errands_density", "no_car", "pop_density", "walk_commute+errands"],
    "quiet": ["provided", "single_family", "owner_occupied", "low_rise", "1-pop_density", "1-bar_density"],
}
profiles = json.load(open("eval/recommendation_profiles.json"))


def engine_with(config):
    e = Recommender("data", feature_set="provided")
    for a in e.areas:
        for feat, cand in config.items():
            a[feat] = PROVIDED[feat][a["zip"]] if cand == "provided" else P[cand][a["zip"]]
    return e


def score(config, subset=None):
    use = [p for p in profiles if subset is None or subset in p["tags"]]
    rep = evaluate(engine_with(config), use)
    s = rep["summary"]
    return s["3"]["precision"], s["5"]["precision"], s["3"]["mrr"], len(use)


def values(cand, feat):
    return PROVIDED[feat] if cand == "provided" else P[cand]


print("=== 1. One tag at a time (others stay provided); only profiles that request the tag ===")
for feat, cands in CANDIDATES.items():
    print(f"\n[{feat}]")
    for cand in cands:
        p3, p5, mrr, n = score({feat: cand}, subset=feat)
        vals = values(cand, feat)
        top = sorted((z for z in ZIPS if vals[z] is not None), key=lambda z: -vals[z])[:5]
        print(f"  {cand:26} P@3={p3:.2f} P@5={p5:.2f} MRR={mrr:.2f} (n={n})  top5: "
              + ", ".join(f"{NAMES[z].replace('ZCTA5 ', '')}" for z in top))

print("\n=== 2. Correlation between candidates (|r| near 1 = same signal) ===")
def corr(a, b):
    pairs = [(a[z], b[z]) for z in ZIPS if a[z] is not None and b[z] is not None]
    xs, ys = zip(*pairs)
    mx, my = st.mean(xs), st.mean(ys)
    return sum((x - mx) * (y - my) for x, y in pairs) / (st.pstdev(xs) * st.pstdev(ys) * len(pairs))
picks = ["transit_commute", "no_car", "food_drink_density", "walk_commute", "errands_density",
         "pop_density", "single_family", "owner_occupied", "low_rise"]
print(" " * 20 + " ".join(f"{p[:9]:>9}" for p in picks))
for a in picks:
    print(f"{a[:19]:20}" + " ".join(f"{corr(P[a], P[b]):9.2f}" for b in picks))

print("\n=== 3. All combinations on all 5 profiles (top 12 by MRR) ===")
results = []
for combo in itertools.product(*CANDIDATES.values()):
    config = dict(zip(CANDIDATES, combo))
    p3, p5, mrr, _ = score(config)
    e = engine_with(config)
    tie = e.recommend({"budget_max": 2500, "household": "alone", "housing_preference": "own_apartment",
                       "tags": ["social", "quiet"], "k": 5})
    spread = len({round(r["score"], 6) for r in e.rank(Request.parse(
        {"budget_max": 2500, "household": "alone", "housing_preference": "own_apartment",
         "tags": ["social", "quiet"]}))[0]})
    results.append((mrr, p3, p5, spread, combo))
results.sort(key=lambda r: (-r[0], -r[1]))
print(f"  {'MRR':>5} {'P@3':>5} {'P@5':>5} {'social+quiet distinct scores':>28}  transit / social / walkable / quiet")
for mrr, p3, p5, spread, combo in results[:12]:
    print(f"  {mrr:5.2f} {p3:5.2f} {p5:5.2f} {spread:28d}  {' / '.join(combo)}")
print(f"\n  ({len(results)} combinations; all-provided baseline: "
      + "MRR={:.2f} P@3={:.2f}".format(*[(r[0], r[1]) for r in results if r[4] == ('provided',) * 4][0]) + ")")
mrrs = sorted(r[0] for r in results)
print(f"  MRR spread across all combos: min {mrrs[0]:.2f}, median {st.median(mrrs):.2f}, max {mrrs[-1]:.2f}")
