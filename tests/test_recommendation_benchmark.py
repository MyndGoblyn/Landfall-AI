import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.recommendation_benchmark import (
    RecommendationBenchmarkCase,
    aggregate_results,
    evaluate_recommendations,
    load_benchmark_cases,
)
from services.recommendation_benchmark_runner import execute_engine_benchmark


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "golden_recommendation_benchmark.json"
)


def test_recommendation_benchmark_fixture_is_versioned_and_well_formed():
    cases = load_benchmark_cases(FIXTURE_PATH)

    assert len(cases) >= 7
    assert {case.mode for case in cases} == {"commander", "deck_role"}
    assert all(case.global_banned_reason_fragments for case in cases)
    assert all(
        any(judgment.label == "core" for judgment in case.judgments)
        for case in cases
    )


def test_recommendation_benchmark_metrics_detect_bad_ranking_and_reasoning():
    case = RecommendationBenchmarkCase.from_dict(
        {
            "id": "metric_safety_check",
            "mode": "commander",
            "top_k": 2,
            "judgments": [
                {
                    "name": "Best Card",
                    "label": "core",
                    "required_evidence_tags": ["direct_synergy"],
                },
                {"name": "Bad Card", "label": "reject"},
            ],
            "gates": {"min_results": 1},
        }
    )

    result = evaluate_recommendations(
        case,
        [
            {
                "name": "Bad Card",
                "evidence_tags": [],
                "reason": "A loose match.",
            }
        ],
        retrieved_names=["Bad Card"],
    )

    assert not result.passed
    assert result.candidate_recall == 0
    assert result.core_recall_at_k == 0
    assert result.precision_at_k == 0
    assert result.hard_rejections == ("Bad Card",)
    assert result.gate_failures


def test_current_engine_clears_recommendation_quality_regression_gates():
    cases = load_benchmark_cases(FIXTURE_PATH)
    results = execute_engine_benchmark(cases, ranker_mode="legacy")
    failures = {
        result.case_id: result.as_dict()
        for result in results
        if not result.passed
    }

    assert not failures

    summary = aggregate_results(results)
    assert summary["passed"]
    assert summary["hard_rejection_count"] == 0
    assert summary["reason_failure_count"] == 0
    assert summary["mean_candidate_recall"] == 1.0

    v2_results = execute_engine_benchmark(cases, ranker_mode="v2")
    v2_failures = {
        result.case_id: result.as_dict()
        for result in v2_results
        if not result.passed
    }
    assert not v2_failures
    assert aggregate_results(v2_results)["mean_ndcg_at_k"] >= summary["mean_ndcg_at_k"]
