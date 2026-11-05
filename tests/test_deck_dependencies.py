import asyncio
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_dependencies import (
    build_dependency_graph,
    dependency_cut_requirements,
    dependency_traits,
    is_dependency_cut_forbidden,
)
from services.deck_invariants import (
    apply_invariants_to_cuts,
    apply_invariants_to_suggestion,
    build_deck_invariants,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def test_typed_tutors_track_targets_and_mana_value_limits():
    cards = [
        {
            "name": "Heliod's Pilgrim",
            "type_line": "Creature — Human Cleric",
            "oracle_text": (
                "When Heliod's Pilgrim enters, you may search your library for "
                "an Aura card, reveal it, put it into your hand, then shuffle."
            ),
        },
        {
            "name": "Zur the Enchanter",
            "type_line": "Legendary Creature — Human Wizard",
            "oracle_text": (
                "Whenever Zur the Enchanter attacks, you may search your library "
                "for an enchantment card with mana value 3 or less, put it onto "
                "the battlefield, then shuffle."
            ),
        },
        {
            "name": "Cheap Aura",
            "type_line": "Enchantment — Aura",
            "cmc": 2,
        },
        {
            "name": "Expensive Aura",
            "type_line": "Enchantment — Aura",
            "cmc": 4,
        },
    ]

    graph = build_dependency_graph(cards)
    packages = {package["key"]: package for package in graph["tutor_packages"]}

    assert packages["enchantment-aura"]["target_cards"] == [
        "Cheap Aura",
        "Expensive Aura",
    ]
    assert packages["enchantment-mv-le-3"]["target_cards"] == ["Cheap Aura"]
    assert packages["enchantment-mv-le-3"]["status"] == "fragile"


def test_creature_subtype_tutor_is_supported_only_with_deck_evidence():
    cards = [
        {
            "name": "Goblin Matron",
            "type_line": "Creature — Goblin",
            "oracle_text": (
                "When Goblin Matron enters, you may search your library for a "
                "Goblin card, reveal it, put it into your hand, then shuffle."
            ),
        },
        {"name": "Skirk Prospector", "type_line": "Creature — Goblin"},
        {"name": "Elvish Mystic", "type_line": "Creature — Elf Druid"},
    ]

    graph = build_dependency_graph(cards)
    package = graph["tutor_packages"][0]

    assert package["required_subtype"] == "goblin"
    assert package["target_cards"] == ["Skirk Prospector"]


def test_fragile_tutor_target_requires_a_legal_replacement():
    cards = [
        {
            "name": "Idyllic Tutor",
            "type_line": "Sorcery",
            "oracle_text": (
                "Search your library for an enchantment card, reveal it, put it "
                "into your hand, then shuffle."
            ),
        },
        {"name": "Only Enchantment", "type_line": "Enchantment", "cmc": 3},
    ]
    invariants = build_deck_invariants(cards, {})
    cuts = apply_invariants_to_cuts(
        [{
            "card_name": "Only Enchantment",
            "confidence": 0.72,
            "reason": "Flexible slot.",
        }],
        cards,
        invariants,
    )
    replacement = {
        "name": "Replacement Enchantment",
        "type_line": "Enchantment",
        "cmc": 2,
    }

    assert cuts[0]["preservation_requirements"] == [
        "tutor_target:enchantment"
    ]
    assert "another target for Enchantment card" in cuts[0]["reason"]
    assert dependency_traits(
        replacement, invariants["dependencies"]
    ) == ["tutor_target:enchantment"]


def test_dead_tutor_target_candidate_receives_bounded_evidence_boost():
    cards = [{
        "name": "Steelshaper's Gift",
        "type_line": "Sorcery",
        "oracle_text": (
            "Search your library for an Equipment card, reveal that card, put it "
            "into your hand, then shuffle."
        ),
    }]
    invariants = build_deck_invariants(cards, {})
    suggestion = apply_invariants_to_suggestion(
        {
            "card_name": "Swiftfoot Boots",
            "role_tag": "protection",
            "score": 82,
            "confidence": 0.8,
            "reason": "Protects the commander.",
        },
        {
            "name": "Swiftfoot Boots",
            "type_line": "Artifact — Equipment",
            "cmc": 2,
        },
        invariants,
    )

    package = invariants["dependencies"]["tutor_packages"][0]
    assert package["status"] == "dead"
    assert suggestion["score"] == 92
    assert "dependency_target_fit" in suggestion["evidence_tags"]
    assert "tutor_target:artifact-equipment" in suggestion["invariant_traits"]


def test_exact_named_links_protect_present_cards_and_reward_missing_target():
    pir = {
        "name": "Pir, Imaginative Rascal",
        "type_line": "Legendary Creature — Human",
        "oracle_text": (
            "Partner with Toothy, Imaginary Friend (When this creature enters, "
            "target player may put Toothy into their hand from their library, "
            "then shuffle.)"
        ),
    }
    graph = build_dependency_graph([pir])
    link = graph["named_links"][0]

    assert link["target_card"] == "Toothy, Imaginary Friend"
    assert link["status"] == "missing"
    assert is_dependency_cut_forbidden("Pir, Imaginative Rascal", graph)
    assert not is_dependency_cut_forbidden("Unrelated Card", graph)

    invariants = build_deck_invariants([pir], {})
    suggestion = apply_invariants_to_suggestion(
        {
            "card_name": "Toothy, Imaginary Friend",
            "role_tag": "counters",
            "score": 80,
            "confidence": 0.8,
            "reason": "Adds a counter payoff.",
        },
        {
            "name": "Toothy, Imaginary Friend",
            "type_line": "Legendary Creature — Illusion",
            "cmc": 4,
        },
        invariants,
    )

    assert suggestion["score"] == 94
    assert "named_dependency_fit" in suggestion["evidence_tags"]

    complete = build_dependency_graph([
        pir,
        {"name": "Toothy, Imaginary Friend", "type_line": "Legendary Creature"},
    ])
    assert complete["named_links"][0]["status"] == "complete"
    assert is_dependency_cut_forbidden("Toothy, Imaginary Friend", complete)


def test_named_card_parser_preserves_commas_in_card_names():
    graph = build_dependency_graph([{
        "name": "Search for Pir",
        "type_line": "Sorcery",
        "oracle_text": (
            "Search your library for a card named Pir, Imaginative Rascal, "
            "reveal it, put it into your hand, then shuffle."
        ),
    }])

    assert graph["named_links"][0]["target_card"] == "Pir, Imaginative Rascal"


def test_land_ramp_and_unsupported_text_do_not_create_dependency_packages():
    cards = [
        {
            "name": "Rampant Growth",
            "type_line": "Sorcery",
            "oracle_text": (
                "Search your library for a basic land card, put that card onto "
                "the battlefield tapped, then shuffle."
            ),
        },
        {
            "name": "Speculative Combo Card",
            "type_line": "Artifact",
            "oracle_text": "This works well with cards that untap artifacts.",
        },
        {
            "name": "Color Restricted Search",
            "type_line": "Sorcery",
            "oracle_text": "Search your library for a green creature card, then shuffle.",
        },
        {
            "name": "Power Restricted Search",
            "type_line": "Sorcery",
            "oracle_text": (
                "Search your library for a creature card with power 2 or less, "
                "reveal it, put it into your hand, then shuffle."
            ),
        },
    ]

    graph = build_dependency_graph(cards)

    assert not graph["active"]
    assert graph["tutor_packages"] == []
    assert graph["named_links"] == []
    assert dependency_cut_requirements(cards[0], graph) == []


def test_exact_named_dependency_is_removed_from_engine_cut_pool():
    class NoopScryfall:
        async def search_card(self, _name):
            return None

    source = {
        "name": "Expensive Partner",
        "type_line": "Legendary Creature",
        "oracle_text": "Partner with Missing Partner",
        "cmc": 8,
        "tags": [],
    }
    cards = [
        source,
        {
            "name": "Cheap Flexible Card",
            "type_line": "Artifact",
            "oracle_text": "",
            "cmc": 2,
            "tags": [],
        },
    ]
    invariants = build_deck_invariants(cards, {})
    engine = EnhancedSuggestionEngine(NoopScryfall())

    cuts = asyncio.run(engine._generate_cuts(
        cards=cards,
        gaps={"roles": {}, "lands": {}},
        stats={"role_counts": {}},
        commander_synergies=[],
        detected_themes=[],
        deck_invariants=invariants,
    ))

    assert "Expensive Partner" not in {cut["card_name"] for cut in cuts}
