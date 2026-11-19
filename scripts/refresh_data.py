"""Monthly data refresh: check sources, stage a rebuild, review the report, then apply.

Run from the repo root:
    python scripts/refresh_data.py check
    python scripts/refresh_data.py fetch [--acs-year Y] [--zbp-year Y] [--gazetteer-year Y]
                                         [--hud-fy Y] [--joana DIR] [--stage DIR]
    python scripts/refresh_data.py build STAGE
    python scripts/refresh_data.py apply STAGE

check   lists newer Census releases, stale transit data and co-living listings to re-verify.
fetch   downloads the Census sources (filtered to Miami-Dade ZIPs) into STAGE/inputs, copies
        noise and Joana's files (HUD rents, area names, transit) from the cache or --joana,
        then runs build.
build   rebuilds the data files into STAGE/data, runs the data checks on them, compares the
        evaluation before and after, and writes STAGE/report.md.
apply   copies a reviewed stage into data/ and the raw cache. Refuses if the checks failed.

Nothing in data/ changes before apply. Stages live under outputs/refresh/ (git-ignored).
Only the original five profiles are scored; the held-out sets stay unscored.
"""

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / "experiments" / "feature_candidates"
BUILD = CACHE / "build_data.py"
SOURCES = DATA / "data_sources.json"
BUILT = {
    "zcta_geography.csv": ("zip",),
    "census_features.csv": ("zip",),
    "rents_hud.csv": ("zip",),
    "zip_area_names.csv": ("zip",),
    "transit_service.csv": ("zip",),
    "neighborhood_aliases.csv": ("alias", "zip"),
}
JOANA_FILES = ["HUD-SAFMR.csv", "area-name.csv", "miami_transit.csv"]
URLS = {
    "acs_year": "https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/"
    "data/5YRData/acsdt5y{y}-b08301.dat",
    "zbp_year": "https://www2.census.gov/programs-surveys/cbp/datasets/{y}/zbp{yy}detail.zip",
    "gazetteer_year": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "{y}_Gazetteer/{y}_Gaz_zcta_national.zip",
}
LABELS = {
    "acs_year": "ACS 5-year B08301 (commute mode)",
    "zbp_year": "ZIP Code Business Patterns (restaurants and bars, USPS city)",
    "gazetteer_year": "Census Gazetteer ZCTA (land area, location)",
    "noise_year": "BTS transportation noise map",
    "hud_fy": "HUD Small Area Fair Market Rents (fiscal year)",
}
# Vintages in the committed data before this script existed.
DEFAULT_VINTAGES = {
    "acs_year": 2022,
    "zbp_year": 2021,
    "gazetteer_year": 2023,
    "noise_year": 2020,
    "hud_fy": 2026,
}
STALE_DAYS = 35
AGENT = {"User-Agent": "flow-neighborhoods-data-refresh"}


def vintages() -> dict:
    if SOURCES.exists():
        return json.loads(SOURCES.read_text(encoding="utf-8"))["vintages"]
    return dict(DEFAULT_VINTAGES)


def url(key: str, year: int) -> str:
    return URLS[key].format(y=year, yy=str(year)[2:])


def published(address: str) -> bool:
    request = urllib.request.Request(address, method="HEAD", headers=AGENT)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def newest(key: str, current: int) -> int:
    latest = current
    for year in range(current + 1, date.today().year + 1):
        if published(url(key, year)):
            latest = year
    return latest


def zips() -> list[str]:
    lines = (DATA / "miami_dade_zctas.txt").read_text(encoding="utf-8").splitlines()
    return [z.strip() for z in lines if z.strip()]


def table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def age(day: str) -> int | None:
    try:
        return (date.today() - date.fromisoformat(day.strip()[:10])).days
    except ValueError:
        return None


# --- check ------------------------------------------------------------------------------


