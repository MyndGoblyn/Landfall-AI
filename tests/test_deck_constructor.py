import asyncio
import sys
from pathlib import Path

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


from services.build_intent import normalize_build_intent
from services.deck_constructor import ConstructorUnavailable, DeckConstructor
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def card(
    name,
    *,
    colors=None,
    mana_cost="{2}",
    type_line="Artifact",
    oracle_text="",
    cmc=2,
    price="1.00",
    commander_legal=True,
):
    return {
        "name": name,
        "oracle_id": f"id-{name.casefold().replace(' ', '-')}",
        "type_line": type_line,
        "oracle_text": oracle_text,
        "mana_cost": mana_cost,
        "cmc": cmc,
        "colors": colors or [],
        "color_identity": colors or [],
        "prices": {"usd": price} if price is not None else {},
        "legalities": {"commander": "legal" if commander_legal else "not_legal"},
        "image_uris": {"normal": f"https://img.test/{name}.jpg"},
    }


MEREN = card(
    "Meren of Clan Nel Toth",
    colors=["B", "G"],
    mana_cost="{2}{B}{G}",
    type_line="Legendary Creature — Human Shaman",
    oracle_text="Whenever another creature you control dies, you get an experience counter.",
    cmc=4,
    price="3.00",
)
VISCERA = card(
    "Viscera Seer",
    colors=["B"],
    mana_cost="{B}",
    type_line="Creature — Vampire Wizard",
    oracle_text="Sacrifice a creature: Scry 1.",
    cmc=1,
    price="0.20",
)
VICTIMIZE = card(
    "Victimize",
    colors=["B"],
    mana_cost="{2}{B}",
    type_line="Sorcery",
    oracle_text="Choose two target creature cards in your graveyard.",
    cmc=3,
    price="0.50",
)
SWORDS = card(
    "Swords to Plowshares",
    colors=["W"],
    mana_cost="{W}",
    type_line="Instant",
    oracle_text="Exile target creature.",
    cmc=1,
    price="1.00",
)
SOL_RING = card(
    "Sol Ring",
    mana_cost="{1}",
    oracle_text="{T}: Add {C}{C}.",
    cmc=1,
    price="1.25",
)
PLAINS = card("Plains", type_line="Basic Land — Plains", mana_cost="", cmc=0, price="0.10")
ISLAND = card("Island", type_line="Basic Land — Island", mana_cost="", cmc=0, price="0.10")
SWAMP = card("Swamp", type_line="Basic Land — Swamp", mana_cost="", cmc=0, price="0.10")
MOUNTAIN = card("Mountain", type_line="Basic Land — Mountain", mana_cost="", cmc=0, price="0.10")
FOREST = card("Forest", type_line="Basic Land — Forest", mana_cost="", cmc=0, price="0.10")
WASTES = card("Wastes", type_line="Basic Land — Wastes", mana_cost="", cmc=0, price="0.10")


class FakeScryfall:
    def __init__(self, cards):
        self.cards = {value["name"].casefold(): value for value in cards}

    async def get_card_bulk(self, names):
        return [self.cards.get(name.casefold()) for name in names]


class FakeEngine:
    async def analyze_deck(self, _deck, deep=False):
        assert deep
        return {
            "coverage_level": "deep",
            "strategy_profile": {
                "lanes": [
                    {
                        "id": "sacrifice",
                        "kind": "synergy",
                        "priority": 92,
                        "status": "developing",
                        "evidence": ["commander sacrifice lane"],
                    },
                    {
                        "id": "draw",
                        "kind": "role",
                        "priority": 84,
                        "status": "deficient",
                        "evidence": ["measured draw gap"],
                    },
                ],
            },
            "recommendation_planner": {
                "version": "balanced-query-planner-v3",
                "portfolio_version": "evidence-portfolio-v3",
            },
            "suggestions_add": [
                {
                    "card_name": "Viscera Seer",
                    "role_tag": "sacrifice",
                    "reason": "A repeatable sacrifice outlet advances Meren's recursion plan.",
                    "score": 96,
                    "confidence": 0.92,
                    "evidence_tags": ["direct_synergy"],
                    "matched_plan_lanes": ["sacrifice"],
                    "selection_position": 1,
                    "selection_reason": "Covers the primary engine lane.",
                    "portfolio_version": "evidence-portfolio-v3",
                },
                {
                    "card_name": "Victimize",
                    "role_tag": "recursion",
                    "reason": "Turns stocked graveyards into two bodies.",
                    "score": 91,
                    "confidence": 0.88,
                    "evidence_tags": ["direct_synergy"],
                    "matched_plan_lanes": ["graveyard"],
                    "selection_position": 2,
                },
                {
                    "card_name": "Swords to Plowshares",
                    "role_tag": "removal",
                    "reason": "Efficient removal.",
                    "score": 90,
                    "confidence": 0.9,
                    "evidence_tags": ["role_gap"],
                    "matched_plan_lanes": ["removal"],
                    "selection_position": 3,
                },
            ],
        }


