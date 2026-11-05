"""Promotion calibration for ranker and deck-role quality changes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.recommendation_benchmark import (
    RecommendationBenchmarkCase,
    RecommendationBenchmarkResult,
    aggregate_results,
)
from services.recommendation_benchmark_runner import execute_engine_benchmark


class CalibrationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DeckCalibrationCase:
    id: str
    description: str
    total_cards: int
    cards: Tuple[Mapping, ...]
    expected_gap_additions: Mapping[str, int]
    expected_hidden_quality_gaps: Tuple[str, ...]
    expected_statuses: Mapping[str, str]

    @classmethod
    def from_dict(cls, value: Mapping) -> "DeckCalibrationCase":
        case_id = str(value.get("id", "")).strip()
        cards = tuple(
            dict(card)
            for card in value.get("cards") or []
            if isinstance(card, Mapping)
        )
        if not case_id:
            raise CalibrationValidationError("Deck calibration case requires an id.")
        if not cards:
            raise CalibrationValidationError(
                f"Deck calibration case {case_id!r} requires cards."
            )
        total_cards = int(value.get("total_cards", 0))
        if total_cards <= 0:
            raise CalibrationValidationError(
                f"Deck calibration case {case_id!r} requires total_cards."
            )
        return cls(
            id=case_id,
            description=str(value.get("description", "")).strip(),
            total_cards=total_cards,
            cards=cards,
            expected_gap_additions={
                str(role): int(count)
                for role, count in (
                    value.get("expected_gap_additions") or {}
                ).items()
            },
            expected_hidden_quality_gaps=tuple(sorted(
                str(role)
                for role in value.get("expected_hidden_quality_gaps") or []
            )),
            expected_statuses={
                str(role): str(status)
                for role, status in (
                    value.get("expected_statuses") or {}
                ).items()
            },
        )


@dataclass(frozen=True)
class DeckCalibrationResult:
    case_id: str
    total_cards: int
    actual_gap_additions: Mapping[str, int]
    hidden_quality_gaps: Tuple[str, ...]
    role_statuses: Mapping[str, str]
    failures: Tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> Dict:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "total_cards": self.total_cards,
            "actual_gap_additions": dict(self.actual_gap_additions),
            "hidden_quality_gaps": list(self.hidden_quality_gaps),
            "role_statuses": dict(self.role_statuses),
            "failures": list(self.failures),
        }


def load_deck_calibration_cases(path: Path) -> List[DeckCalibrationCase]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        raise CalibrationValidationError(
            "Unsupported deck calibration fixture schema."
        )
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CalibrationValidationError(
            "Deck calibration fixture requires cases."
        )
    cases = [
        DeckCalibrationCase.from_dict(item)
        for item in raw_cases
        if isinstance(item, Mapping)
    ]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise CalibrationValidationError(
            "Deck calibration case ids must be unique."
        )
    return cases


def load_real_deck_validation_status(path: Path) -> Dict:
    """Load the reviewed real-deck gate used by the promotion report."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        raise CalibrationValidationError(
            "Unsupported real-deck validation status schema."
        )
    required_counts = ("deck_count", "strict_passes", "partial", "failed")
    counts = {key: int(payload.get(key, -1)) for key in required_counts}
    if any(value < 0 for value in counts.values()):
        raise CalibrationValidationError(
            "Real-deck validation status requires nonnegative result counts."
        )
    if (
        counts["strict_passes"] + counts["partial"] + counts["failed"]
        != counts["deck_count"]
    ):
        raise CalibrationValidationError(
            "Real-deck validation result counts must equal deck_count."
        )
    report_path = str(payload.get("report", "")).strip()
    validation_date = str(payload.get("validation_date", "")).strip()
    if not report_path or not validation_date:
        raise CalibrationValidationError(
            "Real-deck validation status requires a date and report path."
        )
    return {
        "schema_version": 1,
        "validation_date": validation_date,
        "deck_count": counts["deck_count"],
        "strict_passes": counts["strict_passes"],
        "partial": counts["partial"],
        "failed": counts["failed"],
        "required_strict_passes": int(
            payload.get("required_strict_passes", counts["deck_count"])
        ),
        "passed": bool(payload.get("passed", False)),
        "report": report_path,
    }


def evaluate_deck_calibration_case(
    case: DeckCalibrationCase,
) -> DeckCalibrationResult:
    engine = EnhancedSuggestionEngine(
        scryfall_service=None,
        ranker_mode="legacy",
    )
    engine.deck_role_assessment_mode = "effective"
    stats = engine._calculate_stats(list(case.cards), None, [])
    gaps = engine._identify_gaps(stats, [], [])
    role_quality = stats.get("role_quality", {})
    actual_total = int(stats.get("total_cards", 0))
    actual_gaps = {
        role: int(count)
        for role, count in gaps.get("roles", {}).items()
        if int(count) > 0
    }
    hidden = tuple(sorted(stats.get("hidden_role_quality_gaps", [])))
    statuses = {
        role: str(row.get("status", ""))
        for role, row in role_quality.items()
    }
    expected_gaps = dict(case.expected_gap_additions)
    failures = []
    if actual_total != case.total_cards:
        failures.append(
            f"total_cards {actual_total} does not match {case.total_cards}"
        )
    if actual_gaps != expected_gaps:
        failures.append(
            f"gap additions {actual_gaps} do not match {expected_gaps}"
        )
    if hidden != case.expected_hidden_quality_gaps:
        failures.append(
            f"hidden quality gaps {list(hidden)} do not match "
            f"{list(case.expected_hidden_quality_gaps)}"
        )
    for role, expected_status in case.expected_statuses.items():
        if statuses.get(role) != expected_status:
            failures.append(
                f"{role} status {statuses.get(role)!r} does not match "
                f"{expected_status!r}"
            )
    return DeckCalibrationResult(
        case_id=case.id,
        total_cards=actual_total,
        actual_gap_additions=actual_gaps,
        hidden_quality_gaps=hidden,
        role_statuses=statuses,
        failures=tuple(failures),
    )


