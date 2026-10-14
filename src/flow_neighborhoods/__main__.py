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
    parser.add_argument("--features", choices=FEATURE_SETS, default="provided")
    args = parser.parse_args()
    try:
        result = Recommender(
            args.data_dir, scorer=args.scorer, feature_set=args.features
        ).recommend(
            {
                "budget_max": args.budget,
                "household": args.household,
                "housing_preference": args.housing,
                "tags": args.tags,
                "k": args.k,
            }
        )
    except (ValidationError, DataError, OSError) as exc:
        parser.exit(2, f"{type(exc).__name__}: {exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
