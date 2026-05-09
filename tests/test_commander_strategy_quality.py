import sys
from pathlib import Path
import asyncio

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def make_engine():
    return EnhancedSuggestionEngine(scryfall_service=None)


class FakeScryfall:
    def __init__(self):
        self.queries = []
        self.results = []
        self.named_cards = {}

    def extract_card_data(self, scryfall_card):
        return {
            "name": scryfall_card.get("name"),
            "type_line": scryfall_card.get("type_line"),
            "oracle_text": scryfall_card.get("oracle_text", ""),
            "cmc": scryfall_card.get("cmc", 0),
            "colors": scryfall_card.get("colors", []),
            "color_identity": scryfall_card.get("color_identity", []),
            "set_code": scryfall_card.get("set"),
            "collector_number": scryfall_card.get("collector_number"),
            "prices": scryfall_card.get("prices", {}),
            "keywords": scryfall_card.get("keywords", []),
            "legalities": scryfall_card.get("legalities", {}),
        }

    async def search_cards_by_criteria(self, query, limit=20):
        self.queries.append((query, limit))
        return self.results

    async def search_card(self, name):
        return self.named_cards.get(name)


def test_playstyle_tips_do_not_assume_specific_unrelated_counter_or_token_plans():
    engine = make_engine()
    stats = {
        "total_lands": 36,
        "role_counts": {
            "draw": 8,
            "ramp": 10,
            "interaction": 5,
        },
    }
    commander_card = {
        "name": "Test Counter Commander",
        "oracle_text": "Whenever one or more +1/+1 counters are put on a creature you control, proliferate.",
        "type_line": "Legendary Creature",
    }

    tips = engine._generate_playstyle_tips(
        stats,
        commander_synergies=["counters"],
        detected_themes=["counters", "tokens"],
        commander="Test Counter Commander",
        color_identity=["G", "W"],
        commander_card=commander_card,
    )
    joined = " ".join(tips).lower()

    assert "blight" not in joined
    assert "elf" not in joined
    assert "+1/+1 counters" in joined


def test_zur_strategy_tips_are_tutor_limit_specific_and_color_legal():
    engine = make_engine()
    zur_card = {
        "name": "Zur the Enchanter",
        "oracle_text": (
            "Flying. Whenever Zur the Enchanter attacks, you may search your library "
            "for an enchantment card with mana value 3 or less, put it onto the battlefield, then shuffle."
        ),
        "type_line": "Legendary Creature - Human Wizard",
        "color_identity": ["W", "U", "B"],
    }
    synergies = engine._detect_commander_synergies(zur_card)
    constraints = engine._get_commander_constraints(zur_card)

    tips = engine._generate_commander_strategy_tips(zur_card, synergies, constraints)
    joined = " ".join(tips)

    assert "mana value 3 or less" in joined
    assert "Enchantress's Presence" not in joined
    assert "Eidolon of Blossoms" not in joined
    assert any(name in joined for name in ["Mystic Remora", "Rhystic Study", "Necropotence"])


def test_role_examples_respect_color_identity():
    engine = make_engine()

    examples = engine._role_examples("draw", ["G"], [])

    assert "Rhystic Study" not in examples
    assert "Mystic Remora" not in examples
    assert "Phyrexian Arena" not in examples
    assert "Toski, Bearer of Secrets" in examples


def test_random_commander_query_translates_freeform_terms_to_scryfall_syntax():
    engine = make_engine()

    query = engine._build_random_commander_query(
        colors=["B", "G"],
        max_cmc=4,
        search_text="artifact graveyard lifegain counters zombies",
    )

    assert query.startswith("is:commander t:creature f:commander")
    assert "id:bg" in query
    assert "cmc<=4" in query
    assert "otag:lifegain" in query
    assert "o:graveyard" in query
    assert 'o:"+1/+1 counter"' in query
    assert "t:zombie" in query


def test_random_commander_query_supports_keyword_abilities_and_sanitizes_text():
    engine = make_engine()

    query = engine._build_random_commander_query(
        search_text='double strike weird<>term',
    )

    assert 'kw:"double strike"' in query
    assert "<" not in query
    assert ">" not in query