def evaluate_deck_calibration(
    cases: Sequence[DeckCalibrationCase],
) -> List[DeckCalibrationResult]:
    return [evaluate_deck_calibration_case(case) for case in cases]


def build_promotion_report(
    benchmark_cases: Sequence[RecommendationBenchmarkCase],
    deck_cases: Sequence[DeckCalibrationCase],
    real_deck_validation: Mapping | None = None,
    include_details: bool = False,
) -> Dict:
    legacy_results = execute_engine_benchmark(
        list(benchmark_cases),
        ranker_mode="legacy",
    )
    v2_results = execute_engine_benchmark(
        list(benchmark_cases),
        ranker_mode="v2",
    )
    deck_results = evaluate_deck_calibration(deck_cases)
    legacy_summary = aggregate_results(legacy_results)
    v2_summary = aggregate_results(v2_results)

    comparisons = [
        _compare_ranker_case(legacy, v2)
        for legacy, v2 in zip(legacy_results, v2_results)
    ]
    regressed_cases = [
        row["case_id"] for row in comparisons if row["regressed"]
    ]
    changed_top_choices = sum(
        1 for row in comparisons if not row["same_top_choice"]
    )
    failed_deck_cases = [
        result.case_id for result in deck_results if not result.passed
    ]

    gates = {
        "legacy_benchmark_passed": bool(legacy_summary.get("passed")),
        "v2_benchmark_passed": bool(v2_summary.get("passed")),
        "deck_calibration_passed": not failed_deck_cases,
        "zero_ranker_regressions": not regressed_cases,
        "v2_ndcg_not_lower": (
            float(v2_summary.get("mean_ndcg_at_k", 0))
            >= float(legacy_summary.get("mean_ndcg_at_k", 0))
        ),
        "zero_v2_hard_rejections": (
            int(v2_summary.get("hard_rejection_count", 0)) == 0
        ),
        "zero_v2_reason_failures": (
            int(v2_summary.get("reason_failure_count", 0)) == 0
        ),
        "real_deck_validation_passed": bool(
            real_deck_validation and real_deck_validation.get("passed")
        ),
    }
    ready = all(gates.values())
    report = {
        "schema_version": 1,
        "recommendation_cases": len(benchmark_cases),
        "deck_calibration_cases": len(deck_cases),
        "legacy": legacy_summary,
        "v2": v2_summary,
        "comparison": {
            "ready_for_controlled_promotion": ready,
            "gates": gates,
            "regressed_case_ids": regressed_cases,
            "changed_top_choices": changed_top_choices,
            "top_choice_agreement": round(
                (len(comparisons) - changed_top_choices) / len(comparisons),
                4,
            ) if comparisons else 0.0,
        },
        "deck_calibration": {
            "passed": not failed_deck_cases,
            "failed_case_ids": failed_deck_cases,
        },
        "real_deck_validation": (
            dict(real_deck_validation)
            if real_deck_validation
            else {
                "passed": False,
                "error": "real-deck validation status was not supplied",
            }
        ),
    }
    if include_details or not ready:
        report["ranker_case_comparisons"] = comparisons
        report["deck_case_results"] = [
            result.as_dict() for result in deck_results
        ]
    return report


def _compare_ranker_case(
    legacy: RecommendationBenchmarkResult,
    v2: RecommendationBenchmarkResult,
) -> Dict:
    ndcg_delta = round(v2.ndcg_at_k - legacy.ndcg_at_k, 4)
    precision_delta = round(v2.precision_at_k - legacy.precision_at_k, 4)
    core_recall_delta = round(
        v2.core_recall_at_k - legacy.core_recall_at_k,
        4,
    )
    regressed = any([
        ndcg_delta < 0,
        precision_delta < 0,
        core_recall_delta < 0,
        len(v2.hard_rejections) > len(legacy.hard_rejections),
        len(v2.reason_failures) > len(legacy.reason_failures),
    ])
    return {
        "case_id": legacy.case_id,
        "legacy_top": list(legacy.top_names),
        "v2_top": list(v2.top_names),
        "same_top_choice": legacy.top_names[:1] == v2.top_names[:1],
        "same_order": legacy.top_names == v2.top_names,
        "ndcg_delta": ndcg_delta,
        "precision_delta": precision_delta,
        "core_recall_delta": core_recall_delta,
        "regressed": regressed,
    }
