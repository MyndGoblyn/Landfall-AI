import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_input_assessment import (
    apply_recommendation_restraint,
    assess_deck_input,
)


def card(name, qty=1, type_line="Creature"):
    return {"name": name, "qty": qty, "type_line": type_line}


def issue_codes(assessment):
    return {issue["code"] for issue in assessment["issues"]}


def test_complete_normal_deck_is_ready():
    deck = {
        "commander": "Test Commander",
        "cards": [card("Forest", 35, "Basic Land — Forest")] + [
            card(f"Spell {index}") for index in range(64)
        ],
    }

    assessment = assess_deck_input(deck)

    assert assessment["status"] == "ready"
    assert assessment["mainboard_cards"] == 99
    assert assessment["submitted_cards"] == 100
    assert assessment["recommendations_allowed"] is True


def test_eighteen_land_deck_gets_warning_without_assuming_it_is_invalid():
    deck = {
        "commander": "Grist, the Hunger Tide",
        "cards": [card("Forest", 18, "Basic Land — Forest")] + [
            card(f"Spell {index}") for index in range(81)
        ],
    }

    assessment = assess_deck_input(deck)

    assert assessment["analysis_allowed"] is True
    assert assessment["recommendations_allowed"] is True
    assert "severe_mana_base_risk" in issue_codes(assessment)


def test_extreme_repetition_pauses_blind_optimization():
    deck = {
        "commander": "Plargg",
        "cards": [card("Mountain", 97, "Basic Land — Mountain"), card("Spell A"), card("Spell B")],
    }

    assessment = assess_deck_input(deck)
    result = apply_recommendation_restraint(
        {
            "suggestions_add": [{"card_name": "Generic Upgrade"}],
            "suggestions_cut": [{"card_name": "Mountain"}],
            "swap_pairs": [{"add": {}, "cut": {}}],
            "coverage_notes": None,
        },
        assessment,
    )

    assert assessment["analysis_allowed"] is True
    assert assessment["recommendations_allowed"] is False
    assert "intentional_constraint_confirmation" in issue_codes(assessment)
    assert result["suggestions_add"] == []
    assert result["suggestions_cut"] == []
    assert result["swap_pairs"] == []


def test_incomplete_deck_fills_open_slots_without_cuts():
    deck = {
        "commander": "Test Commander",
        "cards": [card("Forest", 35, "Basic Land — Forest")] + [
            card(f"Spell {index}") for index in range(63)
        ],
    }
    assessment = assess_deck_input(deck)
    result = apply_recommendation_restraint(
        {
            "suggestions_add": [
                {"card_name": "Best Addition"},
                {"card_name": "Second Addition"},
            ],
            "suggestions_cut": [{"card_name": "Existing Card"}],
            "swap_pairs": [],
        },
        assessment,
    )

    assert assessment["missing_cards"] == 1
    assert result["suggestions_add"] == [{"card_name": "Best Addition"}]
    assert result["suggestions_cut"] == []
    assert result["swap_pairs"][0]["cut"] is None


def test_partial_or_commanderless_decks_block_analysis_with_exact_counts():
    partial = assess_deck_input({
        "commander": "Lathril",
        "cards": [card("Spell", 23)],
    })
    commanderless = assess_deck_input({
        "cards": [card("Spell", 98)],
    })

    assert partial["status"] == "blocked"
    assert partial["mainboard_cards"] == 23
    assert "severely_incomplete" in issue_codes(partial)
    assert commanderless["status"] == "blocked"
    assert "commander_missing" in issue_codes(commanderless)
