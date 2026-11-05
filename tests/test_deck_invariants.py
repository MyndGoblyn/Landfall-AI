import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_invariants import (
    addition_satisfies_cut_invariants,
    apply_invariants_to_cuts,
    apply_invariants_to_suggestion,
    build_deck_invariants,
    card_invariant_traits,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def test_typal_invariant_detects_quantity_weighted_elf_core():
    cards = [
        {
            "name": "Elvish Mystic",
            "qty": 12,
            "type_line": "Creature — Elf Druid",
        },
        {
            "name": "Llanowar Tribe",
            "qty": 8,
            "type_line": "Creature - Elf Druid",
        },
        {
            "name": "Support Human",
            "qty": 6,
            "type_line": "Creature — Human Shaman",
        },
    ]
    invariants = build_deck_invariants(
        cards,
        {"intentional_constraints": ["typal_core"]},
    )

    assert invariants["typal"]["creature_type"] == "Elf"
    assert invariants["typal"]["on_type_cards"] == 20
    assert invariants["typal"]["creature_cards"] == 26


def test_typal_token_lane_rejects_generic_tokens_but_accepts_elf_tokens():
    invariants = {
        "typal": {
            "creature_type": "Elf",
            "on_type_cards": 24,
            "creature_cards": 30,
        },
        "spell_density": None,
    }
    suggestion = {
        "card_name": "Token Maker",
        "role_tag": "tokens",
        "score": 88,
        "confidence": 0.85,
        "reason": "Makes tokens.",
    }
    generic = {
        "name": "Servo Maker",
        "type_line": "Artifact",
        "oracle_text": "Create two 1/1 colorless Servo creature tokens.",
    }
    elf = {
        "name": "Elvish Promenade",
        "type_line": "Sorcery",
        "oracle_text": "Create a 1/1 green Elf Warrior creature token for each Elf you control.",
    }

    assert apply_invariants_to_suggestion(
        suggestion, generic, invariants
    ) is None
    accepted = apply_invariants_to_suggestion(suggestion, elf, invariants)
    assert accepted is not None
    assert "typal:elf" in accepted["invariant_traits"]


def test_spell_density_lane_requires_an_instant_or_sorcery():
    invariants = {
        "typal": None,
        "spell_density": {
            "instant_sorcery_cards": 35,
            "nonland_cards": 63,
        },
    }
    suggestion = {
        "card_name": "Spell Payoff",
        "role_tag": "instant_sorcery",
        "score": 88,
        "confidence": 0.85,
        "reason": "Supports spells.",
    }
    permanent = {
        "name": "Permanent Payoff",
        "type_line": "Enchantment",
        "oracle_text": "Whenever you cast an instant or sorcery, draw a card.",
    }
    instant = {
        "name": "Consider",
        "type_line": "Instant",
        "oracle_text": "Surveil 1. Draw a card.",
    }

    assert apply_invariants_to_suggestion(
        suggestion, permanent, invariants
    ) is None
    accepted = apply_invariants_to_suggestion(suggestion, instant, invariants)
    assert "spell_density" in accepted["invariant_traits"]


def test_cut_requirements_force_like_for_like_swap_traits():
    invariants = {
        "typal": {
            "creature_type": "Goblin",
            "on_type_cards": 32,
            "creature_cards": 36,
        },
        "spell_density": None,
    }
    cards = [{
        "name": "Goblin Flex Slot",
        "type_line": "Creature — Goblin Warrior",
        "oracle_text": "",
    }]
    cuts = [{
        "card_name": "Goblin Flex Slot",
        "confidence": 0.72,
        "reason": "A flexible slot.",
    }]

    annotated = apply_invariants_to_cuts(cuts, cards, invariants)[0]
    off_type_add = {"card_name": "Generic Creature", "invariant_traits": []}
    goblin_add = {
        "card_name": "Goblin Matron",
        "invariant_traits": ["typal:goblin"],
    }

    assert annotated["preservation_requirements"] == ["typal:goblin"]
    assert not addition_satisfies_cut_invariants(off_type_add, annotated)
    assert addition_satisfies_cut_invariants(goblin_add, annotated)
    assert "another Goblin card" in annotated["reason"]


def test_spell_cut_requires_a_spell_replacement():
    invariants = {
        "typal": None,
        "spell_density": {
            "instant_sorcery_cards": 40,
            "nonland_cards": 62,
        },
    }
    card = {
        "name": "Weak Counterspell",
        "type_line": "Instant",
        "oracle_text": "Counter target spell unless its controller pays {1}.",
    }

    assert card_invariant_traits(card, invariants) == ["spell_density"]


def test_swap_pairing_refuses_an_addition_that_breaks_cut_invariant():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    addition = {
        "card_name": "Generic Creature",
        "role_tag": "draw",
        "cmc": 2,
        "confidence": 0.8,
        "role_gains": {"draw": 1.0},
        "invariant_traits": [],
    }
    cut = {
        "card_name": "Goblin Flex Slot",
        "role_tag": "synergy_optimization",
        "cmc": 3,
        "confidence": 0.62,
        "preservation_requirements": ["typal:goblin"],
    }
    cards = [{
        "name": "Goblin Flex Slot",
        "type_line": "Creature — Goblin Warrior",
        "oracle_text": "",
    }]
    stats = {"role_quality": {}}

    refused = engine._pair_additions_with_safe_cuts(
        [addition],
        [cut],
        cards,
        stats,
    )
    addition["invariant_traits"] = ["typal:goblin"]
    accepted = engine._pair_additions_with_safe_cuts(
        [addition],
        [cut],
        cards,
        stats,
    )

    assert refused[0]["cut"] is None
    assert accepted[0]["cut"]["card_name"] == "Goblin Flex Slot"


def test_aura_ladder_fills_missing_rung_and_protects_unique_mana_value():
    cards = [
        {"name": "One Aura", "type_line": "Enchantment — Aura", "cmc": 1},
        {"name": "Two Aura", "type_line": "Enchantment — Aura", "cmc": 2},
        {"name": "Four Aura", "type_line": "Enchantment — Aura", "cmc": 4},
    ]
    invariants = build_deck_invariants(
        cards,
        {},
        {"aura_tutor_chain": True},
        ["enchantment", "voltron"],
    )
    candidate = {
        "card_name": "Three Aura",
        "role_tag": "voltron",
        "score": 84,
        "confidence": 0.82,
        "reason": "Protects the commander.",
        "evidence_tags": ["direct_synergy"],
    }
    card = {
        "name": "Three Aura",
        "type_line": "Enchantment — Aura",
        "oracle_text": "Enchant creature. Enchanted creature has hexproof.",
        "cmc": 3,
    }

    accepted = apply_invariants_to_suggestion(candidate, card, invariants)
    cuts = apply_invariants_to_cuts(
        [{"card_name": "One Aura", "confidence": 0.7, "reason": "Flexible."}],
        cards,
        invariants,
    )

    assert invariants["aura_ladder"]["missing_core_mana_values"] == ["3"]
    assert accepted["score"] == 92
    assert "aura_density" in accepted["invariant_traits"]
    assert cuts[0]["preservation_requirements"] == [
        "aura_density",
        "aura_mv:1",
    ]


def test_card_type_spread_rewards_scarce_type_and_permanent_engine_penalizes_spell():
    atraxa_cards = [
        {"name": "Creatures", "qty": 20, "type_line": "Creature"},
        {"name": "Artifacts", "qty": 10, "type_line": "Artifact"},
        {"name": "Enchantments", "qty": 8, "type_line": "Enchantment"},
        {"name": "Removal", "qty": 8, "type_line": "Instant"},
        {"name": "Walkers", "qty": 1, "type_line": "Planeswalker"},
    ]
    atraxa = build_deck_invariants(
        atraxa_cards,
        {},
        {
            "card_type_diversity": True,
            "card_types_mentioned": [
                "artifact", "battle", "creature", "enchantment",
                "instant", "land", "planeswalker", "sorcery",
            ],
        },
        ["card_type_diversity"],
    )
    planeswalker = apply_invariants_to_suggestion(
        {
            "card_name": "Removal Walker",
            "role_tag": "removal",
            "score": 82,
            "confidence": 0.8,
            "reason": "Removes a permanent.",
        },
        {
            "name": "Removal Walker",
            "type_line": "Legendary Planeswalker",
            "oracle_text": "Destroy target creature.",
        },
        atraxa,
    )
    muldrotha = build_deck_invariants(
        atraxa_cards,
        {},
        {"graveyard_permanent_engine": True},
        ["graveyard"],
    )
    instant = apply_invariants_to_suggestion(
        {
            "card_name": "One-shot Removal",
            "role_tag": "removal",
            "score": 84,
            "confidence": 0.82,
            "reason": "Removes a permanent.",
        },
        {
            "name": "One-shot Removal",
            "type_line": "Instant",
            "oracle_text": "Destroy target creature.",
        },
        muldrotha,
    )

    assert "planeswalker" in atraxa["card_type_spread"]["protected_types"]
    assert planeswalker["score"] == 87
    assert "archetype_invariant" in planeswalker["evidence_tags"]
    assert instant["score"] == 72
    assert "permanent_engine_mismatch" in instant["penalty_tags"]


def test_sacrifice_engine_tracks_components_and_protects_scarce_outlet():
    cards = [
        {
            "name": "Viscera Seer",
            "type_line": "Creature — Vampire Wizard",
            "oracle_text": "Sacrifice a creature: Scry 1.",
        },
        {
            "name": "Blood Artist",
            "type_line": "Creature — Vampire",
            "oracle_text": "Whenever another creature dies, target player loses 1 life.",
        },
        {
            "name": "Token Maker",
            "qty": 2,
            "type_line": "Creature",
            "oracle_text": "Create two 1/1 black Rat creature tokens.",
        },
    ]
    invariants = build_deck_invariants(
        cards,
        {},
        {},
        ["sacrifice", "tokens"],
    )
    cuts = apply_invariants_to_cuts(
        [{"card_name": "Viscera Seer", "confidence": 0.75, "reason": "Flexible."}],
        cards,
        invariants,
    )
    outlet = apply_invariants_to_suggestion(
        {
            "card_name": "Carrion Feeder",
            "role_tag": "sacrifice",
            "score": 84,
            "confidence": 0.82,
            "reason": "Provides an outlet.",
        },
        {
            "name": "Carrion Feeder",
            "type_line": "Creature — Zombie",
            "oracle_text": "Sacrifice a creature: Put a +1/+1 counter on Carrion Feeder.",
        },
        invariants,
    )

    assert invariants["sacrifice_engine"]["component_counts"] == {
        "outlet": 1,
        "payoff": 1,
        "fodder": 2,
    }
    assert cuts[0]["preservation_requirements"] == ["sacrifice:outlet"]
    assert outlet["score"] == 90
    assert "sacrifice:outlet" in outlet["invariant_traits"]


def test_declared_package_reports_coverage_and_boosts_missing_member():
    invariants = build_deck_invariants(
        [{"name": "Doomsday", "type_line": "Sorcery"}],
        {
            "protected_packages": [{
                "name": "Doomsday line",
                "cards": ["Doomsday", "Thassa's Oracle"],
            }],
        },
    )
    oracle = apply_invariants_to_suggestion(
        {
            "card_name": "Thassa's Oracle",
            "role_tag": "combo",
            "score": 82,
            "confidence": 0.8,
            "reason": "Completes the declared line.",
        },
        {
            "name": "Thassa's Oracle",
            "type_line": "Creature — Merfolk Wizard",
            "oracle_text": "When this creature enters, look at the top X cards.",
        },
        invariants,
    )

    package = invariants["protected_packages"][0]
    assert package["present_cards"] == ["Doomsday"]
    assert package["missing_cards"] == ["Thassa's Oracle"]
    assert not package["complete"]
    assert oracle["score"] == 94
    assert "declared_package_fit" in oracle["evidence_tags"]