def test_commander_eligibility_requires_actual_commander_permission():
    engine = make_engine()

    legendary_creature = {
        "name": "Legal Commander",
        "type_line": "Legendary Creature - Human Wizard",
        "legalities": {"commander": "legal"},
    }
    legendary_vehicle = {
        "name": "Legendary Vehicle",
        "type_line": "Legendary Artifact - Vehicle",
        "legalities": {"commander": "legal"},
    }
    commander_planeswalker = {
        "name": "Commander Planeswalker",
        "type_line": "Legendary Planeswalker",
        "oracle_text": "This card can be your commander.",
        "legalities": {"commander": "legal"},
    }

    assert engine._is_commander_eligible(legendary_creature)
    assert not engine._is_commander_eligible(legendary_vehicle)
    assert engine._is_commander_eligible(commander_planeswalker)
    assert not engine._is_commander_eligible(commander_planeswalker, creature_only=True)


def test_random_commander_filters_to_legendary_creatures():
    engine = make_engine()

    query = engine._build_random_commander_query(search_text="graveyard")

    assert "t:creature" in query


def test_random_commander_colorless_filter_is_exact_color_identity():
    engine = make_engine()

    query = engine._build_random_commander_query(colors=["C"])

    assert "id:c" in query
    assert "id:w" not in query


def test_commander_synergy_detection_does_not_use_type_line_only_artifact_theme():
    engine = make_engine()
    artifact_body = {
        "name": "Artifact Body Commander",
        "type_line": "Legendary Artifact Creature - Construct",
        "oracle_text": "Whenever you draw your second card each turn, put a +1/+1 counter on this creature.",
    }

    synergies = engine._detect_commander_synergies(artifact_body)

    assert "artifact" not in synergies
    assert "counters" in synergies


def test_artifact_synergy_rejects_generic_artifact_without_rules_support():
    engine = make_engine()
    mana_rock = {
        "name": "Generic Mana Rock",
        "type_line": "Artifact",
        "oracle_text": "Tap: Add one mana of any color.",
    }
    artifact_engine = {
        "name": "Artifact Payoff",
        "type_line": "Artifact",
        "oracle_text": "Whenever an artifact enters the battlefield under your control, draw a card.",
    }

    assert not engine._card_matches_synergy(mana_rock, "artifact")
    assert engine._card_matches_synergy(artifact_engine, "artifact")


def test_noncreature_spell_text_does_not_trigger_creature_theme():
    engine = make_engine()
    vivi_card = {
        "name": "Vivi Ornitier",
        "type_line": "Legendary Creature - Wizard",
        "oracle_text": (
            "Whenever you cast a noncreature spell, put a +1/+1 counter on Vivi Ornitier "
            "and it deals 1 damage to each opponent."
        ),
        "color_identity": ["U", "R"],
    }

    synergies = engine._detect_commander_synergies(vivi_card)
    tips = engine._generate_commander_strategy_tips(
        vivi_card,
        synergies,
        engine._get_commander_constraints(vivi_card),
    )
    joined = " ".join(tips).lower()

    assert "creature" not in synergies
    assert "instant_sorcery" in synergies
    assert "rewards casting creatures" not in joined


def test_counter_reasons_do_not_invent_proliferate_or_blight_language():
    engine = make_engine()
    commander = {
        "name": "Counter Commander",
        "type_line": "Legendary Creature",
        "oracle_text": "Whenever another creature you control dies, put a +1/+1 counter on this creature.",
    }
    card = {
        "name": "Hardened Scales",
        "type_line": "Enchantment",
        "oracle_text": "If one or more +1/+1 counters would be put on a creature you control, that many plus one are put on it instead.",
        "cmc": 1,
    }

    reason = engine._generate_commander_recommendation_reason(card, commander["name"], "counters", commander)

    assert "proliferate ability" not in reason
    assert "blight" not in reason.lower()


