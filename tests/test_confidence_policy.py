import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.confidence_policy import EvidenceConfidencePolicy


def test_confidence_policy_never_raises_existing_policy_cap():
    result = EvidenceConfidencePolicy().apply(
        {
            "confidence": 0.68,
            "fit_tier": "Core Fit",
            "evidence_tags": [
                "direct_synergy",
                "reliable_role_source",
                "mechanic_core",
                "multi_plan_fit",
            ],
            "penalty_tags": [],
        },
        "deep",
    )

    assert result["confidence"] == 0.68
    assert result["confidence_scope"] == "evidence_strength_not_probability"


def test_low_reliability_and_exploratory_coverage_lower_confidence():
    result = EvidenceConfidencePolicy().apply(
        {
            "confidence": 0.95,
            "fit_tier": "Role Fit",
            "evidence_tags": ["effective_role_gain"],
            "penalty_tags": ["low_role_reliability"],
        },
        "exploratory",
    )

    assert result["confidence"] < 0.55
    assert result["confidence_band"] == "low"


def test_reviewed_commander_plan_corroborates_but_does_not_replace_card_evidence():
    policy = EvidenceConfidencePolicy()
    unreviewed = policy.apply(
        {
            "confidence": 0.95,
            "fit_tier": "Role Fit",
            "evidence_tags": ["mechanic_core", "declared_intent_fit"],
            "penalty_tags": [],
        },
        "deep",
    )
    reviewed = policy.apply(
        {
            "confidence": 0.95,
            "fit_tier": "Role Fit",
            "evidence_tags": [
                "mechanic_core",
                "declared_intent_fit",
                "reviewed_commander_plan",
            ],
            "penalty_tags": [],
        },
        "deep",
    )

    assert unreviewed["confidence"] == 0.62
    assert reviewed["confidence"] == 0.70
    assert "exact reviewed commander-plan corroboration" in reviewed["confidence_basis"]


def test_construction_evidence_raises_only_the_supported_measured_case():
    result = EvidenceConfidencePolicy().apply(
        {
            "confidence": 0.82,
            "fit_tier": "Role Fit",
            "evidence_tags": [
                "effective_role_gain",
                "declared_intent_fit",
                "construction_role_gap_fit",
                "construction_invariant_fit",
            ],
            "penalty_tags": [],
        },
        "partial",
    )

    assert result["confidence"] == 0.73
    assert "measured construction role deficiency" in result["confidence_basis"]
    assert "verified positive deck-invariant fit" in result["confidence_basis"]
