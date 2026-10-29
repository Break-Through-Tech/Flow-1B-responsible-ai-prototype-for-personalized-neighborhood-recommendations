import runpy, sys, io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    script = sys.argv.pop(1)
    g = runpy.run_path(script, run_name="exp")
score, engine_with, profiles = g["score"], g["engine_with"], g["profiles"]
from flow_neighborhoods.contracts import Request
for q in ["provided", "single_family", "owner_occupied", "low_rise"]:
    cfg = {"transit": "transit_commute+no_car", "social": "food_drink_density", "walkable": "walk_commute", "quiet": q}
    p3, p5, mrr, _ = score(cfg)
    e = engine_with(cfg)
    ranks = []
    for p in profiles:
        order = [x["zip"] for x in e.rank(Request.parse({k: p[k] for k in ("budget_max","household","housing_preference","tags")}))[0]]
        ranks.append(f"{p['profile_id'][:2]}:" + ",".join(str(order.index(z)+1) for z in p["expected_relevant_zips"]))
    print(f"quiet={q:15} P@3={p3:.2f} P@5={p5:.2f} MRR={mrr:.2f}  expected ranks {' '.join(ranks)}")