def test_self_counter_commanders_do_not_accept_proliferate_or_self_contained_counter_cards():
    engine = make_engine()
    commander = {
        "name": "Gimli of the Glittering Caves",
        "type_line": "Legendary Creature - Dwarf Warrior",
        "oracle_text": "Whenever one or more Treasures enter the battlefield under your control, put a +1/+1 counter on Gimli of the Glittering Caves.",
    }
    karns_bastion = {
        "name": "Karn's Bastion",
        "type_line": "Land",
        "oracle_text": "{4}, {T}: Proliferate.",
    }
    walking_ballista = {
        "name": "Walking Ballista",
        "type_line": "Artifact Creature - Construct",
        "oracle_text": "Walking Ballista enters the battlefield with X +1/+1 counters on it. Remove a +1/+1 counter from Walking Ballista: It deals 1 damage to any target.",
    }
    hardened_scales = {
        "name": "Hardened Scales",
        "type_line": "Enchantment",
        "oracle_text": "If one or more +1/+1 counters would be put on a creature you control, that many plus one are put on it instead.",
    }
    opal_palace = {
        "name": "Opal Palace",
        "type_line": "Land",
        "oracle_text": "{T}: Add one mana of any color in your commander's color identity. If you spend this mana to cast your commander, it enters with a number of additional +1/+1 counters on it.",
    }

    assert not engine._card_matches_commander_context(karns_bastion, "counters", commander)
    assert not engine._card_matches_commander_context(walking_ballista, "counters", commander)
    assert engine._card_matches_commander_context(hardened_scales, "counters", commander)
    assert engine._card_matches_commander_context(opal_palace, "counters", commander)


def test_named_counter_commanders_do_not_accept_plus_one_counter_package():
    engine = make_engine()
    commander = {
        "name": "Ultima, Origin of Oblivion",
        "type_line": "Legendary Creature - God",
        "oracle_text": "Whenever Ultima attacks, put a blight counter on target land. Whenever you tap a land for {C}, add an additional {C}.",
    }
    hardened_scales = {
        "name": "Hardened Scales",
        "type_line": "Enchantment",
        "oracle_text": "If one or more +1/+1 counters would be put on a creature you control, that many plus one are put on it instead.",
    }
    contagion_clasp = {
        "name": "Contagion Clasp",
        "type_line": "Artifact",
        "oracle_text": "{4}, {T}: Proliferate.",
    }

    constraints = engine._get_commander_constraints(commander)
    tips = engine._generate_commander_strategy_tips(
        commander,
        ["counters"],
        constraints,
    )
    reason = engine._generate_commander_recommendation_reason(
        contagion_clasp,
        commander["name"],
        "counters",
        commander,
    )

    assert constraints["counter_plan"] == "named_counters"
    assert engine._named_counter_terms(commander["oracle_text"]) == ["blight"]
    assert not engine._card_matches_commander_context(hardened_scales, "counters", commander)
    assert engine._card_matches_commander_context(contagion_clasp, "counters", commander)
    assert "generic +1/+1 counter cards do not advance this plan" in " ".join(tips)
    assert "blight counters" in reason
    assert "put a blight counters" not in reason


def test_commander_analysis_uses_larger_search_budget_only_for_deep_mode():
    fake_scryfall = FakeScryfall()
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander_card = {
        "name": "Many Themes Commander",
        "oracle_text": (
            "Whenever you cast an instant or sorcery spell, create a creature token. "
            "Whenever you gain life, put a +1/+1 counter on each creature you control. "
            "You may play cards from exile. Landfall. Sacrifice an artifact: return target card from your graveyard."
        ),
        "type_line": "Legendary Artifact Enchantment Creature",
        "color_identity": ["W", "U", "B", "R", "G"],
        "legalities": {"commander": "legal"},
    }

    asyncio.run(engine.analyze_commander(commander_card, deep=False))
    fast_query_count = len(fake_scryfall.queries)
    fake_scryfall.queries.clear()

    deep_result = asyncio.run(engine.analyze_commander(commander_card, deep=True))
    deep_query_count = len(fake_scryfall.queries)

    assert fast_query_count == 3
    assert deep_query_count > fast_query_count
    assert deep_query_count <= 8
    assert deep_result["analysis_depth"] == "deep"
    assert any("Deep Strategy" in tip for tip in deep_result["strategy_tips"])


