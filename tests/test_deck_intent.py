import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_intent import (
    DeckIntentProfile,
    apply_intent_to_cuts,
    apply_intent_to_suggestion,
    intent_summary,
    is_cut_protected,
    normalize_intent_profile,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def suggestion(name="Candidate", price=2.0, cmc=2, role="draw"):
    return {
        "card_name": name,
        "price": price,
        "cmc": cmc,
        "role_tag": role,
        "score": 88,
        "confidence": 0.86,
        "reason": "It fills a measured deck need.",
    }


def card(name="Candidate", oracle_text="Draw two cards.", cmc=2):
    return {
        "name": name,
        "oracle_text": oracle_text,
        "type_line": "Instant",
        "cmc": cmc,
    }


def test_default_intent_is_conservative_and_unconfirmed():
    profile = normalize_intent_profile()

    assert not profile["confirmed"]
    assert profile["optimization_mode"] == "preserve"
    assert intent_summary(profile)["recommendation_posture"] == (
        "conservative-unconfirmed"
    )


def test_intent_validates_power_budget_and_card_list_conflicts():
    with pytest.raises(ValidationError):
        DeckIntentProfile(power_level_min=8, power_level_max=6)
    with pytest.raises(ValidationError):
        DeckIntentProfile(budget_mode="strict")
    with pytest.raises(ValidationError):
        DeckIntentProfile(
            protected_cards=["Pet Card"],
            excluded_cards=["pet card"],
        )


def test_protected_packages_are_cut_protected_case_insensitively():
    profile = normalize_intent_profile({
        "confirmed": True,
        "protected_cards": ["Yuriko, the Tiger's Shadow"],
        "protected_packages": [
            {"name": "Doomsday line", "cards": ["Doomsday", "Thassa's Oracle"]},
        ],
    })

    assert is_cut_protected("DOOMSDAY", profile)
    assert is_cut_protected("Yuriko, the Tiger's Shadow", profile)
    assert not is_cut_protected("Island", profile)


def test_strict_budget_rejects_over_cap_and_unpriced_candidates():
    profile = normalize_intent_profile({
        "confirmed": True,
        "budget_mode": "strict",
        "max_card_price_usd": 5,
    })

    assert apply_intent_to_suggestion(
        suggestion(price=8), card(), profile
    ) is None
    assert apply_intent_to_suggestion(
        suggestion(price=None), card(), profile
    ) is None
    accepted = apply_intent_to_suggestion(
        suggestion(price=4.50), card(), profile
    )
    assert accepted is not None
    assert "Within the declared $5.00 card cap" in accepted["intent_alignment"]


def test_target_budget_keeps_but_penalizes_a_disclosed_exception():
    profile = normalize_intent_profile({
        "confirmed": True,
        "budget_mode": "target",
        "max_card_price_usd": 5,
    })

    result = apply_intent_to_suggestion(
        suggestion(price=8), card(), profile
    )

    assert result["score"] == 70
    assert result["confidence"] == 0.62
    assert "exceeds" in result["intent_warnings"][0]


def test_declared_fast_mana_and_nonland_tutor_exclusions_are_enforced():
    profile = normalize_intent_profile({
        "confirmed": True,
        "intentional_constraints": ["no_fast_mana", "no_tutors"],
    })
    mana_crypt = card(
        name="Mana Crypt",
        oracle_text="{T}: Add {C}{C}.",
        cmc=0,
    )
    demonic_tutor = card(
        name="Demonic Tutor",
        oracle_text="Search your library for a card, put it into your hand, then shuffle.",
    )
    cultivate = card(
        name="Cultivate",
        oracle_text="Search your library for up to two basic land cards.",
    )

    assert apply_intent_to_suggestion(
        suggestion("Mana Crypt", cmc=0, role="ramp"),
        mana_crypt,
        profile,
    ) is None
    assert apply_intent_to_suggestion(
        suggestion("Demonic Tutor", role="tutor"),
        demonic_tutor,
        profile,
    ) is None
    assert apply_intent_to_suggestion(
        suggestion("Cultivate", role="ramp"),
        cultivate,
        profile,
    ) is not None


def test_competitive_target_penalizes_slow_generic_cards_not_alt_cost_cards():
    profile = normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "competitive",
        "power_level_min": 9,
        "power_level_max": 10,
    })
    slow = apply_intent_to_suggestion(
        suggestion("Slow Draw", cmc=6),
        card("Slow Draw", "Draw four cards.", cmc=6),
        profile,
    )
    alternate_cost = apply_intent_to_suggestion(
        suggestion("Free Draw", cmc=6),
        card(
            "Free Draw",
            "You may exile a blue card rather than pay this spell's mana cost. Draw two cards.",
            cmc=6,
        ),
        profile,
    )

    assert slow["score"] == 74
    assert slow["intent_warnings"]
    assert alternate_cost["score"] == 96
    assert not alternate_cost["intent_warnings"]
    assert "competitive_efficiency_fit" in alternate_cost["evidence_tags"]