def check(_args) -> int:
    current = vintages()
    print("Source releases")
    for key in URLS:
        label = LABELS[key]
        latest = newest(key, current[key])
        note = f"newer release: {latest}" if latest > current[key] else "up to date"
        print(f"  {label}: using {current[key]}, {note}")
    today = date.today()
    hud_due = today.year + 1 if today.month >= 10 else today.year
    hud = f"using FY{current['hud_fy']}"
    if current["hud_fy"] < hud_due:
        hud += (
            f"; FY{hud_due} (starts Oct 1) may be out: check huduser.gov, ask Joana for a new file"
        )
    print(f"  HUD Small Area FMR: {hud} (huduser.gov blocks automated checks)")
    print(f"  BTS noise map: using {current['noise_year']} (updated every few years; no check)")

    print("\nTransit (Joana's GTFS build)")
    days = [age(r["data_as_of"]) for r in table(DATA / "transit_service.csv")]
    oldest = max((d for d in days if d is not None), default=None)
    if oldest is None or oldest > STALE_DAYS:
        print(f"  built {oldest} days ago; ask Joana to rerun build_transit_data.py on a new feed")
    else:
        print(f"  built {oldest} days ago, current")

    print(f"\nCo-living listings observed more than {STALE_DAYS} days ago (re-verify)")
    stale = [
        r for r in table(DATA / "co_living_listings.csv") if (age(r["observed"]) or 0) > STALE_DAYS
    ]
    for r in stale:
        print(f"  {r['property']} ({r['zip']}), observed {r['observed']}")
    if not stale:
        print("  none")
    return 0


# --- fetch ------------------------------------------------------------------------------


def download(address: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(address, headers=AGENT), timeout=300) as r:
        return r.read()


def fetch_acs(year: int, target: Path, wanted: set[str]) -> None:
    geoids = {f"860Z200US{z}".encode() for z in wanted}
    request = urllib.request.Request(url("acs_year", year), headers=AGENT)
    kept = 0
    with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as out:
        out.write(response.readline())
        for line in response:
            if line.split(b"|", 1)[0] in geoids:
                out.write(line)
                kept += 1
    if not kept:
        raise SystemExit(f"ACS {year}: no Miami-Dade ZCTA rows found")


def fetch_zbp(year: int, target: Path, wanted: set[str]) -> None:
    archive = zipfile.ZipFile(io.BytesIO(download(url("zbp_year", year))))
    name = next(n for n in archive.namelist() if n.lower().endswith(".txt"))
    with archive.open(name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""))
        missing = {"zip", "naics", "est", "city"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"ZBP {year}: columns changed, missing {sorted(missing)}")
        with target.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=reader.fieldnames, quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()
            writer.writerows(r for r in reader if r["zip"] in wanted)


def fetch_gazetteer(year: int, folder: Path, wanted: set[str]) -> None:
    archive = zipfile.ZipFile(io.BytesIO(download(url("gazetteer_year", year))))
    name = next(n for n in archive.namelist() if n.endswith(".txt"))
    lines = archive.read(name).decode("utf-8").splitlines(keepends=True)
    sep = "|" if "|" in lines[0] else "\t"  # pipe-delimited from the 2025 release on
    kept = [lines[0]] + [line for line in lines[1:] if line.split(sep, 1)[0] in wanted]
    if len(kept) == 1:
        raise SystemExit(f"Gazetteer {year}: no Miami-Dade ZCTA rows found")
    (folder / f"{year}_Gaz_zcta_national.txt").write_text("".join(kept), encoding="utf-8")