def test_deep_strategy_tips_are_visibly_distinct_from_fast_tips():
    engine = make_engine()
    zur_card = {
        "name": "Zur the Enchanter",
        "oracle_text": (
            "Flying. Whenever Zur the Enchanter attacks, you may search your library "
            "for an enchantment card with mana value 3 or less, put it onto the battlefield, then shuffle."
        ),
        "type_line": "Legendary Creature - Human Wizard",
        "color_identity": ["W", "U", "B"],
    }
    synergies = engine._detect_commander_synergies(zur_card)
    constraints = engine._get_commander_constraints(zur_card)

    fast_tips = engine._generate_commander_strategy_tips(zur_card, synergies, constraints)
    deep_tips = fast_tips + engine._generate_deep_commander_strategy_tips(zur_card, synergies, constraints)

    assert len(deep_tips) > len(fast_tips)
    assert any("Deep Strategy - Tutor Map" in tip for tip in deep_tips)


@pytest.mark.parametrize(
    ("commander_card", "expected_synergies", "expected_tip_terms"),
    [
        (
            {
                "name": "Artifact Recursion Commander",
                "oracle_text": "Whenever an artifact card is put into your graveyard from anywhere, you may return another target artifact card from your graveyard to your hand.",
                "type_line": "Legendary Artifact Creature",
                "color_identity": ["U", "B"],
            },
            {"artifact", "graveyard"},
            ["artifacts", "graveyard"],
        ),
        (
            {
                "name": "Creature ETB Commander",
                "oracle_text": "Whenever another creature enters the battlefield under your control, draw a card.",
                "type_line": "Legendary Creature",
                "color_identity": ["G", "U"],
            },
            {"creature"},
            ["etb", "creatures"],
        ),
        (
            {
                "name": "Blink Commander",
                "oracle_text": "Exile another target creature you control, then return it to the battlefield under its owner's control.",
                "type_line": "Legendary Creature",
                "color_identity": ["W", "U"],
            },
            {"blink"},
            ["blink", "etb"],
        ),
        (
            {
                "name": "Exile Value Commander",
                "oracle_text": "Whenever you play a card from exile, create a Treasure token.",
                "type_line": "Legendary Creature",
                "color_identity": ["B", "R"],
            },
            {"exile", "artifact_tokens"},
            ["exile", "treasure"],
        ),
        (
            {
                "name": "Lifegain Commander",
                "oracle_text": "Whenever you gain life, put a +1/+1 counter on each creature you control.",
                "type_line": "Legendary Creature",
                "color_identity": ["W", "B"],
            },
            {"lifegain", "counters", "creature"},
            ["lifegain", "counters"],
        ),
        (
            {
                "name": "Landfall Commander",
                "oracle_text": "Landfall - Whenever a land enters the battlefield under your control, draw a card.",
                "type_line": "Legendary Creature",
                "color_identity": ["G", "U"],
            },
            {"landfall"},
            ["landfall", "land drops"],
        ),
    ],
)
def test_strategy_tips_cover_representative_commander_archetypes(
    commander_card,
    expected_synergies,
    expected_tip_terms,
):
    engine = make_engine()

    synergies = set(engine._detect_commander_synergies(commander_card))
    tips = engine._generate_commander_strategy_tips(
        commander_card,
        list(synergies),
        engine._get_commander_constraints(commander_card),
    )
    joined = " ".join(tips).lower()

    assert expected_synergies.issubset(synergies)
    for term in expected_tip_terms:
        assert term in joined
    assert "rhystic study" not in joined or "U" in commander_card["color_identity"]
    assert "phyrexian arena" not in joined or "B" in commander_card["color_identity"]


