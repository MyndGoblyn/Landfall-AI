"""Quality-aware deck role coverage for Commander recommendations.

Raw card counts are useful diagnostics, but they overstate coverage when a card
only performs a job conditionally, inefficiently, or as a minor rider.  This
module assigns every detected role source a conservative 0..1 contribution so
the suggestion engine can reason about the reliability of the current deck and
the actual gain from a proposed addition.
"""

from __future__ import annotations

import math
import re
from typing import Callable, Dict, Iterable, List, Mapping, Sequence


class DeckRoleAssessor:
    """Turn raw role detections into bounded, explainable coverage."""

    VERSION = "deck-role-v1"

    def __init__(self, role_targets: Mapping[str, Sequence[int]]):
        self.role_targets = {
            role: (int(target[0]), int(target[1]))
            for role, target in role_targets.items()
        }

    def assess(
        self,
        cards: Iterable[Dict],
        detect_roles: Callable[[str, str, str], List[str]],
    ) -> Dict:
        role_rows = {
            role: {
                "raw_count": 0,
                "effective_count": 0.0,
                "high_quality_count": 0,
                "conditional_count": 0,
                "target_min": target[0],
                "target_max": target[1],
                "contributors": [],
            }
            for role, target in self.role_targets.items()
        }

        for card in cards:
            oracle_text = str(card.get("oracle_text", "")).lower()
            type_line = str(card.get("type_line", "")).lower()
            name = str(card.get("name", ""))
            quantity = self._quantity(card.get("qty", 1))
            roles = detect_roles(oracle_text, type_line, name)
            for role in roles:
                if role not in role_rows:
                    continue
                contribution = self.card_role_contribution(card, role)
                if contribution <= 0:
                    continue
                row = role_rows[role]
                row["raw_count"] += quantity
                row["effective_count"] += contribution * quantity
                if contribution >= 0.8:
                    row["high_quality_count"] += quantity
                if contribution < 0.65:
                    row["conditional_count"] += quantity
                row["contributors"].append({
                    "name": name,
                    "quantity": quantity,
                    "contribution": contribution,
                    "effective_total": round(contribution * quantity, 2),
                    "quality": self._quality_band(contribution),
                })

        total_effective_gap = 0
        hidden_quality_gaps = []
        for role, row in role_rows.items():
            row["effective_count"] = round(row["effective_count"], 2)
            deficit = max(0.0, row["target_min"] - row["effective_count"])
            row["effective_gap"] = round(deficit, 2)
            row["recommended_additions"] = int(math.ceil(deficit - 1e-9))
            if deficit > 0:
                row["status"] = "quality_gap" if row["raw_count"] >= row["target_min"] else "gap"
            elif row["effective_count"] > row["target_max"]:
                row["status"] = "saturated"
            else:
                row["status"] = "healthy"
            row["contributors"].sort(
                key=lambda item: (-item["contribution"], item["name"].lower())
            )
            if row["status"] == "quality_gap":
                hidden_quality_gaps.append(role)
            total_effective_gap += row["effective_gap"]

        return {
            "version": self.VERSION,
            "roles": role_rows,
            "total_effective_gap": round(total_effective_gap, 2),
            "hidden_quality_gaps": hidden_quality_gaps,
        }

    def card_role_contribution(self, card: Mapping, role: str) -> float:
        """Return the effective fraction of one dependable role source."""
        text = str(card.get("oracle_text", "")).lower()
        type_line = str(card.get("type_line", "")).lower()
        cmc = self._number(card.get("cmc", 0))
        weight = 0.85

        if cmc <= 2:
            weight += 0.1
        elif cmc == 5:
            weight -= 0.12
        elif cmc >= 6:
            weight -= 0.25

        if any(phrase in text for phrase in [
            "combat damage to a player",
            "combat damage to an opponent",
            "when this creature dies",
            "when it dies",
        ]):
            weight -= 0.2
        if any(phrase in text for phrase in [
            "only if",
            "activate only",
            "if you control your commander",
            "during your turn",
        ]):
            weight -= 0.15

        if role == "draw":
            weight = self._draw_weight(text, type_line, cmc, weight)
        elif role == "ramp":
            weight = self._ramp_weight(text, type_line, cmc, weight)
        elif role == "removal":
            weight = self._removal_weight(text, cmc, weight)
        elif role == "sweeper":
            weight = self._sweeper_weight(text, cmc, weight)
        elif role == "interaction":
            weight = self._interaction_weight(text, cmc, weight)
        elif role == "protection":
            weight = self._protection_weight(text, cmc, weight)

        return round(max(0.1, min(1.0, weight)), 2)

    def marginal_utility(
        self,
        card: Mapping,
        assessment: Mapping,
        detected_roles: Sequence[str],
        primary_role: str,
    ) -> Dict:
        """Measure how much reliable coverage a candidate adds to this list."""
        roles = assessment.get("roles", {})
        contributions = {
            role: self.card_role_contribution(card, role)
            for role in detected_roles
            if role in self.role_targets
        }
        primary_gain = contributions.get(primary_role, 0.0)
        gap_roles = [
            role for role, gain in contributions.items()
            if gain > 0 and float(roles.get(role, {}).get("effective_gap", 0)) > 0
        ]
        covered_gap = sum(
            min(gain, float(roles.get(role, {}).get("effective_gap", 0)))
            for role, gain in contributions.items()
        )
        primary_row = roles.get(primary_role, {})
        before = float(primary_row.get("effective_count", 0))
        after = before + primary_gain
        target_min = int(primary_row.get(
            "target_min",
            self.role_targets.get(primary_role, (0, 0))[0],
        ))
        need_pressure = (
            min(1.0, float(primary_row.get("effective_gap", 0)) / max(target_min, 1))
            if target_min else 0.0
        )
        utility = primary_gain * 52 + covered_gap * 20 + need_pressure * 20
        if len(gap_roles) > 1:
            utility += min(8, (len(gap_roles) - 1) * 4)
        if primary_role in roles and primary_row.get("status") == "saturated":
            utility -= 24

        return {
            "score": round(max(0.0, min(100.0, utility)), 1),
            "primary_role": primary_role,
            "primary_gain": round(primary_gain, 2),
            "role_gains": contributions,
            "gap_roles": gap_roles,
            "covered_gap": round(covered_gap, 2),
            "coverage_before": round(before, 2),
            "coverage_after": round(after, 2),
            "target_min": target_min,
        }

    @staticmethod
    def _draw_weight(text: str, type_line: str, cmc: float, weight: float) -> float:
        repeatable = any(phrase in text for phrase in [
            "at the beginning of",
            "whenever",
            "each time",
        ]) or (":" in text and "draw" in text)
        if repeatable:
            weight += 0.08
        draw_match = re.search(r"\bdraw (a|one|two|three|four|x|that many) cards?\b", text)
        amount = draw_match.group(1) if draw_match else "a"
        if amount in {"two", "three", "four", "x", "that many"}:
            weight += 0.08
        elif not repeatable:
            weight -= 0.22
        if "then discard" in text or "discard a card" in text and "draw" in text:
            weight -= 0.12
        if "each player draws" in text or "target opponent draws" in text:
            weight -= 0.28
        if "creature" in type_line and "when" in text and "draw a card" in text:
            weight -= 0.1
        if cmc >= 6:
            weight -= 0.08
        return weight

    @staticmethod
    def _ramp_weight(text: str, type_line: str, cmc: float, weight: float) -> float:
        land_term = any(term in text for term in [
            "land", "plains", "island", "swamp", "mountain", "forest", "wastes",
        ])
        puts_land_in_play = (
            "search your library" in text
            and land_term
            and "onto the battlefield" in text
        )
        land_to_hand_only = (
            "search your library" in text
            and land_term
            and "into your hand" in text
            and "onto the battlefield" not in text
        )
        mana_source = "add " in text and ("{" in text or "mana" in text)
        treasure = "treasure token" in text
        if puts_land_in_play or mana_source:
            weight += 0.05
        if land_to_hand_only:
            weight -= 0.45
        if treasure and not mana_source and not puts_land_in_play:
            weight -= 0.22
        if "sacrifice" in text and treasure:
            weight -= 0.08
        if cmc >= 4:
            weight -= 0.18
        if "land" in type_line:
            weight -= 0.35
        return weight

    @staticmethod
    def _removal_weight(text: str, cmc: float, weight: float) -> float:
        if any(phrase in text for phrase in ["target permanent", "target nonland permanent"]):
            weight += 0.08
        elif "target creature" in text:
            weight -= 0.02
        elif "target artifact" in text or "target enchantment" in text:
            weight -= 0.18
        if any(phrase in text for phrase in [
            "with mana value",
            "power 3 or less",
            "power 4 or greater",
            "attacking creature",
            "tapped creature",
        ]):
            weight -= 0.18
        if cmc >= 5:
            weight -= 0.12
        return weight

    @staticmethod
    def _sweeper_weight(text: str, cmc: float, weight: float) -> float:
        if "all permanents" in text or "all nonland permanents" in text:
            weight += 0.08
        elif "all creatures" in text:
            weight += 0.04
        if "all creatures of the chosen type" in text or "all creatures with" in text:
            weight -= 0.22
        if "-x/-x" in text:
            weight -= 0.08
        if cmc >= 7:
            weight -= 0.12
        return weight

    @staticmethod
    def _interaction_weight(text: str, cmc: float, weight: float) -> float:
        if "counter target spell" in text:
            weight += 0.05
        elif "counter target" in text and "ability" in text:
            weight -= 0.08
        else:
            weight -= 0.2
        if "unless its controller pays" in text or "unless that player pays" in text:
            weight -= 0.16
        if cmc >= 4:
            weight -= 0.12
        return weight

    @staticmethod
    def _protection_weight(text: str, cmc: float, weight: float) -> float:
        protects_others = any(phrase in text for phrase in [
            "target creature gains",
            "target permanent gains",
            "permanents you control gain",
            "creatures you control gain",
            "other creatures you control",
            "phase out",
        ])
        self_only = any(phrase in text for phrase in [
            "this creature has hexproof",
            "this creature has indestructible",
        ]) or (
            not protects_others
            and any(term in text for term in ["ward", "hexproof", "indestructible"])
        )
        if protects_others:
            weight += 0.08
        elif self_only:
            weight -= 0.5
        if cmc >= 4:
            weight -= 0.12
        return weight

    @staticmethod
    def _quantity(value) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _number(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _quality_band(contribution: float) -> str:
        if contribution >= 0.8:
            return "reliable"
        if contribution >= 0.6:
            return "conditional"
        return "incidental"
