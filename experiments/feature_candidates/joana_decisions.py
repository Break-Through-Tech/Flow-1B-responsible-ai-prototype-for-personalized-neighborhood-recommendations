"""Test Joana's new data (transit service, rents, area names) against the current engine.

Run from the repo root:  python experiments/feature_candidates/joana_decisions.py
Inputs are cached copies of origin/joana files in experiments/feature_candidates/joana/.

Same rule as decisions.py, fixed before running: adopt only if MRR rises by >= 0.02 and
no profile's reciprocal rank falls; otherwise a tie, broken by the fairer option (place
measures over resident-demographic proxies), then the simpler one.
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

J = Path(__file__).parent / "joana"
profiles = json.load(open("eval/recommendation_profiles.json"))
base = Recommender("data")
ZIPS = [a["zip"] for a in base.areas]
land = {r["zip"]: float(r["land_sqmi"]) for r in csv.DictReader(open("data/zcta_geography.csv"))}
transit = {r["zip_code"]: r for r in csv.DictReader(open(J / "miami_transit.csv"))}
hud = {r["zip_code"]: r for r in csv.DictReader(open(J / "HUD-SAFMR.csv"))}


def num(row, col):
    try:
        value = float(row[col])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


def pct(values):
    return percentiles({z: values.get(z) for z in ZIPS})


def per_sqmi(col):
    return {z: num(transit[z], col) / land[z] if z in transit and land.get(z) and num(transit[z], col) is not None else None for z in ZIPS}


headway = {z: num(transit[z], "weekday_median_headway_minutes") if z in transit else None for z in ZIPS}
departures = pct(per_sqmi("weekday_departures"))
frequency = {z: None if v is None else 1 - v for z, v in pct(headway).items()}
TRANSIT = {
    "current: transit commute share": {a["zip"]: a["transit"] for a in base.areas},
    "weekday departures per sq mi": departures,
    "stops per sq mi": pct(per_sqmi("transit_stop_count")),
    "frequency (1 - median headway)": frequency,
    "departures/sq mi + frequency": {
        z: None if None in (departures[z], frequency[z]) else (departures[z] + frequency[z]) / 2
        for z in ZIPS
    },
}


def hud_rent(z, profile, option):
    row = hud.get(z, {})
    if option == "HUD 1BR for everyone":
        return num(row, "one_bedroom")
    if profile["housing_preference"] == "co_living":
        return num(row, "efficiency")
    return num(row, "two_bedroom" if profile["household"] == "with_co_leaser" else "one_bedroom")


RENT = ["current: ACS 2018-22 median", "HUD by unit size", "HUD 1BR for everyone"]


def run(transit_option, rent_option):
    rr, p3, p5, eligible = {}, [], [], []
    for profile in profiles:
        engine = Recommender("data")
        for a in engine.areas:
            a["transit"] = TRANSIT[transit_option][a["zip"]]
            if rent_option != RENT[0]:
                a["median_rent_usd"] = hud_rent(a["zip"], profile, rent_option)
        rows = {r["k"]: r for r in evaluate(engine, [profile])["profiles"]}
        rr[profile["profile_id"][:2]] = rows[3]["reciprocal_rank"]
        p3.append(rows[3]["precision"])
        p5.append(rows[5]["precision"])
        eligible.append(rows[3]["response"]["eligible_count"])
    return {"mrr": mean(rr.values()), "p3": mean(p3), "p5": mean(p5), "rr": rr, "eligible": eligible}


def verdict(b, t):
    worse = [k for k in b["rr"] if t["rr"][k] < b["rr"][k] - 1e-9]
    gain = t["mrr"] - b["mrr"]
    if gain >= 0.02 and not worse:
        return "ADOPT"
    if gain < -1e-9 or worse:
        return "worse" + (f" ({','.join(worse)} drop)" if worse else "")
    return "tie"


baseline = run(list(TRANSIT)[0], RENT[0])
print(f"{'option':42} {'MRR':>6} {'P@3':>5} {'P@5':>5}  per-profile RR                               verdict")
print(f"{'baseline (current engine)':42} {baseline['mrr']:6.3f} {baseline['p3']:5.2f} {baseline['p5']:5.2f}  " + " ".join(f"{k}:{v:.2f}" for k, v in baseline["rr"].items()))
print("-- transit")
for option in list(TRANSIT)[1:]:
    r = run(option, RENT[0])
    print(f"{option:42} {r['mrr']:6.3f} {r['p3']:5.2f} {r['p5']:5.2f}  " + " ".join(f"{k}:{v:.2f}" for k, v in r["rr"].items()) + f"   {verdict(baseline, r)}")
print("-- rent (budget filter)")
for option in RENT[1:]:
    r = run(list(TRANSIT)[0], option)
    print(f"{option:42} {r['mrr']:6.3f} {r['p3']:5.2f} {r['p5']:5.2f}  " + " ".join(f"{k}:{v:.2f}" for k, v in r["rr"].items()) + f"   {verdict(baseline, r)}")
    print(f"{'   eligible ZIPs per profile':42} {r['eligible']} (baseline {baseline['eligible']})")

names = {a["zip"]: a["area_name"] for a in base.areas}
for option in list(TRANSIT)[1:]:
    top = sorted((z for z in ZIPS if TRANSIT[option][z] is not None), key=lambda z: -TRANSIT[option][z])[:6]
    print(f"\ntop transit by {option}: " + ", ".join(names[z].replace("ZCTA5 ", "") for z in top))
