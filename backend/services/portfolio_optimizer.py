"""Deterministic V3 portfolio selection over evidence-ranked candidates."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Mapping, Sequence, Tuple


class EvidencePortfolioOptimizer:
    """Select a complementary set rather than independent top-scoring cards.

    A bounded beam keeps the implementation deterministic and inexpensive for
    the small candidate pools produced by the planner.  V2 remains available as
    the rollback selector.
    """

    VERSION = "evidence-portfolio-v3"

    def __init__(self, ranker, beam_width: int = 64, candidate_cap: int = 32):
        self.ranker = ranker
        self.beam_width = max(8, int(beam_width))
        self.candidate_cap = max(10, int(candidate_cap))

    def select(self, candidates: List[Dict], max_cards: int, kind: str) -> List[Dict]:
        if max_cards <= 0 or not candidates:
            return []
        name_field = "card_name" if kind == "deck" else "name"
        ordered = sorted(
            candidates,
            key=lambda card: self.ranker.sort_key(card, name_field=name_field),
        )[: self.candidate_cap]
        competitive = any(
            str(card.get("optimization_mode") or "").casefold() == "competitive"
            for card in ordered
        )
        if competitive:
            # In competitive mode repeated interaction is often correct, but
            # every slot still needs curated function evidence.  Filtering at
            # the portfolio boundary protects callers that bypass retrieval's
            # V3 eligibility check.
            ordered = [
                card for card in ordered
                if "competitive_evidence" in set(card.get("evidence_tags") or [])
            ]
        if kind == "deck":
            ordered = [
                card for card in ordered
                if self.ranker.score(card) >= 30
            ]
        if not ordered:
            return []

        # Each state stores candidate indexes in catalog order.  Keeping only
        # the strongest bounded frontier prevents exponential growth.
        states: List[Tuple[int, ...]] = [tuple()]
        for index, _candidate in enumerate(ordered):
            expanded = list(states)
            expanded.extend(
                (*state, index)
                for state in states
                if len(state) < max_cards
            )
            unique = list(dict.fromkeys(expanded))
            unique.sort(key=lambda state: (
                -self._objective([ordered[i] for i in state], kind),
                -len(state),
                tuple(
                    str(ordered[i].get(name_field, "")).casefold()
                    for i in state
                ),
            ))
            states = unique[: self.beam_width]

        eligible = [state for state in states if state]
        if not eligible:
            return []
        best = max(
            eligible,
            key=lambda state: (
                self._objective([ordered[i] for i in state], kind),
                len(state),
                tuple(-i for i in state),
            ),
        )
        selected_pool = [ordered[i] for i in best]
        return self._order_selected(selected_pool, kind, name_field)

    def _objective(self, cards: Sequence[Mapping], kind: str) -> float:
        if not cards:
            return 0.0
        score = sum(self.ranker.score(card) for card in cards)
        roles = Counter(
            str(card.get("role_tag", card.get("role", ""))).casefold()
            for card in cards
        )
        jobs = Counter(
            str(card.get("job", card.get("role_tag", ""))).casefold()
            for card in cards
        )
        lanes = {
            str(lane)
            for card in cards
            for lane in card.get("matched_plan_lanes") or []
            if str(lane)
        }
        primary_lanes = Counter(
            str((card.get("matched_plan_lanes") or [""])[0]).casefold()
            for card in cards
        )
        competitive = any(
            str(card.get("optimization_mode") or "").casefold() == "competitive"
            for card in cards
        )
        if not competitive:
            score += len({role for role in roles if role}) * 4
            score += len(lanes) * 6
        score += min(18.0, sum(
            max(0.0, float(card.get("effective_role_gain") or 0)) * 3
            for card in cards
        ))
        if not competitive:
            score -= sum(max(0, count - 1) * 16 for count in roles.values())
            score -= sum(max(0, count - 1) * 10 for count in jobs.values())
            score -= sum(max(0, count - 2) * 8 for count in primary_lanes.values())
        if kind == "deck":
            generic_count = sum(
                self.ranker._is_generic_without_plan_evidence(card)
                for card in cards
            )
            score -= max(0, generic_count - 2) * 12
        return score

    def _order_selected(
        self,
        selected_pool: Sequence[Dict],
        kind: str,
        name_field: str,
    ) -> List[Dict]:
        remaining = list(selected_pool)
        ordered: List[Dict] = []
        competitive = any(
            str(card.get("optimization_mode") or "").casefold() == "competitive"
            for card in selected_pool
        )
        while remaining:
            def order_score(card: Mapping) -> float:
                score = self.ranker.selection_score(card, ordered, kind)
                role = str(card.get("role_tag", card.get("role", ""))).casefold()
                card_lanes = {
                    str(lane).casefold()
                    for lane in card.get("matched_plan_lanes") or []
                    if str(lane)
                }
                covered_lanes = {
                    str(lane).casefold()
                    for picked in ordered
                    for lane in picked.get("matched_plan_lanes") or []
                    if str(lane)
                }
                same_role = sum(
                    str(picked.get("role_tag", picked.get("role", ""))).casefold()
                    == role
                    for picked in ordered
                )
                if competitive:
                    return score
                repeated_role_penalty = same_role * 18
                if len(ordered) < 5 and same_role >= 2:
                    # Do not let a third copy of the same functional answer
                    # occupy the visible top five when another strong plan
                    # lane survived portfolio selection.
                    repeated_role_penalty += 24
                new_lane_count = len(card_lanes - covered_lanes)
                new_lane_bonus = min(8, new_lane_count * 4)
                fully_redundant_penalty = (
                    6 if card_lanes and not new_lane_count else 0
                )
                return (
                    score
                    - repeated_role_penalty
                    + new_lane_bonus
                    - fully_redundant_penalty
                )

            remaining.sort(key=lambda card: (
                -order_score(card),
                card.get("_synergy_index", card.get("_query_index", 99)),
                card.get("_source_rank", 999),
                str(card.get(name_field, "")),
            ))
            ordered.append(remaining.pop(0))
        return ordered