class FakeIterativeEngine:
    def __init__(self):
        self.calls = 0

    async def analyze_deck(self, deck, deep=False):
        assert deep
        self.calls += 1
        present = {value["name"] for value in deck.get("cards") or []}
        next_card = next(
            (value for value in (VISCERA, VICTIMIZE) if value["name"] not in present),
            None,
        )
        suggestions = []
        if next_card:
            suggestions.append({
                "card_name": next_card["name"],
                "role_tag": "engine",
                "reason": "The next evidence pass fills a measured engine slot.",
                "score": 95,
                "confidence": 0.9,
                "evidence_tags": ["direct_synergy"],
                "matched_plan_lanes": ["engine"],
                "selection_position": 1,
                "portfolio_version": "evidence-portfolio-v3",
            })
        return {
            "coverage_level": "deep",
            "strategy_profile": {"lanes": []},
            "recommendation_planner": {
                "portfolio_version": "evidence-portfolio-v3",
            },
            "suggestions_add": suggestions,
        }


class FakeReviewedConstructionEngine:
    def __init__(self):
        self.calls = []

    async def _generate_additions(self):
        return []

    async def analyze_deck(self, _deck, deep=False, **kwargs):
        assert deep
        self.calls.append(kwargs)
        return {
            "coverage_level": "deep",
            "strategy_profile": {"lanes": []},
            "recommendation_planner": {
                "portfolio_version": "evidence-portfolio-v3",
            },
            "suggestions_add": [],
        }


def intent(**updates):
    value = {
        "confirmed": True,
        "deck_name": "Meren scaffold",
        "starting_point": "commander",
        "commander_name": MEREN["name"],
        "build_mode": "guided_scaffold",
        "playstyle": "value",
        "target_bracket": 3,
        "budget_mode": "flexible",
        "build_shape": "core_shell",
        "collection_mode": "all_cards",
    }
    value.update(updates)
    return normalize_build_intent(value)


def constructor(mode="scaffold", max_slots=40):
    return DeckConstructor(
        FakeEngine(),
        FakeScryfall([
            MEREN,
            VISCERA,
            VICTIMIZE,
            SWORDS,
            SOL_RING,
            PLAINS,
            ISLAND,
            SWAMP,
            MOUNTAIN,
            FOREST,
            WASTES,
        ]),
        mode=mode,
        max_scaffold_slots=max_slots,
    )


def test_scaffold_is_stable_and_rejects_off_identity_candidates():
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}
    first = asyncio.run(constructor().construct(deck, intent()))
    second = asyncio.run(constructor().construct(deck, intent()))

    assert first == second
    assert first["status"] == "ready_partial"
    assert [card["name"] for card in first["selected_cards"]] == [
        "Viscera Seer",
        "Victimize",
    ]
    assert any(
        item["card_name"] == "Swords to Plowshares"
        and item["code"] == "candidate_illegal"
        for item in first["validation"]["rejected_candidates"]
    )
    assert first["role_allocation"]
    assert first["unresolved_slots"][0]["count"] == 38


def test_owned_only_filters_candidates_and_protected_conflicts_block():
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}
    result = asyncio.run(constructor().construct(deck, intent(
        collection_mode="owned_only",
        owned_card_names=["Victimize"],
        protected_cards=["Viscera Seer"],
    )))

    assert result["status"] == "blocked"
    assert any(error["code"] == "protected_card_not_owned" for error in result["validation"]["errors"])
    assert [card["name"] for card in result["selected_cards"]] == ["Victimize"]


def test_full_scaffold_allocates_basics_from_symbol_demand():
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}
    result = asyncio.run(constructor().construct(deck, intent(build_shape="full_deck")))

    basics = result["mana_base"]["basic_land_allocation"]
    assert set(basics) == {"Swamp", "Forest"}
    assert sum(basics.values()) == 36
    assert basics["Swamp"] > basics["Forest"]
    assert result["scope"]["request_slot_limit"] == 40
    assert result["scope"]["selected_slots"] == 38
    assert result["scope"]["deferred_slots"] == 59


