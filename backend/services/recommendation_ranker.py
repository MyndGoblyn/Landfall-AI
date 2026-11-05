"""Evidence-first recommendation ranking with bounded, inspectable components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class RankAssessment:
    version: str
    score: float
    components: Mapping[str, float]
    matched_evidence: Tuple[str, ...]
    applied_penalties: Tuple[str, ...]

    def as_dict(self) -> Dict:
        return {
            "version": self.version,
            "score": self.score,
            "components": dict(self.components),
            "matched_evidence": list(self.matched_evidence),
            "applied_penalties": list(self.applied_penalties),
        }


class EvidenceRankerV2:
    """Rank candidates by evidence classes instead of a dominant branch score."""

    VERSION = "evidence-v2"

    PLAN_WEIGHTS = {
        "direct_synergy": 20,
        "commander_theme_match": 22,
        "archetype_need_match": 14,
        "role_gap_overlap": 19,
        "requested_category": 18,
        "commander_theme_overlap": 17,
        "role_gap": 16,
        "needed_role": 14,
        "existing_deck_theme": 11,
        "enabler": 12,
        "payoff": 10,
        "competitive_evidence": 26,
        "compact_win_component": 25,
        "declared_strategy_priority": 21,
    }
    FUNCTION_WEIGHTS = {
        "repeatable_engine": 10,
        "card_flow": 9,
        "protection": 9,
        "interaction": 9,
        "mana_development": 8,
        "sacrifice_outlet": 8,
        "counter_scaling": 8,
        "counter_placement": 7,
        "creature_token_support": 7,
        "board_support": 7,
        "table_control": 7,
        "recursion": 7,
        "card_access": 6,
        "role_value": 6,
        "low_setup_cost": 5,
        "effective_role_gain": 8,
        "reliable_role_source": 7,
        "multi_role_gain": 6,
        "competitive_efficiency_fit": 10,
        "free_interaction": 12,
        "efficient_interaction": 10,
        "compact_tutor": 10,
        "competitive_enabler": 9,
        "competitive_card_advantage": 10,
    }
    CORROBORATION_WEIGHTS = {
        "mechanic_core": 6,
        "mechanic_support": 4,
        "mechanic_match": 3,
        "tutorable_enchantment": 6,
        "typal_density": 5,
        "vanilla_creature_plan": 6,
        "vanilla_creature_density": 5,
        "creature_density": 4,
        "existing_deck_theme": 4,
        "declared_budget_fit": 6,
        "declared_intent_fit": 5,
        "archetype_invariant": 8,
        "declared_package_fit": 8,
        "dependency_target_fit": 8,
        "named_dependency_fit": 8,
        "total_budget_fit": 7,
    }
    PENALTY_WEIGHTS = {
        "wrong_token_type": 60,
        "wrong_counter_context": 60,
        "dead_colorless_mana": 60,
        "wrong_card_type": 50,
        "low_theme_overlap": 24,
        "low_evidence": 20,
        "uncorroborated_mechanic": 14,
        "support_only_mechanic": 10,
        "generic_staple": 9,
        "role_not_current_gap": 8,
        "curve_pressure": 7,
        "high_mana_value": 5,
        "role_saturated": 5,
        "one_shot_effect": 4,
        "low_role_reliability": 16,
        "over_budget_target": 25,
        "over_budget_flexible": 8,
        "competitive_curve_mismatch": 18,
        "off_typal_creature": 24,
        "intent_unconfirmed": 4,
        "permanent_engine_mismatch": 14,
        "total_budget_pressure": 8,
        "total_budget_outlier": 24,
        "implicit_budget_pressure": 18,
        "implicit_budget_outlier": 32,
        "implicit_budget_unpriced": 28,
        "missing_competitive_evidence": 28,
        "high_power_tempo_mismatch": 22,
    }

    def assess(self, recommendation: Mapping) -> RankAssessment:
        evidence_tags = set(recommendation.get("evidence_tags") or [])
        penalty_tags = set(recommendation.get("penalty_tags") or [])

        plan_alignment = max(
            (weight for tag, weight in self.PLAN_WEIGHTS.items() if tag in evidence_tags),
            default=0,
        )
        function_values = sorted(
            (
                weight
                for tag, weight in self.FUNCTION_WEIGHTS.items()
                if tag in evidence_tags
            ),
            reverse=True,
        )
        functional_value = min(18, sum(function_values[:2]))
        corroboration = min(
            8,
            sum(
                weight
                for tag, weight in self.CORROBORATION_WEIGHTS.items()
                if tag in evidence_tags
            ),
        )
        legacy_quality = self._legacy_quality_component(recommendation.get("score"))
        efficiency = self._efficiency_component(recommendation, evidence_tags)
        evidence_density = min(6, len(evidence_tags) * 1.5)
        popularity_prior = self._popularity_component(recommendation.get("_source_rank"))
        penalties = min(
            70,
            sum(self.PENALTY_WEIGHTS.get(tag, 6) for tag in penalty_tags),
        )

        components = {
            "plan_alignment": float(plan_alignment),
            "functional_value": float(functional_value),
            "corroboration": float(corroboration),
            "legacy_quality": legacy_quality,
            "efficiency": efficiency,
            "evidence_density": float(evidence_density),
            "popularity_prior": popularity_prior,
            "penalties": -float(penalties),
        }
        score = max(0.0, min(100.0, sum(components.values())))
        return RankAssessment(
            version=self.VERSION,
            score=round(score, 4),
            components=components,
            matched_evidence=tuple(sorted(evidence_tags)),
            applied_penalties=tuple(sorted(penalty_tags)),
        )

    def score(self, recommendation: Mapping) -> float:
        return self.assess(recommendation).score

    def sort_key(self, recommendation: Mapping, name_field: str = "name") -> tuple:
        return (
            -self.score(recommendation),
            recommendation.get("_synergy_index", recommendation.get("_query_index", 99)),
            recommendation.get("_source_rank", 999),
            recommendation.get(name_field, ""),
        )

    def selection_score(
        self,
        recommendation: Mapping,
        selected: Sequence[Mapping],
        kind: str,
    ) -> float:
        score = self.score(recommendation)
        if kind == "deck":
            role = str(recommendation.get("role_tag", "")).lower()
            same_role = sum(
                1
                for card in selected
                if str(card.get("role_tag", "")).lower() == role
            )
            generic = self._is_generic_without_plan_evidence(recommendation)
            same_generic = sum(
                1
                for card in selected
                if self._is_generic_without_plan_evidence(card)
            )
            portfolio_penalty = same_generic * 10 if generic else 0

            try:
                budget_limit = float(recommendation.get("budget_limit_usd") or 0)
                portfolio_share = float(
                    recommendation.get("budget_portfolio_share") or 0.25
                )
                selected_cost = sum(
                    float(card.get("price") or 0)
                    for card in selected
                )
                candidate_cost = float(recommendation.get("price") or 0)
            except (TypeError, ValueError):
                budget_limit = 0
                portfolio_share = 0.25
                selected_cost = 0
                candidate_cost = 0
            if (
                budget_limit > 0
                and selected_cost + candidate_cost > budget_limit * portfolio_share
            ):
                portfolio_penalty += 22

            competitive = recommendation.get("optimization_mode") == "competitive"
            if competitive and "competitive_evidence" not in set(
                recommendation.get("evidence_tags") or []
            ):
                portfolio_penalty += 26
            return score - same_role * 7 - portfolio_penalty

        job = str(recommendation.get("job", recommendation.get("role", ""))).lower()
        role = str(recommendation.get("role", "")).lower()
        same_job = sum(
            1
            for card in selected
            if str(card.get("job", card.get("role", ""))).lower() == job
        )
        same_role = sum(
            1
            for card in selected
            if str(card.get("role", "")).lower() == role
        )
        return score - same_job * 9 - same_role * 7

    def select(self, candidates: List[Dict], max_cards: int, kind: str) -> List[Dict]:
        name_field = "card_name" if kind == "deck" else "name"
        remaining = sorted(
            candidates,
            key=lambda card: self.sort_key(card, name_field=name_field),
        )
        selected: List[Dict] = []
        while remaining and len(selected) < max_cards:
            eligible = remaining
            if kind == "deck" and len(selected) < 5:
                deferred_budget_tags = {
                    "over_budget_target",
                    "total_budget_outlier",
                    "implicit_budget_pressure",
                    "implicit_budget_outlier",
                    "implicit_budget_unpriced",
                }
                budget_clean = [
                    card for card in eligible
                    if not deferred_budget_tags & set(
                        card.get("penalty_tags") or []
                    )
                ]
                if budget_clean:
                    eligible = budget_clean
                if not selected:
                    plan_specific = [
                        card for card in eligible
                        if not self._is_generic_without_plan_evidence(card)
                    ]
                    if plan_specific:
                        best_overall = max(
                            self.selection_score(card, selected, kind)
                            for card in eligible
                        )
                        best_plan = max(
                            self.selection_score(card, selected, kind)
                            for card in plan_specific
                        )
                        if best_plan >= best_overall - 8:
                            eligible = plan_specific
                generic_selected = sum(
                    1 for card in selected
                    if self._is_generic_without_plan_evidence(card)
                )
                plan_specific = [
                    card for card in eligible
                    if not self._is_generic_without_plan_evidence(card)
                ]
                if generic_selected >= 2 and plan_specific:
                    eligible = plan_specific
            eligible.sort(
                key=lambda card: (
                    -self.selection_score(card, selected, kind),
                    card.get("_synergy_index", card.get("_query_index", 99)),
                    card.get("_source_rank", 999),
                    card.get(name_field, ""),
                )
            )
            choice = eligible[0]
            if kind == "deck" and self.selection_score(choice, selected, kind) < 30:
                break
            remaining.remove(choice)
            selected.append(choice)
        return selected

    @staticmethod
    def _is_generic_without_plan_evidence(recommendation: Mapping) -> bool:
        role = str(recommendation.get("role_tag") or "").lower()
        if role not in {
            "draw", "ramp", "removal", "sweeper", "interaction", "protection",
        }:
            return False
        evidence = set(recommendation.get("evidence_tags") or [])
        return not bool(evidence & {
            "direct_synergy",
            "commander_theme_match",
            "archetype_need_match",
            "existing_deck_theme",
            "declared_package_fit",
            "competitive_evidence",
            "declared_strategy_priority",
        })

    @staticmethod
    def _legacy_quality_component(value) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0
        return round(max(0.0, min(18.0, (score - 60) / 35 * 18)), 4)

    @staticmethod
    def _efficiency_component(recommendation: Mapping, evidence_tags: set) -> float:
        try:
            cmc = float(recommendation.get("cmc") or 0)
        except (TypeError, ValueError):
            cmc = 0
        setup_like = bool(
            evidence_tags
            & {
                "enabler",
                "protection",
                "card_flow",
                "interaction",
                "mana_development",
                "sacrifice_outlet",
            }
        )
        if setup_like:
            if cmc <= 1:
                return 10.0
            if cmc <= 2:
                return 9.0
            if cmc <= 3:
                return 7.0
            if cmc <= 4:
                return 4.0
            if cmc <= 5:
                return 2.0
            return 0.0
        if cmc <= 3:
            return 7.0
        if cmc <= 4:
            return 5.0
        if cmc <= 6:
            return 3.0
        return 2.0

    @staticmethod
    def _popularity_component(value) -> float:
        try:
            rank = int(value)
        except (TypeError, ValueError):
            return 0.0
        if rank <= 1:
            return 4.0
        if rank <= 4:
            return 3.0
        if rank <= 12:
            return 2.0
        if rank <= 30:
            return 1.0
        return 0.0
