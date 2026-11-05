"""Compare promotion candidates against recommendation and deck-profile gates."""

import argparse
import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1]
REPO_PATH = BACKEND_PATH.parent
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.recommendation_benchmark import load_benchmark_cases
from services.recommendation_calibration import (
    build_promotion_report,
    load_deck_calibration_cases,
    load_real_deck_validation_status,
)


DEFAULT_RECOMMENDATION_FIXTURE = (
    REPO_PATH / "tests" / "fixtures" / "golden_recommendation_benchmark.json"
)
DEFAULT_DECK_FIXTURE = (
    REPO_PATH / "tests" / "fixtures" / "golden_deck_calibration.json"
)
DEFAULT_REAL_DECK_STATUS = (
    REPO_PATH / "tests" / "fixtures" / "real_deck_validation_status.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate whether Recommendation Ranker V2 is safe for a controlled "
            "promotion from shadow mode."
        )
    )
    parser.add_argument(
        "--recommendation-fixture",
        type=Path,
        default=DEFAULT_RECOMMENDATION_FIXTURE,
    )
    parser.add_argument(
        "--deck-fixture",
        type=Path,
        default=DEFAULT_DECK_FIXTURE,
    )
    parser.add_argument(
        "--real-deck-status",
        type=Path,
        default=DEFAULT_REAL_DECK_STATUS,
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Include per-case ranker comparisons and deck calibration results.",
    )
    args = parser.parse_args()

    benchmark_cases = load_benchmark_cases(
        args.recommendation_fixture.resolve()
    )
    deck_cases = load_deck_calibration_cases(args.deck_fixture.resolve())
    real_deck_validation = load_real_deck_validation_status(
        args.real_deck_status.resolve()
    )
    report = build_promotion_report(
        benchmark_cases,
        deck_cases,
        real_deck_validation=real_deck_validation,
        include_details=args.details,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return (
        0
        if report["comparison"]["ready_for_controlled_promotion"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
