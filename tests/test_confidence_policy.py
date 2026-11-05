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
