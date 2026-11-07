import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


from services.build_intent import (
    BuildIntent,
    migrate_legacy_deck_intent,
    normalize_build_intent,
)


def base_intent(**updates):
    value = {
        "confirmed": True,
        "deck_name": "Meren recursion",
        "starting_point": "commander",
        "commander_name": "Meren of Clan Nel Toth",
        "build_mode": "guided_scaffold",
        "playstyle": "value",
        "target_bracket": 3,
        "budget_mode": "strict",
        "budget_limit_usd": 150,
        "max_card_price_usd": 8,
        "build_shape": "core_shell",
        "collection_mode": "prefer_owned",
        "owned_card_names": ["Sol Ring", "Viscera Seer"],
        "protected_cards": ["Viscera Seer"],
        "intentional_constraints": ["no_fast_mana"],
        "notes": "Creature-heavy recursion with no compact combo finish.",
    }
    value.update(updates)
    return value


def test_build_intent_round_trip_is_stable_and_inspectable():
    first = normalize_build_intent(base_intent())
    second = normalize_build_intent(first["intent"])

    assert first == second
    assert first["schema_version"] == 1
    assert first["intent"]["power_level_min"] == 5
    assert first["intent"]["power_level_max"] == 6
    assert first["mapping"]["playstyle"]["lane_weights"]["engine"] == 1.3
    assert first["mapping"]["budget"]["hard_gate"]
    assert first["mapping"]["build_shape"] == {
        "scope": "engine_and_support_core",
        "maximum_requested_slots": 40,
    }
    assert first["mapping"]["collection"]["owned_card_count"] == 2
    assert first["deck_intent_profile"]["confirmed"]
    assert "permanent_engine" in first["deck_intent_profile"]["strategy_priorities"]
    assert "compact_wins" not in first["deck_intent_profile"]["strategy_priorities"]


def test_power_band_discloses_policy_and_maps_competitive_intent():
    normalized = normalize_build_intent(base_intent(
        target_bracket=5,
        power_level_min=9,
        power_level_max=10,
        budget_mode="unrestricted",
        budget_limit_usd=None,
        max_card_price_usd=None,
        playstyle="combo",
    ))

    assert normalized["mapping"]["power"]["policies"] == {
        "fast_mana": "expected",
        "tutors": "expected",
        "compact_combos": "expected",
        "interaction": "competitive",
    }
    profile = normalized["deck_intent_profile"]
    assert profile["optimization_mode"] == "competitive"
    assert {"high_power", "cedh", "tournament"}.issubset(profile["experience_tags"])


@pytest.mark.parametrize(
    "updates",
    [
        {"deck_name": "   "},
        {"commander_name": None},
        {"playstyle": "custom", "custom_strategy_priorities": []},
        {"target_bracket": 2, "power_level_min": 7},
        {"budget_mode": "strict", "max_card_price_usd": None},
        {"budget_mode": "unrestricted", "budget_limit_usd": 50},
        {"build_shape": "missing_slots"},
        {"collection_mode": "owned_only", "owned_card_names": []},
        {"excluded_cards": ["Viscera Seer"]},
    ],
)
def test_build_intent_rejects_contradictory_choices(updates):
    with pytest.raises(ValidationError):
        BuildIntent.model_validate(base_intent(**updates))


def test_complete_draft_discloses_the_promoted_phase_five_path():
    normalized = normalize_build_intent(base_intent(build_mode="complete_draft"))

    assert normalized["intent"]["build_mode"] == "complete_draft"
    assert normalized["mapping"]["construction"]["enabled"]
    assert normalized["mapping"]["construction"]["availability"] == (
        "phase_5_promoted"
    )


def test_guided_scaffold_enables_only_the_phase_four_bounded_constructor():
    normalized = normalize_build_intent(base_intent(build_mode="guided_scaffold"))

    construction = normalized["mapping"]["construction"]
    assert construction["enabled"] is True
    assert construction["requested_mode"] == "guided_scaffold"
    assert construction["availability"] == "phase_4_scaffold"
    assert construction["next_action"] == "save_intent_and_build_scaffold"
    assert normalized["mapping"]["build_shape"]["maximum_requested_slots"] == 40


def test_legacy_deck_intent_migrates_without_losing_strict_card_cap():
    migrated = migrate_legacy_deck_intent(
        {
            "schema_version": 1,
            "confirmed": True,
            "power_level_min": 6,
            "power_level_max": 6,
            "budget_mode": "strict",
            "max_card_price_usd": 5,
            "strategy_priorities": ["graveyard_recursion"],
            "protected_cards": ["Pet Card"],
        },
        deck_name="Legacy Meren",
        commander_name="Meren of Clan Nel Toth",
        existing_deck_id="deck-1",
    )

    assert migrated["intent"]["starting_point"] == "existing_deck"
    assert migrated["intent"]["existing_deck_id"] == "deck-1"
    assert migrated["intent"]["build_shape"] == "missing_slots"
    assert migrated["intent"]["max_card_price_usd"] == 5
    assert migrated["intent"]["budget_limit_usd"] is None
    assert migrated["deck_intent_profile"]["protected_cards"] == ["Pet Card"]

