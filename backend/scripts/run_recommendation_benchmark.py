"""Print the deterministic recommendation quality report and fail on regression."""

import argparse
import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1]
REPO_PATH = BACKEND_PATH.parent
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.recommendation_benchmark import aggregate_results, load_benchmark_cases
from services.recommendation_benchmark_runner import execute_engine_benchmark


DEFAULT_FIXTURE = (
    REPO_PATH / "tests" / "fixtures" / "golden_recommendation_benchmark.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run LandFallAI recommendation quality regression gates."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="Path to a versioned recommendation benchmark JSON fixture.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Include every per-case result instead of failures only.",
    )
    parser.add_argument(
        "--ranker",
        choices=["legacy", "shadow", "v2"],
        default="legacy",
        help="Recommendation ranking path to evaluate (default: legacy).",
    )
    args = parser.parse_args()

    cases = load_benchmark_cases(args.fixture.resolve())
    results = execute_engine_benchmark(cases, ranker_mode=args.ranker)
    summary = aggregate_results(results)
    report = {
        "ranker": args.ranker,
        "summary": summary,
        "results": [
            result.as_dict()
            for result in results
            if args.details or not result.passed
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
