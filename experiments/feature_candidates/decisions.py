"""Test each open decision with and without the change, using a fixed rule.

Run from the repo root:  python experiments/feature_candidates/decisions.py
Needs census/b25031.dat and noise/noise_by_zip.csv (see noise.py).

Rule (fixed before running): adopt a change only if MRR rises by >= 0.02 and
no profile's reciprocal rank falls. Otherwise it is a tie, broken by principle:
the fairer option (no resident-demographic proxies), then the simpler one.
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
base_engine = Recommender("data", feature_set="provided")  # for ZIPs and rents only
ZIPS = [a["zip"] for a in base_engine.areas]
land = {r["zip"]: float(r["land_sqmi"]) for r in csv.DictReader(open("data/zcta_geography.csv"))}


def acs(table):
    return {r["GEO_ID"][-5:]: r for r in csv.DictReader(open(HERE / f"census/{table}.dat"), delimiter="|")}


def share(num, den):
    return float(num) / float(den) if float(den) > 0 else None


commute, vehicles = acs("b08301"), acs("b08201")
population = {r["zip"]: float(r["population"]) for r in csv.DictReader(open("data/public_features_cleaned.csv"))}
noise = {r["zip"]: float(r["share_ge_55"]) for r in csv.DictReader(open(HERE / "noise/noise_by_zip.csv"))}
estab = {}
for r in csv.DictReader(open(HERE / "census/zbp_miami.csv")):
    estab.setdefault(r["zip"], {})[r["naics"]] = int(r["est"])
rent_by_size = {}
for r in csv.DictReader(open(HERE / "census/b25031.dat"), delimiter="|"):

    def ok(v):
        return float(v) if float(v) > 0 else None

    rent_by_size[r["GEO_ID"][-5:]] = {"all": ok(r["B25031_E001"]), "1br": ok(r["B25031_E003"]), "2br": ok(r["B25031_E004"])}


def pct(values):
    return percentiles({z: values.get(z) for z in ZIPS})


def per_sqmi(*codes):
    return {z: sum(estab.get(z, {}).get(c, 0) for c in codes) / land[z] if land.get(z) else None for z in ZIPS}


def inv(d):
    return {z: None if v is None else 1 - v for z, v in d.items()}


def avg(*ds):
    return {z: None if any(d[z] is None for d in ds) else sum(d[z] for d in ds) / len(ds) for z in ZIPS}


P = {
    "transit_commute": pct({z: share(commute[z]["B08301_E010"], commute[z]["B08301_E001"]) for z in ZIPS}),
    "no_vehicle": pct({z: share(vehicles[z]["B08201_E002"], vehicles[z]["B08201_E001"]) for z in ZIPS}),
    "food_drink": pct(per_sqmi("722///")),
    "food_drink_arts": pct(per_sqmi("722///", "71----")),
    "walk": pct({z: share(commute[z]["B08301_E019"], commute[z]["B08301_E001"]) for z in ZIPS}),
    "errands": pct(per_sqmi("4451//", "446///")),
    "density": pct({z: population[z] / land[z] if z in population and land.get(z) else None for z in ZIPS}),
    "bars": pct(per_sqmi("7224//")),
    "noise": pct(noise),
}
FEATURES = {
    "transit": {"commute + no-car": avg(P["transit_commute"], P["no_vehicle"]), "commute only": P["transit_commute"]},
    "social": {"restaurants+bars": P["food_drink"], "+ arts venues": P["food_drink_arts"]},
    "walkable": {"walk to work": P["walk"], "walk + errands": avg(P["walk"], P["errands"])},
    "quiet": {"density + nightlife": avg(inv(P["density"]), inv(P["bars"])), "noise": inv(P["noise"])},
}
RENT = ["all-unit median", "co-leaser 2BR", "co-leaser 2BR + alone 1BR"]
BASE = {"transit": "commute + no-car", "social": "restaurants+bars", "walkable": "walk to work",
        "quiet": "density + nightlife", "rent": "all-unit median", "co_living": "keep", "pet": "keep"}


def rent_for(z, profile, option):
    sizes = rent_by_size.get(z, {})
    if option != "all-unit median" and profile["housing_preference"] == "own_apartment":
        if profile["household"] == "with_co_leaser":
            return sizes.get("2br")
        if option.endswith("1BR"):
            return sizes.get("1br")
    return next(a["median_rent_usd"] for a in base_engine.areas if a["zip"] == z)


def run(config):
    rr, p3, p5, eligible = {}, [], [], []
    for profile in profiles:
        engine = Recommender("data", feature_set="census")
        for a in engine.areas:
            for feat in ("transit", "social", "walkable", "quiet"):
                a[feat] = FEATURES[feat][config[feat]][a["zip"]]
            a["median_rent_usd"] = rent_for(a["zip"], profile, config["rent"])
            if config["pet"] == "drop":
                a["pet_friendly"] = 0.0  # constant, so it cannot reorder; tests the claim
        p = dict(profile)
        if config["co_living"] == "drop" and p["housing_preference"] == "co_living":
            # Score co-living requests on their other tags only.
            for a in engine.areas:
                a["co_living_friendly"] = 0.0
        rep = evaluate(engine, [p])
        rows = {r["k"]: r for r in rep["profiles"]}
        rr[p["profile_id"][:2]] = rows[3]["reciprocal_rank"]
        p3.append(rows[3]["precision"])
        p5.append(rows[5]["precision"])
        eligible.append(rows[3]["response"]["eligible_count"])
    return {"mrr": mean(rr.values()), "p3": mean(p3), "p5": mean(p5), "rr": rr, "eligible": eligible}


def verdict(base, test):
    worse = [k for k in base["rr"] if test["rr"][k] < base["rr"][k] - 1e-9]
    if test["mrr"] - base["mrr"] >= 0.02 and not worse:
        return "ADOPT"
    if worse and test["mrr"] - base["mrr"] >= 0.02:
        return f"tie (better MRR but {','.join(worse)} worse)"
    if test["mrr"] < base["mrr"] - 1e-9:
        return "reject (worse)"
    return "tie"


base = run(BASE)
print(f"baseline: MRR {base['mrr']:.3f} P@3 {base['p3']:.2f} P@5 {base['p5']:.2f}  rr {base['rr']}")
print(f"\n{'decision':10} {'option':28} {'MRR':>6} {'P@3':>5} {'P@5':>5}  {'per-profile reciprocal rank':40} verdict")
tests = [("transit", "commute only"), ("social", "+ arts venues"), ("walkable", "walk + errands"),
         ("quiet", "noise"), ("rent", "co-leaser 2BR"), ("rent", "co-leaser 2BR + alone 1BR"),
         ("co_living", "drop"), ("pet", "drop")]
for key, option in tests:
    res = run(dict(BASE, **{key: option}))
    rr = " ".join(f"{k}:{v:.2f}" for k, v in res["rr"].items())
    print(f"{key:10} {option:28} {res['mrr']:6.3f} {res['p3']:5.2f} {res['p5']:5.2f}  {rr:40} {verdict(base, res)}")
    if key == "rent":
        print(f"{'':10} {'eligible ZIPs per profile':28} {res['eligible']} (baseline {base['eligible']})")
cov = {k: sum(1 for z in ZIPS if rent_by_size.get(z, {}).get(k)) for k in ("all", "1br", "2br")}
print(f"\nrent coverage among {len(ZIPS)} ZIPs: {cov}")
