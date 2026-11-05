"""Deterministic quality metrics for suggestion-engine benchmark cases.

The benchmark deliberately evaluates recommendation output independently from
the implementation that produced it.  This lets the current engine and future
rankers run against the same labeled candidate pools and regression gates.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


QUALITY_GAINS = {
    "core": 7,
    "strong": 3,
    "situational": 1,
    "weak": 0,
    "reject": 0,
}
RELEVANT_LABELS = frozenset({"core", "strong"})


class BenchmarkValidationError(ValueError):
    """Raised when a recommendation benchmark fixture is malformed."""


@dataclass(frozen=True)
class CandidateJudgment:
    """Expected quality and evidence requirements for one candidate card."""

    name: str
    label: str
    required_evidence_tags: Tuple[str, ...] = ()
    required_reason_fragments: Tuple[str, ...] = ()
    banned_reason_fragments: Tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping) -> "CandidateJudgment":
        name = str(value.get("name", "")).strip()
        label = str(value.get("label", "")).strip().lower()
        if not name:
            raise BenchmarkValidationError("Candidate judgment requires a name.")
        if label not in QUALITY_GAINS:
            raise BenchmarkValidationError(
                f"Candidate {name!r} has unsupported label {label!r}."
            )
        return cls(
            name=name,
            label=label,
            required_evidence_tags=_string_tuple(
                value.get("required_evidence_tags")
            ),
            required_reason_fragments=_string_tuple(
                value.get("required_reason_fragments")
            ),
            banned_reason_fragments=_string_tuple(
                value.get("banned_reason_fragments")
            ),
        )


@dataclass(frozen=True)
class BenchmarkGates:
    """Per-case minimum quality required for a regression-safe result."""

    min_results: int = 1
    min_candidate_recall: float = 1.0
    min_core_recall_at_k: float = 1.0
    min_precision_at_k: float = 1.0
    min_ndcg_at_k: float = 0.9
    max_hard_rejections: int = 0
    max_reason_failures: int = 0

    @classmethod
    def from_dict(cls, value: Optional[Mapping]) -> "BenchmarkGates":
        value = value or {}
        gates = cls(
            min_results=int(value.get("min_results", 1)),
            min_candidate_recall=float(value.get("min_candidate_recall", 1.0)),
            min_core_recall_at_k=float(value.get("min_core_recall_at_k", 1.0)),
            min_precision_at_k=float(value.get("min_precision_at_k", 1.0)),
            min_ndcg_at_k=float(value.get("min_ndcg_at_k", 0.9)),
            max_hard_rejections=int(value.get("max_hard_rejections", 0)),
            max_reason_failures=int(value.get("max_reason_failures", 0)),
        )
        for name in (
            "min_candidate_recall",
            "min_core_recall_at_k",
            "min_precision_at_k",
            "min_ndcg_at_k",
        ):
            metric = getattr(gates, name)
            if not 0 <= metric <= 1:
                raise BenchmarkValidationError(
                    f"Benchmark gate {name} must be between 0 and 1."
                )
        if gates.min_results < 0:
            raise BenchmarkValidationError("min_results cannot be negative.")
        if gates.max_hard_rejections < 0 or gates.max_reason_failures < 0:
            raise BenchmarkValidationError("Maximum failure gates cannot be negative.")
        return gates


@dataclass(frozen=True)
class RecommendationBenchmarkCase:
    """One labeled ranking problem for commander or deck recommendations."""

    id: str
    mode: str
    top_k: int
    judgments: Tuple[CandidateJudgment, ...]
    gates: BenchmarkGates = field(default_factory=BenchmarkGates)
    global_banned_reason_fragments: Tuple[str, ...] = ()
    payload: Mapping = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping) -> "RecommendationBenchmarkCase":
        case_id = str(value.get("id", "")).strip()
        mode = str(value.get("mode", "")).strip().lower()
        top_k = int(value.get("top_k", 5))
        if not case_id:
            raise BenchmarkValidationError("Benchmark case requires an id.")
        if mode not in {"commander", "deck_role"}:
            raise BenchmarkValidationError(
                f"Benchmark case {case_id!r} has unsupported mode {mode!r}."
            )
        if top_k <= 0:
            raise BenchmarkValidationError(
                f"Benchmark case {case_id!r} requires top_k greater than zero."
            )

        raw_judgments = value.get("judgments") or []
        judgments = tuple(
            CandidateJudgment.from_dict(item)
            for item in raw_judgments
            if isinstance(item, Mapping)
        )
        if not judgments:
            raise BenchmarkValidationError(
                f"Benchmark case {case_id!r} requires candidate judgments."
            )
        normalized_names = [item.name.casefold() for item in judgments]
        if len(normalized_names) != len(set(normalized_names)):
            raise BenchmarkValidationError(
                f"Benchmark case {case_id!r} has duplicate candidate names."
            )
        if not any(item.label in RELEVANT_LABELS for item in judgments):
            raise BenchmarkValidationError(
                f"Benchmark case {case_id!r} requires a core or strong candidate."
            )

        reserved = {
            "id",
            "mode",
            "top_k",
            "judgments",
            "gates",
            "global_banned_reason_fragments",
        }
        payload = {key: item for key, item in value.items() if key not in reserved}
        return cls(
            id=case_id,
            mode=mode,
            top_k=top_k,
            judgments=judgments,
            gates=BenchmarkGates.from_dict(value.get("gates")),
            global_banned_reason_fragments=_string_tuple(
                value.get("global_banned_reason_fragments")
            ),
            payload=payload,
        )

    @property
    def judgments_by_name(self) -> Dict[str, CandidateJudgment]:
        return {judgment.name.casefold(): judgment for judgment in self.judgments}


@dataclass(frozen=True)
class RecommendationBenchmarkResult:
    """Metrics and gate failures for one executed benchmark case."""

    case_id: str
    top_names: Tuple[str, ...]
    result_count: int
    candidate_recall: float
    core_recall_at_k: float
    precision_at_k: float
    ndcg_at_k: float
    hard_rejections: Tuple[str, ...]
    reason_failures: Tuple[str, ...]
    unknown_results: Tuple[str, ...]
    gate_failures: Tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.gate_failures

    def as_dict(self) -> Dict:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "top_names": list(self.top_names),
            "result_count": self.result_count,
            "candidate_recall": round(self.candidate_recall, 4),
            "core_recall_at_k": round(self.core_recall_at_k, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "ndcg_at_k": round(self.ndcg_at_k, 4),
            "hard_rejections": list(self.hard_rejections),
            "reason_failures": list(self.reason_failures),
            "unknown_results": list(self.unknown_results),
            "gate_failures": list(self.gate_failures),
        }


def load_benchmark_cases(path: Path) -> List[RecommendationBenchmarkCase]:
    """Load and validate a versioned recommendation benchmark fixture."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise BenchmarkValidationError("Benchmark fixture must be a JSON object.")
    if payload.get("schema_version") != 1:
        raise BenchmarkValidationError("Unsupported benchmark schema version.")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise BenchmarkValidationError("Benchmark fixture requires a non-empty cases list.")
    global_banned = payload.get("global_banned_reason_fragments") or []
    if not isinstance(global_banned, list):
        raise BenchmarkValidationError(
            "global_banned_reason_fragments must be an array."
        )
    cases = []
    for item in raw_cases:
        if not isinstance(item, Mapping):
            continue
        case_value = dict(item)
        inherited_banned = [
            *global_banned,
            *(case_value.get("global_banned_reason_fragments") or []),
        ]
        case_value["global_banned_reason_fragments"] = inherited_banned
        cases.append(RecommendationBenchmarkCase.from_dict(case_value))
    if len(cases) != len(raw_cases):
        raise BenchmarkValidationError("Every benchmark case must be a JSON object.")
    case_ids = [case.id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise BenchmarkValidationError("Benchmark case ids must be unique.")
    return cases


def evaluate_recommendations(
    case: RecommendationBenchmarkCase,
    ranked_recommendations: Sequence[Mapping],
    retrieved_names: Optional[Iterable[str]] = None,
) -> RecommendationBenchmarkResult:
    """Evaluate ranked output against one case's relevance and reason labels."""
    judgments = case.judgments_by_name
    top = list(ranked_recommendations[: case.top_k])
    top_names = [_recommendation_name(item) for item in top]
    retrieved = {
        str(name).strip().casefold()
        for name in (retrieved_names if retrieved_names is not None else top_names)
        if str(name).strip()
    }

    desired_candidates = {
        item.name.casefold()
        for item in case.judgments
        if item.label in RELEVANT_LABELS
    }
    core_candidates = {
        item.name.casefold()
        for item in case.judgments
        if item.label == "core"
    }
    candidate_recall = _recall(desired_candidates, retrieved)
    selected_names = {name.casefold() for name in top_names if name}
    core_recall = _recall(core_candidates, selected_names)

    relevant_count = sum(
        1
        for name in top_names
        if judgments.get(name.casefold())
        and judgments[name.casefold()].label in RELEVANT_LABELS
    )
    precision = relevant_count / len(top) if top else 0.0
    ndcg = _ndcg_at_k(top_names, judgments, case.top_k)

    hard_rejections = tuple(
        name
        for name in top_names
        if judgments.get(name.casefold())
        and judgments[name.casefold()].label == "reject"
    )
    unknown_results = tuple(
        name for name in top_names if name.casefold() not in judgments
    )
    reason_failures = tuple(
        failure
        for recommendation in top
        for failure in _reason_failures(case, recommendation, judgments)
    )

    gates = case.gates
    gate_failures: List[str] = []
    if len(top) < gates.min_results:
        gate_failures.append(
            f"result_count {len(top)} is below {gates.min_results}"
        )
    if candidate_recall < gates.min_candidate_recall:
        gate_failures.append(
            f"candidate_recall {candidate_recall:.3f} is below "
            f"{gates.min_candidate_recall:.3f}"
        )
    if core_recall < gates.min_core_recall_at_k:
        gate_failures.append(
            f"core_recall_at_k {core_recall:.3f} is below "
            f"{gates.min_core_recall_at_k:.3f}"
        )
    if precision < gates.min_precision_at_k:
        gate_failures.append(
            f"precision_at_k {precision:.3f} is below "
            f"{gates.min_precision_at_k:.3f}"
        )
    if ndcg < gates.min_ndcg_at_k:
        gate_failures.append(
            f"ndcg_at_k {ndcg:.3f} is below {gates.min_ndcg_at_k:.3f}"
        )
    if len(hard_rejections) > gates.max_hard_rejections:
        gate_failures.append(
            f"hard_rejections {len(hard_rejections)} exceeds "
            f"{gates.max_hard_rejections}"
        )
    if len(reason_failures) > gates.max_reason_failures:
        gate_failures.append(
            f"reason_failures {len(reason_failures)} exceeds "
            f"{gates.max_reason_failures}"
        )
    if unknown_results:
        gate_failures.append(
            f"unlabeled benchmark results: {', '.join(unknown_results)}"
        )

    return RecommendationBenchmarkResult(
        case_id=case.id,
        top_names=tuple(top_names),
        result_count=len(top),
        candidate_recall=candidate_recall,
        core_recall_at_k=core_recall,
        precision_at_k=precision,
        ndcg_at_k=ndcg,
        hard_rejections=hard_rejections,
        reason_failures=reason_failures,
        unknown_results=unknown_results,
        gate_failures=tuple(gate_failures),
    )


def aggregate_results(results: Sequence[RecommendationBenchmarkResult]) -> Dict:
    """Return a compact CI/reporting summary for multiple benchmark cases."""
    if not results:
        return {
            "case_count": 0,
            "passed": False,
            "passed_cases": 0,
            "failed_cases": 0,
        }

    def average(field_name: str) -> float:
        return round(
            sum(float(getattr(result, field_name)) for result in results)
            / len(results),
            4,
        )

    failed = [result.case_id for result in results if not result.passed]
    return {
        "case_count": len(results),
        "passed": not failed,
        "passed_cases": len(results) - len(failed),
        "failed_cases": len(failed),
        "failed_case_ids": failed,
        "mean_candidate_recall": average("candidate_recall"),
        "mean_core_recall_at_k": average("core_recall_at_k"),
        "mean_precision_at_k": average("precision_at_k"),
        "mean_ndcg_at_k": average("ndcg_at_k"),
        "hard_rejection_count": sum(len(result.hard_rejections) for result in results),
        "reason_failure_count": sum(len(result.reason_failures) for result in results),
    }


def _string_tuple(value) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise BenchmarkValidationError("Benchmark string collections must be arrays.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _recommendation_name(recommendation: Mapping) -> str:
    return str(
        recommendation.get("name") or recommendation.get("card_name") or ""
    ).strip()


def _recall(expected: set, actual: set) -> float:
    if not expected:
        return 1.0
    return len(expected & actual) / len(expected)


def _ndcg_at_k(
    names: Sequence[str],
    judgments: Mapping[str, CandidateJudgment],
    top_k: int,
) -> float:
    gains = [
        QUALITY_GAINS.get(judgments[name.casefold()].label, 0)
        if name.casefold() in judgments
        else 0
        for name in names[:top_k]
    ]
    ideal = sorted(
        (QUALITY_GAINS[item.label] for item in judgments.values()),
        reverse=True,
    )[:top_k]
    actual_dcg = _discounted_gain(gains)
    ideal_dcg = _discounted_gain(ideal)
    return actual_dcg / ideal_dcg if ideal_dcg else 1.0


def _discounted_gain(gains: Sequence[int]) -> float:
    return sum(
        gain / math.log2(index + 2)
        for index, gain in enumerate(gains)
    )


def _reason_failures(
    case: RecommendationBenchmarkCase,
    recommendation: Mapping,
    judgments: Mapping[str, CandidateJudgment],
) -> List[str]:
    name = _recommendation_name(recommendation)
    judgment = judgments.get(name.casefold())
    if not judgment:
        return []

    failures = []
    evidence_tags = {
        str(tag).strip().casefold()
        for tag in recommendation.get("evidence_tags", []) or []
    }
    reason = str(recommendation.get("reason", ""))
    reason_lower = reason.casefold()

    for tag in judgment.required_evidence_tags:
        if tag.casefold() not in evidence_tags:
            failures.append(f"{name}: missing evidence tag {tag}")
    for fragment in judgment.required_reason_fragments:
        if fragment.casefold() not in reason_lower:
            failures.append(f"{name}: missing reason fragment {fragment!r}")
    banned = (
        *case.global_banned_reason_fragments,
        *judgment.banned_reason_fragments,
    )
    for fragment in banned:
        if fragment.casefold() in reason_lower:
            failures.append(f"{name}: banned reason fragment {fragment!r}")
    return failures