def fetch(args) -> int:
    current = vintages()
    chosen = {
        "acs_year": args.acs_year or newest("acs_year", current["acs_year"]),
        "zbp_year": args.zbp_year or newest("zbp_year", current["zbp_year"]),
        "gazetteer_year": args.gazetteer_year
        or newest("gazetteer_year", current["gazetteer_year"]),
        "noise_year": current["noise_year"],
        "hud_fy": args.hud_fy or current["hud_fy"],
    }
    stage = Path(args.stage or ROOT / "outputs" / "refresh" / date.today().isoformat())
    census = stage / "inputs" / "census"
    if stage.exists():
        shutil.rmtree(stage)
    for sub in ("census", "noise", "joana"):
        (stage / "inputs" / sub).mkdir(parents=True)
    wanted = set(zips())
    print(f"Downloading ACS {chosen['acs_year']} B08301 (~90 MB, filtered as it streams)")
    fetch_acs(chosen["acs_year"], census / "b08301.dat", wanted)
    print(f"Downloading ZIP Code Business Patterns {chosen['zbp_year']}")
    fetch_zbp(chosen["zbp_year"], census / "zbp_miami.csv", wanted)
    print(f"Downloading Gazetteer {chosen['gazetteer_year']}")
    fetch_gazetteer(chosen["gazetteer_year"], census, wanted)
    (census / "sources.json").write_text(json.dumps(chosen, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(CACHE / "noise" / "noise_by_zip.csv", stage / "inputs" / "noise")
    joana = Path(args.joana) if args.joana else CACHE / "joana"
    for name in JOANA_FILES:
        shutil.copy2(joana / name, stage / "inputs" / "joana" / name)
    return build(argparse.Namespace(stage=stage))


# --- build ------------------------------------------------------------------------------


def number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare(old: Path, new: Path, key: tuple[str, ...]) -> list[str]:
    before = {tuple(r[k] for k in key): r for r in table(old)} if old.exists() else {}
    after = {tuple(r[k] for k in key): r for r in table(new)}
    added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
    numeric, text = {}, []
    for k in sorted(before.keys() & after.keys()):
        for column, value in after[k].items():
            was = before[k].get(column)
            if was == value:
                continue
            a, b = number(was), number(value)
            if a is not None and b is not None:
                numeric.setdefault(column, []).append((k, a, b, (b - a) / a if a else None))
            else:
                text.append(f"{'/'.join(k)} {column}: {was!r} -> {value!r}")
    lines = [f"{len(after)} rows; {len(added)} added, {len(removed)} removed"]
    if added:
        lines.append("added: " + ", ".join("/".join(k) for k in added[:15]))
    if removed:
        lines.append("removed: " + ", ".join("/".join(k) for k in removed[:15]))
    for column, changes in numeric.items():
        rel = [c[3] for c in changes if c[3] is not None]
        big = sorted(changes, key=lambda c: -abs(c[3] or 0))[:5]
        lines.append(
            f"`{column}`: {len(changes)} changed, median {median(rel):+.1%}; largest: "
            + ", ".join(f"{'/'.join(k)} {a:g} -> {b:g}" for k, a, b, _ in big)
            if rel
            else f"`{column}`: {len(changes)} changed"
        )
    lines += text[:10]
    if len(text) > 10:
        lines.append(f"... and {len(text) - 10} more text changes")
    return lines


def scores(data_dir: Path) -> tuple[dict, dict]:
    sys.path.insert(0, str(ROOT / "src"))
    from flow_neighborhoods import Recommender
    from flow_neighborhoods.evaluate import evaluate

    profiles = json.loads((ROOT / "eval" / "recommendation_profiles.json").read_text("utf-8"))
    mapping = json.loads((ROOT / "eval" / "neighborhood_zips.json").read_text("utf-8"))
    report = evaluate(Recommender(data_dir), profiles, mapping["neighborhoods"])
    tops = {
        r["profile_id"]: [x["zip"] for x in r["response"]["results"]]
        for r in report["profiles"]
        if r["k"] == 3
    }
    return report["summary"]["3"], tops


def build(args) -> int:
    stage = Path(args.stage)
    inputs, built = stage / "inputs", stage / "data"
    census = inputs / "census"
    gazetteers = sorted(census.glob("*_Gaz_zcta_national.txt"))
    if len(gazetteers) != 1:
        raise SystemExit(f"expected one Gazetteer file in {census}, found {len(gazetteers)}")
    if built.exists():
        shutil.rmtree(built)
    shutil.copytree(DATA, built)
    subprocess.run(
        [sys.executable, str(BUILD), str(gazetteers[0]), str(census), str(built)],
        cwd=ROOT,
        check=True,
    )
    chosen = json.loads((census / "sources.json").read_text("utf-8"))
    current = vintages()

    checks = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_data_files.py",
        ],
        cwd=ROOT,
        check=False,
        env=dict(os.environ, FLOW_DATA_CHECK_DIR=str(built)),
        capture_output=True,
        text=True,
    )
    passed = checks.returncode == 0
    before, before_top = scores(DATA)
    after, after_top = scores(built)

    out = [f"# Data refresh {stage.name}", ""]
    out += ["## Sources", "", "| Source | Now | Staged |", "|---|---:|---:|"]
    for key in DEFAULT_VINTAGES:
        flag = " **new**" if chosen[key] != current[key] else ""
        out.append(f"| {LABELS[key]} | {current[key]} | {chosen[key]}{flag} |")
    out += [
        "",
        "HUD rents, area names and transit are Joana's files, copied as given; noise is unchanged.",
        "",
        "## Data checks",
        "",
        f"{'Passed' if passed else '**Failed**'}: `tests/test_data_files.py` on the staged files.",
        "",
        "```",
        checks.stdout.strip().splitlines()[-1] if checks.stdout.strip() else checks.stderr[-500:],
        "```",
        "",
        "## Changes by file",
        "",
    ]
    for name, key in BUILT.items():
        out.append(f"**{name}**")
        out += [f"- {line}" for line in compare(DATA / name, built / name, key)]
        out.append("")
    out += ["## Evaluation (original five profiles, top 3)", ""]
    out += ["| Metric | Now | Staged |", "|---|---:|---:|"]
    for metric in ("precision", "mrr", "neighborhood_coverage", "budget_pass_rate_nonempty"):
        out.append(f"| {metric} | {before[metric]:.2f} | {after[metric]:.2f} |")
    moved = [p for p in before_top if before_top[p] != after_top.get(p)]
    out.append("")
    for p in moved:
        out.append(f"- {p}: {', '.join(before_top[p])} -> {', '.join(after_top[p])}")
    if not moved:
        out.append("No profile's top 3 changed.")
    stale_docs = [
        f"- `data_dictionary.md:{i}`: {line.strip()}"
        for i, line in enumerate((ROOT / "data_dictionary.md").read_text("utf-8").splitlines(), 1)
        for key in ("acs_year", "zbp_year", "gazetteer_year")
        if chosen[key] != current[key] and str(current[key]) in line
    ]
    out += ["", "## Before applying", ""]
    if stale_docs:
        out += ["Update the source years in these lines after applying:", *stale_docs, ""]
    out += [
        "Read the changes above. If they look right:",
        "",
        f"    python scripts/refresh_data.py apply {stage.relative_to(ROOT).as_posix()}",
        "",
        "then run the tests, review `git diff data/`, and open a PR with this report.",
    ]
    (stage / "report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    status = {"checks_passed": passed, "vintages": chosen, "built": date.today().isoformat()}
    (stage / "status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {stage / 'report.md'} (data checks {'passed' if passed else 'FAILED'})")
    return 0 if passed else 1


# --- apply ------------------------------------------------------------------------------


def apply(args) -> int:
    stage = Path(args.stage)
    status = json.loads((stage / "status.json").read_text("utf-8"))
    if not status["checks_passed"]:
        raise SystemExit("data checks failed for this stage; fix the inputs and rebuild")
    for name in BUILT:
        shutil.copy2(stage / "data" / name, DATA / name)
    census = CACHE / "census"
    for old in census.glob("*_Gaz_zcta_national.txt"):
        old.unlink()
    for sub in ("census", "noise", "joana"):
        (CACHE / sub).mkdir(parents=True, exist_ok=True)
        for path in (stage / "inputs" / sub).iterdir():
            shutil.copy2(path, CACHE / sub / path.name)
    record = {"refreshed": status["built"], "vintages": status["vintages"]}
    SOURCES.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Applied {stage.name}. Next: update docs listed in report.md, run pytest, open a PR.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check").set_defaults(run=check)
    f = commands.add_parser("fetch")
    for flag in ("--acs-year", "--zbp-year", "--gazetteer-year", "--hud-fy"):
        f.add_argument(flag, type=int)
    f.add_argument("--joana", help="folder with Joana's updated " + ", ".join(JOANA_FILES))
    f.add_argument("--stage")
    f.set_defaults(run=fetch)
    for name, run in (("build", build), ("apply", apply)):
        p = commands.add_parser(name)
        p.add_argument("stage")
        p.set_defaults(run=run)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