def test_brago_is_blink_not_impulse_exile():
    engine = make_engine()
    brago = {
        "name": "Brago, King Eternal",
        "oracle_text": (
            "Flying. Whenever Brago, King Eternal deals combat damage to a player, "
            "exile any number of target nonland permanents you control, then return "
            "those cards to the battlefield under their owner's control."
        ),
        "type_line": "Legendary Creature",
        "color_identity": ["W", "U"],
    }
    mystic_forge = {
        "name": "Mystic Forge",
        "oracle_text": "You may look at the top card of your library any time. You may cast artifact spells and colorless spells from the top of your library.",
        "type_line": "Artifact",
    }
    wall_of_omens = {
        "name": "Wall of Omens",
        "oracle_text": "Defender. When Wall of Omens enters the battlefield, draw a card.",
        "type_line": "Creature",
    }

    synergies = engine._detect_commander_synergies(brago)

    assert "blink" in synergies
    assert "exile" not in synergies
    assert not engine._card_matches_commander_context(mystic_forge, "blink", brago)
    assert engine._card_matches_commander_context(wall_of_omens, "blink", brago)


def test_sacrifice_recommendations_reject_land_fetches():
    engine = make_engine()
    teysa = {
        "name": "Teysa Karlov",
        "oracle_text": (
            "If a creature dying causes a triggered ability of a permanent you control to trigger, "
            "that ability triggers an additional time."
        ),
        "type_line": "Legendary Creature",
        "color_identity": ["W", "B"],
    }
    evolving_wilds = {
        "name": "Evolving Wilds",
        "oracle_text": "{T}, Sacrifice Evolving Wilds: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
        "type_line": "Land",
    }
    viscera_seer = {
        "name": "Viscera Seer",
        "oracle_text": "Sacrifice a creature: Scry 1.",
        "type_line": "Creature",
    }

    assert not engine._card_matches_commander_context(evolving_wilds, "sacrifice", teysa)
    assert engine._card_matches_commander_context(viscera_seer, "sacrifice", teysa)


def test_voltron_recommendations_reject_curses_as_generic_auras():
    engine = make_engine()
    curse = {
        "name": "Curse of Opulence",
        "oracle_text": "Enchant player. Whenever enchanted player is attacked, create a Gold token.",
        "type_line": "Enchantment — Aura Curse",
    }
    boots = {
        "name": "Swiftfoot Boots",
        "oracle_text": "Equipped creature has hexproof and haste. Equip {1}.",
        "type_line": "Artifact — Equipment",
    }

    assert not engine._card_matches_synergy(curse, "voltron")
    assert engine._card_matches_synergy(boots, "voltron")


def test_commander_recommendations_exclude_lands_even_when_mechanically_relevant():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Karn's Bastion",
            "oracle_text": "{4}, {T}: Proliferate.",
            "type_line": "Land",
            "cmc": 0,
            "color_identity": [],
        },
        {
            "name": "Contagion Clasp",
            "oracle_text": "When Contagion Clasp enters the battlefield, put a -1/-1 counter on target creature. {4}, {T}: Proliferate.",
            "type_line": "Artifact",
            "cmc": 2,
            "color_identity": [],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Named Counter Commander",
        "oracle_text": "Whenever this creature attacks, put a blight counter on target creature. Then proliferate.",
        "type_line": "Legendary Creature",
        "color_identity": [],
    }

    cards = asyncio.run(engine._search_commander_recommendations(
        commander_card=commander,
        synergies=["counters"],
        color_identity=[],
        commander_constraints=engine._get_commander_constraints(commander),
        max_cards=5,
        search_budget=1,
        per_synergy_limit=5,
        query_limit=10,
        minimum_score=72,
    ))

    assert [card["name"] for card in cards] == ["Contagion Clasp"]