def test_competitive_target_rewards_low_cost_role_card():
    profile = normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "competitive",
        "power_level_min": 9,
        "power_level_max": 10,
    })
    efficient = apply_intent_to_suggestion(
        suggestion("Efficient Interaction", cmc=1, role="interaction"),
        card("Efficient Interaction", "Counter target spell.", cmc=1),
        profile,
    )

    assert efficient["score"] == 96
    assert "competitive_efficiency_fit" in efficient["evidence_tags"]
    assert "competitive efficiency" in efficient["reason"]


def test_unconfirmed_and_intentional_jank_cut_policies_abstain():
    cuts = [
        {"card_name": f"Cut {index}", "confidence": 0.8, "reason": "Flexible."}
        for index in range(5)
    ]
    unconfirmed = apply_intent_to_cuts(cuts, normalize_intent_profile())
    jank = apply_intent_to_cuts(cuts, normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "preserve",
        "intentional_constraints": ["intentional_jank"],
    }))

    assert len(unconfirmed) == 2
    assert all(cut["confidence"] == 0.48 for cut in unconfirmed)
    assert all(cut["intent_warnings"] for cut in unconfirmed)
    assert jank == []


def test_preserve_jank_rejects_generic_goodstuff_but_keeps_direct_synergy():
    profile = normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "preserve",
        "power_level_min": 3,
        "power_level_max": 4,
        "intentional_constraints": ["intentional_jank"],
    })
    generic = suggestion("Generic Staple")
    generic["evidence_tags"] = ["role_gap"]
    donation = suggestion("Bad Gift")
    donation["evidence_tags"] = ["direct_synergy"]

    assert apply_intent_to_suggestion(generic, card(), profile) is None
    accepted = apply_intent_to_suggestion(donation, card(), profile)
    assert accepted is not None
    assert "lower-power" in accepted["intent_alignment"][-1]


def test_severe_land_shortage_becomes_top_level_repair_unless_preserved():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    stats = {"total_lands": 18}
    unconfirmed = engine._build_mana_base_repair_suggestion(
        stats,
        ["B", "G"],
        normalize_intent_profile(),
    )
    preserve_low_land = engine._build_mana_base_repair_suggestion(
        stats,
        ["B", "G"],
        normalize_intent_profile({
            "confirmed": True,
            "optimization_mode": "preserve",
            "intentional_constraints": ["low_land_count"],
        }),
    )
    repair_low_land = engine._build_mana_base_repair_suggestion(
        stats,
        ["B", "G"],
        normalize_intent_profile({
            "confirmed": True,
            "optimization_mode": "repair",
            "intentional_constraints": ["low_land_count"],
        }),
    )

    assert unconfirmed["suggested_quantity"] == 12
    assert unconfirmed["action_only"]
    assert "30-land functional floor" in unconfirmed["reason"]
    assert preserve_low_land is None
    assert repair_low_land["suggested_quantity"] == 12
