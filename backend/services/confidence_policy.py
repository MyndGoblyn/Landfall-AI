"""Versioned, conservative confidence policy for recommendation evidence."""

from __future__ import annotations

from typing import Dict, Mapping


class EvidenceConfidencePolicy:
    """Turn inspectable evidence into a bounded confidence band.

    This value is an evidence-strength score, not a statistical probability of
    user satisfaction.  The policy never raises a lower cap already imposed by
    budget, intent, invariants, or exploratory coverage.
    """

    VERSION = "evidence-confidence-policy-v1"

    COVERAGE_CAPS = {
        "deep": 0.94,
        "partial": 0.88,
        "exploratory": 0.72,
    }

    PENALTIES = {
        "low_role_reliability": 0.22,
        "missing_competitive_evidence": 0.30,
        "implicit_budget_unpriced": 0.18,
        "implicit_budget_outlier": 0.20,
        "total_budget_outlier": 0.18,
        "implicit_budget_pressure": 0.10,
        "total_budget_pressure": 0.08,
        "high_mana_value": 0.06,
        "one_shot_effect": 0.04,
        "off_typal_creature": 0.08,
        "heuristic_signal": 0.08,
    }

    def apply(self, recommendation: Mapping, coverage_level: str) -> Dict:
        result = dict(recommendation)
        evidence = set(result.get("evidence_tags") or [])
        penalties = set(result.get("penalty_tags") or [])
        basis = []
        score = 0.52

        if "competitive_evidence" in evidence:
            score += 0.24
            basis.append("curated competitive function")
        elif "direct_synergy" in evidence:
            score += 0.18
            basis.append("direct commander-plan evidence")

        if "reliable_role_source" in evidence:
            score += 0.14
            basis.append("reliable measured role gain")
        elif "effective_role_gain" in evidence:
            score += 0.08
            basis.append("measured role gain")

        if evidence & {"mechanic_core", "archetype_need_match"}:
            score += 0.07
            basis.append("registry or archetype corroboration")
        if "multi_plan_fit" in evidence:
            score += 0.04
            basis.append("multiple independently matched lanes")
        if "declared_intent_fit" in evidence:
            score += 0.03
            basis.append("declared intent alignment")
        if result.get("fit_tier") in {"Core Fit", "Competitive Evidence"}:
            score += 0.04

        penalty_total = sum(
            amount for tag, amount in self.PENALTIES.items() if tag in penalties
        )
        score -= penalty_total
        if result.get("invariant_warnings"):
            score -= 0.08
            basis.append("deck-structure warning lowers confidence")
        if penalties:
            basis.append(
                "penalties: " + ", ".join(sorted(penalties))
            )

        coverage = str(coverage_level or "partial").casefold()
        score = min(score, self.COVERAGE_CAPS.get(coverage, 0.82))
        existing_value = result.get("confidence")
        try:
            existing_cap = float(existing_value)
        except (TypeError, ValueError):
            existing_cap = {
                "core": 0.95,
                "high": 0.90,
                "support": 0.82,
                "medium": 0.78,
                "alternate": 0.68,
                "exploratory": 0.60,
                "speculative": 0.45,
            }.get(str(existing_value or "").casefold(), 0.50)
        score = round(max(0.25, min(existing_cap, score)), 2)
        result["confidence"] = score
        result["confidence_band"] = (
            "high" if score >= 0.85
            else "moderate" if score >= 0.70
            else "limited" if score >= 0.55
            else "low"
        )
        result["confidence_model"] = self.VERSION
        result["confidence_basis"] = basis or ["bounded deterministic evidence"]
        result["confidence_scope"] = "evidence_strength_not_probability"
        return result