def test_parallel_recommendation_search_is_bounded():
    class SlowScryfall(FakeScryfall):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def search_cards_by_criteria(self, query, limit=20):
            self.queries.append((query, limit))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return []

    fake_scryfall = SlowScryfall()
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Many Themes Commander",
        "oracle_text": "Whenever you cast a creature spell, create a token, gain life, proliferate, then play a card from exile. Landfall.",
        "type_line": "Legendary Artifact Enchantment Creature",
        "color_identity": ["W", "U", "B", "R", "G"],
    }

    asyncio.run(engine._search_commander_recommendations(
        commander_card=commander,
        synergies=["artifact", "creature", "tokens", "lifegain", "counters", "exile", "landfall"],
        color_identity=["W", "U", "B", "R", "G"],
        commander_constraints=engine._get_commander_constraints(commander),
        max_cards=5,
        search_budget=7,
        per_synergy_limit=2,
        query_limit=10,
        minimum_score=84,
        concurrency=3,
    ))

    assert len(fake_scryfall.queries) > 3
    assert fake_scryfall.max_active <= 3
    assert fake_scryfall.max_active > 1


def test_generic_combo_lines_are_not_added_for_creature_themes():
    engine = make_engine()

    combos = engine._generate_combo_suggestions(
        "Chulane, Teller of Tales",
        ["creature"],
        [],
    )

    assert combos == []


def test_board_conversion_profile_is_general_not_commander_specific():
    engine = make_engine()
    commander = {
        "name": "Wide Board Converter",
        "oracle_text": (
            "Other creatures you control have base power and toughness 4/2 "
            "and are Warriors in addition to their other creature types. "
            "Creatures you control attack each combat if able."
        ),
        "type_line": "Legendary Creature",
        "color_identity": ["R"],
    }

    synergies = engine._detect_commander_synergies(commander)
    tips = engine._generate_commander_strategy_tips(
        commander,
        synergies,
        engine._get_commander_constraints(commander),
    )
    joined = " ".join(tips).lower()

    assert "board_conversion" in synergies
    assert "cheap bodies" in joined
    assert "token makers" in joined
    assert "quantity into combat pressure" in joined


def test_board_conversion_scores_bodies_and_rejects_etb_only_value():
    engine = make_engine()
    commander = {
        "name": "Wide Board Converter",
        "oracle_text": "Other creatures you control have base power and toughness 4/2. Creatures you control attack each combat if able.",
        "type_line": "Legendary Creature",
        "color_identity": [],
    }
    token_maker = {
        "name": "Servo Engine",
        "oracle_text": "When Servo Engine enters the battlefield, create two 1/1 colorless Servo artifact creature tokens.",
        "type_line": "Artifact Creature",
        "cmc": 3,
    }
    cheap_body = {
        "name": "Signal Pest",
        "oracle_text": "Battle cry.",
        "type_line": "Artifact Creature",
        "cmc": 1,
    }
    etb_value = {
        "name": "Solemn Simulacrum",
        "oracle_text": "When Solemn Simulacrum enters the battlefield, search your library for a basic land card. When it dies, you may draw a card.",
        "type_line": "Artifact Creature",
        "cmc": 4,
    }
    noncreature_token_card = {
        "name": "Academy Manufactor",
        "oracle_text": "If you would create a Clue, Food, or Treasure token, instead create one of each.",
        "type_line": "Artifact Creature",
        "cmc": 3,
    }

    assert engine._card_matches_synergy(token_maker, "board_conversion")
    assert engine._card_matches_commander_context(token_maker, "board_conversion", commander)
    assert engine._recommendation_quality_metadata(token_maker, "board_conversion", commander)["score"] >= 84
    assert "creature material" in engine._generate_commander_recommendation_reason(
        token_maker,
        commander["name"],
        "board_conversion",
        commander,
    )
    assert engine._card_matches_synergy(cheap_body, "board_conversion")
    assert engine._recommendation_quality_metadata(cheap_body, "board_conversion", commander)["score"] >= 84
    assert not engine._card_matches_commander_context(etb_value, "board_conversion", commander)
    assert engine._recommendation_quality_metadata(noncreature_token_card, "board_conversion", commander)["job"] == "early attacker"


