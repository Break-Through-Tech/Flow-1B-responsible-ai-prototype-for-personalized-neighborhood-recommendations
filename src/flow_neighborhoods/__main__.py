"""Run from the repository root: python -m flow_neighborhoods --budget 2500 ..."""

import argparse
import json

from .contracts import ValidationError
from .data import DataError
from .engine import FEATURE_SETS, SCORERS, Recommender


def main():
    parser = argparse.ArgumentParser(description="Offline ZIP recommendation baseline")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--household", choices=["alone", "with_co_leaser"], default="alone")
    parser.add_argument(
        "--housing", choices=["own_apartment", "co_living"], default="own_apartment"
    )
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--scorer", choices=list(SCORERS), default="mean")
    parser.add_argument("--features", choices=FEATURE_SETS, default="census")
    parser.add_argument(
        "--weight", action="append", default=[], metavar="TAG=1|2|3", help="priority of a tag"
    )
    parser.add_argument("--near", action="append", default=[], metavar="NEIGHBORHOOD")
    args = parser.parse_args()
    try:
        weights = {}
        for item in args.weight:
            tag, _, level = item.partition("=")
            if not level.isdigit():
                raise ValidationError(f"--weight expects TAG=1|2|3, got {item!r}.")
            weights[tag] = int(level)
        engine = Recommender(args.data_dir, scorer=args.scorer, feature_set=args.features)
        result = engine.recommend(
            {
                "budget_max": args.budget,
                "household": args.household,
                "housing_preference": args.housing,
                "tags": args.tags,
                "k": args.k,
                "weights": weights,
                "near": args.near,
            }
        )
    except (ValidationError, DataError, OSError) as exc:
        parser.exit(2, f"{type(exc).__name__}: {exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
