"""Quantity-aware input validation and recommendation restraint for Commander decks."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Mapping


EXPECTED_MAINBOARD_CARDS = 99
MINIMUM_ANALYZABLE_CARDS = 50


def assess_deck_input(deck: Mapping) -> Dict:
    """Return user-facing diagnostics without treating unusual intent as an error."""
    cards = [card for card in deck.get("cards", []) if isinstance(card, Mapping)]
    quantities = [_safe_quantity(card.get("qty", 1)) for card in cards]
    mainboard_cards = sum(quantities)
    commander = str(deck.get("commander") or "").strip() or None
    submitted_cards = mainboard_cards + (1 if commander else 0)
    land_cards = sum(
        qty
        for card, qty in zip(cards, quantities)
        if "land" in str(card.get("type_line") or "").casefold()
    )
    name_counts = Counter()
    for card, qty in zip(cards, quantities):
        name = str(card.get("name") or "").strip()
        if name:
            name_counts[name] += qty
    largest_stack_name, largest_stack = (
        name_counts.most_common(1)[0] if name_counts else (None, 0)
    )
    largest_stack_share = (
        largest_stack / mainboard_cards if mainboard_cards else 0.0
    )

    issues: List[Dict] = []
    analysis_allowed = True
    recommendations_allowed = True

    if not commander:
        analysis_allowed = False
        recommendations_allowed = False
        issues.append(_issue(
            "commander_missing",
            "error",
            "No commander was identified. Mark the commander in the source list before analysis.",
        ))

    missing_cards = max(EXPECTED_MAINBOARD_CARDS - mainboard_cards, 0)
    excess_cards = max(mainboard_cards - EXPECTED_MAINBOARD_CARDS, 0)
    if mainboard_cards < MINIMUM_ANALYZABLE_CARDS:
        analysis_allowed = False
        recommendations_allowed = False
        issues.append(_issue(
            "severely_incomplete",
            "error",
            (
                f"Only {mainboard_cards} main-deck cards were imported; "
                f"{missing_cards} more are needed for a 99-card Commander main deck."
            ),
        ))
    elif missing_cards:
        issues.append(_issue(
            "incomplete_mainboard",
            "warning",
            (
                f"The main deck has {mainboard_cards} cards and is missing "
                f"{missing_cards}. Recommendations will fill open slots without proposing cuts."
            ),
        ))
    elif excess_cards:
        issues.append(_issue(
            "oversized_mainboard",
            "warning",
            (
                f"The main deck has {mainboard_cards} cards, {excess_cards} above the "
                "Commander target. Review cuts before adding cards."
            ),
        ))

    if mainboard_cards >= MINIMUM_ANALYZABLE_CARDS and land_cards <= 20:
        issues.append(_issue(
            "severe_mana_base_risk",
            "warning",
            (
                f"Only {land_cards} lands were detected. This may be intentional, but the deck "
                "needs unusually dense fast mana or a very low curve to function consistently."
            ),
        ))
    elif mainboard_cards >= MINIMUM_ANALYZABLE_CARDS and land_cards <= 27:
        issues.append(_issue(
            "low_land_count",
            "notice",
            (
                f"The deck has {land_cards} lands. Low-curve and competitive lists can support "
                "this, so the count is flagged for review rather than treated as automatically wrong."
            ),
        ))

    extreme_repetition = (
        mainboard_cards >= 90 and
        (len(name_counts) <= 10 or largest_stack_share >= 0.70)
    )
    if extreme_repetition:
        recommendations_allowed = False
        issues.append(_issue(
            "intentional_constraint_confirmation",
            "warning",
            (
                f"{largest_stack_name or 'One card'} occupies {largest_stack} of "
                f"{mainboard_cards} main-deck slots. Automated upgrades are paused because this "
                "looks like an intentional construction constraint or joke deck."
            ),
        ))

    if not analysis_allowed:
        status = "blocked"
    elif not recommendations_allowed or any(
        issue["severity"] == "warning" for issue in issues
    ):
        status = "review"
    else:
        status = "ready"

    return {
        "status": status,
        "analysis_allowed": analysis_allowed,
        "recommendations_allowed": recommendations_allowed,
        "commander_identified": bool(commander),
        "mainboard_cards": mainboard_cards,
        "submitted_cards": submitted_cards,
        "expected_mainboard_cards": EXPECTED_MAINBOARD_CARDS,
        "missing_cards": missing_cards,
        "excess_cards": excess_cards,
        "unique_cards": len(name_counts),
        "land_cards": land_cards,
        "largest_stack": {
            "card_name": largest_stack_name,
            "quantity": largest_stack,
            "share": round(largest_stack_share, 4),
        },
        "issues": issues,
    }


def apply_recommendation_restraint(result: Dict, assessment: Mapping) -> Dict:
    """Keep analysis honest for incomplete or intentionally constrained inputs."""
    result["input_assessment"] = dict(assessment)
    mainboard_cards = int(assessment.get("mainboard_cards", 0))
    missing_cards = int(assessment.get("missing_cards", 0))

    if not assessment.get("recommendations_allowed", True):
        result["suggestions_add"] = []
        result["suggestions_cut"] = []
        result["swap_pairs"] = []
        note = (
            "Automated upgrades were paused until the deck's unusual construction "
            "constraint is confirmed."
        )
        result["coverage_notes"] = _append_note(result.get("coverage_notes"), note)
    elif mainboard_cards < EXPECTED_MAINBOARD_CARDS:
        additions = list(result.get("suggestions_add") or [])[:missing_cards]
        result["suggestions_add"] = additions
        result["suggestions_cut"] = []
        result["swap_pairs"] = [
            {
                "add": addition,
                "cut": None,
                "reason": "This fills an open deck slot; no cut is needed yet.",
            }
            for addition in additions
        ]
    return result


def blocking_message(assessment: Mapping) -> str:
    errors = [
        str(issue.get("message"))
        for issue in assessment.get("issues", [])
        if issue.get("severity") == "error"
    ]
    return " ".join(errors) or "This deck is not ready for analysis."


def _safe_quantity(value) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _issue(code: str, severity: str, message: str) -> Dict:
    return {"code": code, "severity": severity, "message": message}


def _append_note(existing, note: str) -> str:
    if not existing:
        return note
    return f"{existing} {note}"
