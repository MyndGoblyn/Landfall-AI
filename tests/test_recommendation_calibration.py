import sys
from dataclasses import replace
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.recommendation_benchmark import (
    RecommendationBenchmarkResult,
    load_benchmark_cases,
)
from services.recommendation_calibration import (
    _compare_ranker_case,
    build_promotion_report,
    evaluate_deck_calibration,
    load_deck_calibration_cases,
    load_real_deck_validation_status,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DECK_FIXTURE = FIXTURE_DIR / "golden_deck_calibration.json"
RECOMMENDATION_FIXTURE = (
    FIXTURE_DIR / "golden_recommendation_benchmark.json"
)
REAL_DECK_STATUS_FIXTURE = FIXTURE_DIR / "real_deck_validation_status.json"


def test_deck_calibration_fixture_contains_99_card_quality_profiles():
    cases = load_deck_calibration_cases(DECK_FIXTURE)

    assert len(cases) == 8
    assert all(case.total_cards == 99 for case in cases)
    assert {case.id for case in cases} >= {
        "balanced_reliable_coverage",
        "cantrips_hide_draw_gap",
        "top_heavy_utility_suite",
        "efficient_multi_role_slots",
    }


def test_effective_role_assessment_clears_all_deck_calibration_cases():
    results = evaluate_deck_calibration(
        load_deck_calibration_cases(DECK_FIXTURE)
    )

    assert all(result.passed for result in results), [
        result.as_dict() for result in results if not result.passed
    ]


def test_latest_real_deck_status_allows_promotion_after_synthetic_gates_pass():
    real_deck_status = load_real_deck_validation_status(
        REAL_DECK_STATUS_FIXTURE
    )
    report = build_promotion_report(
        load_benchmark_cases(RECOMMENDATION_FIXTURE),
        load_deck_calibration_cases(DECK_FIXTURE),
        real_deck_validation=real_deck_status,
        include_details=True,
    )

    comparison = report["comparison"]
    assert comparison["ready_for_controlled_promotion"]
    assert all(comparison["gates"].values())
    assert comparison["regressed_case_ids"] == []
    assert comparison["top_choice_agreement"] >= 0.9
    assert report["deck_calibration"]["passed"]
    assert report["real_deck_validation"]["strict_passes"] == 18
    assert len(report["ranker_case_comparisons"]) == 14
    assert len(report["deck_case_results"]) == 8


def test_failing_real_deck_status_blocks_synthetic_promotion_result():
    real_deck_status = load_real_deck_validation_status(
        REAL_DECK_STATUS_FIXTURE
    )
    real_deck_status["passed"] = False
    real_deck_status["strict_passes"] = 6
    real_deck_status["partial"] = 2
    real_deck_status["failed"] = 10

    report = build_promotion_report(
        load_benchmark_cases(RECOMMENDATION_FIXTURE),
        load_deck_calibration_cases(DECK_FIXTURE),
        real_deck_validation=real_deck_status,
    )

    comparison = report["comparison"]
    assert not comparison["ready_for_controlled_promotion"]
    assert not comparison["gates"]["real_deck_validation_passed"]
    assert all(
        passed
        for gate, passed in comparison["gates"].items()
        if gate != "real_deck_validation_passed"
    )


def test_deck_calibration_failure_blocks_controlled_promotion():
    deck_cases = load_deck_calibration_cases(DECK_FIXTURE)
    incorrect_case = replace(
        deck_cases[0],
        expected_gap_additions={"draw": 1},
    )
    report = build_promotion_report(
        load_benchmark_cases(RECOMMENDATION_FIXTURE),
        [incorrect_case],
        real_deck_validation=load_real_deck_validation_status(
            REAL_DECK_STATUS_FIXTURE
        ),
    )

    assert not report["comparison"]["ready_for_controlled_promotion"]
    assert not report["comparison"]["gates"]["deck_calibration_passed"]
    assert report["deck_calibration"]["failed_case_ids"] == [
        "balanced_reliable_coverage"
    ]


def test_per_case_metric_regression_is_detected_even_when_names_match():
    legacy = RecommendationBenchmarkResult(
        case_id="regression_probe",
        top_names=("Best Card",),
        result_count=1,
        candidate_recall=1.0,
        core_recall_at_k=1.0,
        precision_at_k=1.0,
        ndcg_at_k=1.0,
        hard_rejections=(),
        reason_failures=(),
        unknown_results=(),
        gate_failures=(),
    )
    v2 = replace(legacy, ndcg_at_k=0.5)

    comparison = _compare_ranker_case(legacy, v2)

    assert comparison["same_top_choice"]
    assert comparison["regressed"]
    assert comparison["ndcg_delta"] == -0.5