def test_board_conversion_recommendation_search_returns_nonland_material():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Path of Ancestry",
            "oracle_text": "Add one mana of any color in your commander's color identity.",
            "type_line": "Land",
            "cmc": 0,
            "color_identity": [],
        },
        {
            "name": "Servo Engine",
            "oracle_text": "When Servo Engine enters the battlefield, create two 1/1 colorless Servo artifact creature tokens.",
            "type_line": "Artifact Creature",
            "cmc": 3,
            "color_identity": [],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Wide Board Converter",
        "oracle_text": "Other creatures you control have base power and toughness 4/2. Creatures you control attack each combat if able.",
        "type_line": "Legendary Creature",
        "color_identity": [],
    }

    cards = asyncio.run(engine._search_commander_recommendations(
        commander_card=commander,
        synergies=["board_conversion"],
        color_identity=[],
        commander_constraints=engine._get_commander_constraints(commander),
        max_cards=5,
        search_budget=1,
        per_synergy_limit=5,
        query_limit=10,
        minimum_score=84,
    ))

    assert [card["name"] for card in cards] == ["Servo Engine"]
    assert cards[0]["job"] == "wide-board material"
    assert cards[0]["evidence"] == "adds creature material for the commander to convert"


def test_deep_deck_analysis_is_visibly_distinct_from_fast_analysis():
    fake_scryfall = FakeScryfall()
    fake_scryfall.named_cards["Wide Board Converter"] = {
        "name": "Wide Board Converter",
        "oracle_text": "Other creatures you control have base power and toughness 4/2. Creatures you control attack each combat if able.",
        "type_line": "Legendary Creature",
        "color_identity": ["R"],
    }
    engine = EnhancedSuggestionEngine(fake_scryfall)
    cards = [
        {
            "name": "Mountain",
            "qty": 36,
            "type_line": "Basic Land - Mountain",
            "oracle_text": "",
            "cmc": 0,
            "colors": [],
            "tags": [],
        },
        {
            "name": "Servo Engine",
            "qty": 16,
            "type_line": "Artifact Creature",
            "oracle_text": "When Servo Engine enters the battlefield, create two 1/1 colorless Servo artifact creature tokens.",
            "cmc": 2,
            "colors": [],
            "tags": ["tokens"],
        },
        {
            "name": "Expensive Value Creature",
            "qty": 8,
            "type_line": "Creature",
            "oracle_text": "When this creature enters the battlefield, draw a card.",
            "cmc": 6,
            "colors": ["R"],
            "tags": [],
        },
    ]
    deck = {
        "name": "Deep Test",
        "commander": "Wide Board Converter",
        "cards": cards,
        "color_identity": ["R"],
    }

    fast = asyncio.run(engine.analyze_deck(deck, deep=False))
    deep = asyncio.run(engine.analyze_deck(deck, deep=True))

    assert fast["analysis_depth"] == "fast"
    assert deep["analysis_depth"] == "deep"
    assert len(deep["playstyle_tips"]) > len(fast["playstyle_tips"])
    assert any("Deep Analysis -" in tip for tip in deep["playstyle_tips"])


def test_double_faced_card_images_return_front_and_back():
    engine = make_engine()
    images = engine._get_card_images({
        "name": "Double Faced Test",
        "card_faces": [
            {"image_uris": {"normal": "front.jpg"}},
            {"image_uris": {"normal": "back.jpg"}},
        ],
    })

    assert images == {"front": "front.jpg", "back": "back.jpg"}


def test_sections_are_built_for_paged_strategy_and_recommendations():
    engine = make_engine()
    tips = [
        "Token engines need repeatable makers.",
        "Balance makers and payoffs.",
        "Use 36-38 lands and 10-12 ramp sources.",
        "Reserve 7-10 slots for answers and protection.",
        "Deep Strategy - Resource Loop: Check makers, outlets, and payoffs.",
    ]
    cards = [
        {"name": "Core A", "confidence": "core"},
        {"name": "Support A", "confidence": "support"},
        {"name": "More A", "confidence": "alternate"},
    ]

    strategy_sections = engine._build_strategy_sections(tips)
    recommendation_sections = engine._build_recommended_sections(cards)

    assert [section["id"] for section in strategy_sections] == ["game_plan", "foundation", "deep"]
    assert [section["id"] for section in recommendation_sections] == ["core", "support", "alternate"]