def test_owned_only_mana_allocation_respects_saved_copy_quantities():
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}
    result = asyncio.run(constructor().construct(deck, intent(
        build_shape="full_deck",
        collection_mode="owned_only",
        collection_source="saved_collection",
        owned_card_quantities={
            "Viscera Seer": 1,
            "Victimize": 1,
            "Swamp": 1,
            "Forest": 2,
        },
    )))

    basics = result["mana_base"]["basic_land_allocation"]
    assert basics == {"Swamp": 1, "Forest": 2}
    assert result["collection"] == {
        "mode": "owned_only",
        "source": "saved_collection",
        "unique_owned_cards": 4,
        "owned_copies": 5,
    }
    assert any(
        warning["code"] == "owned_only_mana_quantity_limited"
        for warning in result["validation"]["warnings"]
    )


def test_strict_budget_blocks_an_over_cap_fixed_card():
    deck = {
        "commander": MEREN["name"],
        "commanders": [MEREN["name"]],
        "cards": [{"name": "Sol Ring", "qty": 1}],
    }
    result = asyncio.run(constructor().construct(deck, intent(
        budget_mode="strict",
        max_card_price_usd=1,
    )))

    assert result["status"] == "blocked"
    assert any(error["code"] == "fixed_card_over_cap" for error in result["validation"]["errors"])


def test_complete_drafts_remain_behind_the_promotion_mode():
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}

    with pytest.raises(ConstructorUnavailable, match="Phase 5"):
        asyncio.run(constructor().construct(deck, intent(build_mode="complete_draft")))


def test_complete_mode_reanalyzes_after_each_evidence_portfolio():
    engine = FakeIterativeEngine()
    complete_constructor = DeckConstructor(
        engine,
        FakeScryfall([
            MEREN,
            VISCERA,
            VICTIMIZE,
            SWAMP,
            FOREST,
        ]),
        mode="complete",
    )
    deck = {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []}

    result = asyncio.run(complete_constructor.construct(
        deck,
        intent(build_mode="complete_draft", build_shape="full_deck"),
    ))

    assert engine.calls == 3
    assert [
        row["accepted_count"]
        for row in result["evidence"]["construction_passes"]
    ] == [1, 1, 0]
    assert [
        card["construction_pass"]
        for card in result["selected_cards"]
        if card["source"] == "planner_v3"
    ] == [1, 2]
    assert result["status"] == "ready_partial"


def test_complete_mode_enables_reviewed_profiles_without_changing_public_default():
    engine = FakeReviewedConstructionEngine()
    complete_constructor = DeckConstructor(
        engine,
        FakeScryfall([MEREN, SWAMP, FOREST]),
        mode="complete",
    )

    asyncio.run(complete_constructor.construct(
        {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []},
        intent(build_mode="complete_draft", build_shape="full_deck"),
    ))

    assert engine.calls
    assert all(
        call["use_reviewed_commander_profile"] is True
        for call in engine.calls
    )
    assert EnhancedSuggestionEngine.analyze_deck.__kwdefaults__[
        "use_reviewed_commander_profile"
    ] is False


def test_complete_mode_does_not_optimize_through_intentional_jank_constraints():
    engine = FakeReviewedConstructionEngine()
    complete_constructor = DeckConstructor(
        engine,
        FakeScryfall([MEREN, SWAMP, FOREST]),
        mode="complete",
    )

    asyncio.run(complete_constructor.construct(
        {"commander": MEREN["name"], "commanders": [MEREN["name"]], "cards": []},
        intent(
            build_mode="complete_draft",
            build_shape="full_deck",
            intentional_constraints=["intentional_jank", "flavor_first"],
        ),
    ))

    assert engine.calls
    assert all(
        call["use_reviewed_commander_profile"] is False
        for call in engine.calls
    )


def test_complete_role_reservation_tracks_structural_deficits():
    records = [
        {"role": "draw", "qty": 4},
        {"role": "mana rock", "qty": 2},
        {"role": "removal", "qty": 3},
        {"role": "protection", "qty": 2},
        {"role": "protected package", "qty": 20},
    ]

    assert DeckConstructor._complete_role_deficits(records) == {
        "draw": 1,
        "ramp": 4,
        "interaction": 3,
    }
    assert DeckConstructor._structural_role_group("card velocity") == "draw"
    assert DeckConstructor._structural_role_group("ramp") == "ramp"
    assert DeckConstructor._structural_role_group("sweeper") == "interaction"
    assert DeckConstructor._structural_role_group("landfall") is None
