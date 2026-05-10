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
    assert "id=bg" in query
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

    assert "id=c" in query
    assert "id=w" not in query


def test_random_commander_multicolor_filter_is_exact_and_canonical():
    engine = make_engine()

    query = engine._build_random_commander_query(colors=["R", "U"])

    assert "id=ur" in query
    assert "id<=ur" not in query
    assert "id=c" not in query


def test_random_commander_colored_filter_ignores_accidental_colorless_marker():
    engine = make_engine()

    query = engine._build_random_commander_query(colors=["C", "G"])

    assert "id=g" in query
    assert "id=c" not in query


def test_random_commander_fallback_preserves_selected_color_identity():
    class SequencedScryfall(FakeScryfall):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def search_cards_by_criteria(self, query, limit=20):
            self.queries.append((query, limit))
            self.calls += 1
            if self.calls == 2:
                return [{
                    "name": "Izzet Commander",
                    "type_line": "Legendary Creature - Wizard",
                    "oracle_text": "Whenever you cast an instant or sorcery spell, draw a card.",
                    "cmc": 3,
                    "colors": ["U", "R"],
                    "color_identity": ["U", "R"],
                    "legalities": {"commander": "legal"},
                }]
            return []

    fake = SequencedScryfall()
    engine = EnhancedSuggestionEngine(fake)

    result = asyncio.run(engine.get_random_commander(colors=["R", "U"], search_text="unlikely"))
    queries = [query for query, _limit in fake.queries[:2]]

    assert result["name"] == "Izzet Commander"
    assert all("id=ur" in query for query in queries)
    assert result["search_query"] == "is:commander t:creature f:commander id=ur"


def test_random_commander_scores_semantic_matches_above_loose_text_hits():
    engine = make_engine()
    intent = engine._random_commander_search_intent(search_text="artifact graveyard")
    artifact_graveyard_commander = {
        "name": "Artifact Graveyard Commander",
        "type_line": "Legendary Artifact Creature - Artificer",
        "oracle_text": (
            "Whenever an artifact card is put into your graveyard from anywhere, "
            "return another target artifact card from your graveyard to your hand."
        ),
        "cmc": 3,
        "color_identity": ["U", "B"],
    }
    loose_artifact_body = {
        "name": "Loose Artifact Body",
        "type_line": "Legendary Artifact Creature - Construct",
        "oracle_text": "Vigilance.",
        "cmc": 4,
        "color_identity": [],
    }

    strong = engine._score_random_commander_candidate(artifact_graveyard_commander, intent)
    loose = engine._score_random_commander_candidate(loose_artifact_body, intent)

    assert {"artifact", "graveyard"}.issubset(set(strong["matched_synergies"]))
    assert strong["score"] >= loose["score"] + 30


def test_random_commander_flash_search_prefers_real_reactive_engine():
    engine = make_engine()
    intent = engine._random_commander_search_intent(search_text="flash")
    flash_body = {
        "name": "Flash Body",
        "type_line": "Legendary Creature - Wizard",
        "oracle_text": "Flash.",
        "cmc": 4,
        "color_identity": ["U"],
    }
    flash_engine = {
        "name": "Reactive Flash Engine",
        "type_line": "Legendary Creature - Wizard",
        "oracle_text": (
            "Flash. You may cast creature spells as though they had flash. "
            "At the beginning of each end step, if you cast a spell this turn, draw a card."
        ),
        "cmc": 5,
        "color_identity": ["U", "G"],
    }

    body_score = engine._score_random_commander_candidate(flash_body, intent)
    engine_score = engine._score_random_commander_candidate(flash_engine, intent)
    ranked = engine._rank_random_commander_candidates([flash_body, flash_engine], intent)

    assert "flash_reactive_control" in engine_score["matched_archetypes"]
    assert "flash_control" in engine_score["matched_synergies"]
    assert body_score["matched_archetypes"] == []
    assert engine_score["score"] > body_score["score"]
    assert ranked[0]["card"]["name"] == "Reactive Flash Engine"


def test_random_commander_reuses_ranked_pool_for_same_filter():
    engine = make_engine()
    intent = engine._random_commander_search_intent(search_text="artifact graveyard")
    candidates = [
        {
            "name": "Artifact Graveyard Commander",
            "type_line": "Legendary Artifact Creature - Artificer",
            "oracle_text": (
                "Whenever an artifact card is put into your graveyard from anywhere, "
                "return another target artifact card from your graveyard to your hand."
            ),
            "cmc": 3,
            "color_identity": ["U", "B"],
            "legalities": {"commander": "legal"},
        },
        {
            "name": "Loose Artifact Body",
            "type_line": "Legendary Artifact Creature - Construct",
            "oracle_text": "Vigilance.",
            "cmc": 4,
            "color_identity": [],
            "legalities": {"commander": "legal"},
        },
    ]
    rank_calls = 0
    original_rank = engine._rank_random_commander_candidates

    def counting_rank(cards, ranking_intent):
        nonlocal rank_calls
        rank_calls += 1
        return original_rank(cards, ranking_intent)

    engine._rank_random_commander_candidates = counting_rank

    first = engine._select_random_commander_candidate(candidates, intent, query="cached-query")
    second = engine._select_random_commander_candidate(candidates, intent, query="cached-query")

    assert first["card"]["name"]
    assert second["card"]["name"]
    assert rank_calls == 1


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
    assert cards[0]["fit_tier"] == "Core Fit"
    assert "creature_token_support" in cards[0]["evidence_tags"]


def test_recommendation_quality_gate_rejects_wrong_token_type_for_creature_tokens():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Big Score",
            "oracle_text": "As an additional cost to cast this spell, discard a card. Draw two cards and create two Treasure tokens.",
            "type_line": "Instant",
            "cmc": 4,
            "color_identity": ["R"],
        },
        {
            "name": "Dragon Fodder",
            "oracle_text": "Create two 1/1 red Goblin creature tokens.",
            "type_line": "Sorcery",
            "cmc": 2,
            "color_identity": ["R"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Creature Token Commander",
        "oracle_text": "Whenever you create one or more creature tokens, draw a card.",
        "type_line": "Legendary Creature",
        "color_identity": ["R"],
    }

    cards = asyncio.run(engine._search_commander_recommendations(
        commander_card=commander,
        synergies=["tokens"],
        color_identity=["R"],
        commander_constraints=engine._get_commander_constraints(commander),
        max_cards=5,
        search_budget=1,
        per_synergy_limit=5,
        query_limit=10,
        minimum_score=72,
    ))

    assert [card["name"] for card in cards] == ["Dragon Fodder"]
    assert "creature_token_support" in cards[0]["evidence_tags"]
    assert "Treasure" not in cards[0]["reason"]


def test_commander_recommendations_score_full_batch_before_synergy_cap():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Wide Burn",
            "oracle_text": "Wide Burn deals X damage divided as you choose among any number of target creatures.",
            "type_line": "Sorcery",
            "cmc": 4,
            "color_identity": ["R"],
        },
        {
            "name": "Insightful Wide Burn",
            "oracle_text": "Insightful Wide Burn deals X damage divided as you choose among any number of target creatures. Draw a card.",
            "type_line": "Sorcery",
            "cmc": 4,
            "color_identity": ["R"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Target Cost Commander",
        "oracle_text": "Spells you cast cost {1} less to cast for each target.",
        "type_line": "Legendary Creature",
        "color_identity": ["R"],
    }

    cards = asyncio.run(engine._search_commander_recommendations(
        commander_card=commander,
        synergies=["target_spells"],
        color_identity=["R"],
        commander_constraints=engine._get_commander_constraints(commander),
        max_cards=1,
        search_budget=1,
        per_synergy_limit=1,
        query_limit=10,
        minimum_score=84,
    ))

    assert [card["name"] for card in cards] == ["Insightful Wide Burn"]
    assert "card_flow" in cards[0]["evidence_tags"]


def test_deck_analysis_scores_full_batch_before_accepting_additions():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Token Doubler",
            "oracle_text": "If you would create one or more tokens, create twice that many of those tokens instead.",
            "type_line": "Enchantment",
            "cmc": 4,
            "color_identity": ["G"],
        },
        {
            "name": "Insightful Token Doubler",
            "oracle_text": "If you would create one or more tokens, create twice that many of those tokens instead. Draw a card.",
            "type_line": "Enchantment",
            "cmc": 4,
            "color_identity": ["G"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Token Commander",
        "oracle_text": "Whenever you create one or more creature tokens, draw a card.",
        "type_line": "Legendary Creature",
        "color_identity": ["G"],
    }

    cards = asyncio.run(engine._generate_additions(
        gaps={"roles": {}, "lands": {}, "colors": {}, "synergy": ["tokens"]},
        commander="Token Commander",
        color_identity=["G"],
        current_cards=[],
        commander_synergies=["tokens"],
        commander_data=commander,
        categories=None,
        commander_constraints=engine._get_commander_constraints(commander),
        search_budget=1,
    ))

    assert cards[0]["card_name"] == "Insightful Token Doubler"
    assert "card_flow" in cards[0]["evidence_tags"]


def test_deck_analysis_rewards_role_fixes_that_overlap_commander_theme():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Generic Draw Spell",
            "oracle_text": "Draw two cards.",
            "type_line": "Sorcery",
            "cmc": 3,
            "color_identity": ["G"],
        },
        {
            "name": "Token Draw Engine",
            "oracle_text": "Whenever a creature token enters the battlefield under your control, draw a card.",
            "type_line": "Enchantment",
            "cmc": 3,
            "color_identity": ["G"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Token Commander",
        "oracle_text": "Whenever you create one or more creature tokens, draw a card.",
        "type_line": "Legendary Creature",
        "color_identity": ["G"],
    }

    cards = asyncio.run(engine._generate_additions(
        gaps={"roles": {"draw": 2}, "lands": {}, "colors": {}, "synergy": ["tokens"]},
        commander="Token Commander",
        color_identity=["G"],
        current_cards=[],
        commander_synergies=["tokens"],
        commander_data=commander,
        categories=["draw"],
        commander_constraints=engine._get_commander_constraints(commander),
        search_budget=1,
    ))

    assert cards[0]["card_name"] == "Token Draw Engine"
    assert "commander_theme_overlap" in cards[0]["evidence_tags"]


def test_deck_analysis_synergy_additions_exclude_lands():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Sacrifice Tower",
            "oracle_text": "{T}, Sacrifice a creature: Add {B}{B}.",
            "type_line": "Land",
            "cmc": 0,
            "color_identity": [],
        },
        {
            "name": "Sacrifice Outlet",
            "oracle_text": "Sacrifice a creature: Scry 1.",
            "type_line": "Creature",
            "cmc": 1,
            "color_identity": ["B"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)
    commander = {
        "name": "Sacrifice Commander",
        "oracle_text": "Whenever you sacrifice a creature, draw a card.",
        "type_line": "Legendary Creature",
        "color_identity": ["B"],
    }

    cards = asyncio.run(engine._generate_additions(
        gaps={"roles": {}, "lands": {}, "colors": {}, "synergy": ["sacrifice"]},
        commander="Sacrifice Commander",
        color_identity=["B"],
        current_cards=[],
        commander_synergies=["sacrifice"],
        commander_data=commander,
        categories=None,
        commander_constraints=engine._get_commander_constraints(commander),
        search_budget=1,
    ))

    assert [card["card_name"] for card in cards] == ["Sacrifice Outlet"]


def test_deck_analysis_role_additions_exclude_lands():
    fake_scryfall = FakeScryfall()
    fake_scryfall.results = [
        {
            "name": "Fetch Land",
            "oracle_text": "{T}, Sacrifice Fetch Land: Search your library for a basic land card.",
            "type_line": "Land",
            "cmc": 0,
            "color_identity": [],
        },
        {
            "name": "Ramp Spell",
            "oracle_text": "Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.",
            "type_line": "Sorcery",
            "cmc": 2,
            "color_identity": ["G"],
        },
    ]
    engine = EnhancedSuggestionEngine(fake_scryfall)

    cards = asyncio.run(engine._generate_additions(
        gaps={"roles": {"ramp": 2}, "lands": {}, "colors": {}, "synergy": []},
        commander=None,
        color_identity=["G"],
        current_cards=[],
        commander_synergies=[],
        commander_data=None,
        categories=["ramp"],
        commander_constraints={"commander_color_identity": ["G"]},
        search_budget=1,
    ))

    assert [card["card_name"] for card in cards] == ["Ramp Spell"]


def test_deck_analysis_cut_suggestions_flag_redundant_off_theme_roles():
    fake_scryfall = FakeScryfall()
    engine = EnhancedSuggestionEngine(fake_scryfall)
    redundant_draw = {
        "name": "Off Theme Draw Engine",
        "oracle_text": "At the beginning of your upkeep, draw a card.",
        "type_line": "Enchantment",
        "cmc": 3,
        "tags": [],
    }
    cards = [redundant_draw] + [
        {
            "name": f"Cheap Draw {index}",
            "oracle_text": "Draw a card.",
            "type_line": "Instant",
            "cmc": 1,
            "tags": [],
        }
        for index in range(13)
    ]
    stats = {"role_counts": {"draw": 13}}

    cuts = asyncio.run(engine._generate_cuts(
        cards=cards,
        gaps={"roles": {}, "lands": {}},
        stats=stats,
        commander_synergies=["tokens"],
        detected_themes=["tokens"],
    ))

    assert cuts[0]["card_name"] == "Off Theme Draw Engine"
    assert cuts[0]["role_tag"] == "role_redundancy"
    assert "already has enough" in cuts[0]["reason"]


def test_recommendation_selection_applies_soft_job_diversity():
    engine = make_engine()
    candidates = [
        {"name": "First Outlet", "score": 90, "job": "sacrifice outlet", "role": "sacrifice", "fit_tier": "Core Fit", "confidence": "core", "evidence_tags": ["direct_synergy"], "penalty_tags": [], "cmc": 2, "_source_rank": 0, "_synergy_index": 0},
        {"name": "Second Outlet", "score": 90, "job": "sacrifice outlet", "role": "sacrifice", "fit_tier": "Core Fit", "confidence": "core", "evidence_tags": ["direct_synergy"], "penalty_tags": [], "cmc": 2, "_source_rank": 1, "_synergy_index": 0},
        {"name": "Third Outlet", "score": 90, "job": "sacrifice outlet", "role": "sacrifice", "fit_tier": "Core Fit", "confidence": "core", "evidence_tags": ["direct_synergy"], "penalty_tags": [], "cmc": 2, "_source_rank": 2, "_synergy_index": 0},
        {"name": "Token Payoff", "score": 89, "job": "token payoff", "role": "tokens", "fit_tier": "Core Fit", "confidence": "core", "evidence_tags": ["direct_synergy"], "penalty_tags": [], "cmc": 3, "_source_rank": 3, "_synergy_index": 1},
    ]

    selected = engine._select_ranked_recommendations(candidates, 3)

    assert [card["name"] for card in selected] == ["First Outlet", "Token Payoff", "Second Outlet"]


def test_recommendation_quality_gate_marks_loose_counter_matches_speculative():
    engine = make_engine()
    commander = {
        "name": "Named Counter Commander",
        "oracle_text": "Whenever this creature attacks, put a blight counter on target creature. Then proliferate.",
        "type_line": "Legendary Creature",
        "color_identity": [],
    }
    loose_counter_card = {
        "name": "Random Counter Trick",
        "oracle_text": "Put a +1/+1 counter on target creature.",
        "type_line": "Instant",
        "cmc": 1,
    }

    quality = engine._recommendation_quality_metadata(loose_counter_card, "counters", commander)

    assert quality["fit_tier"] == "Speculative"
    assert "wrong_counter_context" in quality["penalty_tags"]
    assert quality["score"] < 72


def test_role_fix_reason_does_not_claim_commander_synergy():
    engine = make_engine()
    gaps = {"roles": {"draw": 3}}
    draw_card = {
        "name": "Read the Bones",
        "oracle_text": "Scry 2, then draw two cards. You lose 2 life.",
        "type_line": "Sorcery",
        "cmc": 3,
    }

    quality = engine._role_recommendation_quality_metadata(draw_card, "draw", gaps)
    reason = engine._generate_validated_role_reason(draw_card, "draw", quality)

    assert quality["fit_tier"] in {"Role Fix", "Strong Role Fix"}
    assert "role" in reason.lower()
    assert "commander-specific synergy" not in reason.lower()


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


def test_enchantment_recommendation_reasons_name_actual_evidence():
    engine = make_engine()
    commander = {
        "name": "Zur the Enchanter",
        "oracle_text": (
            "Flying. Whenever Zur the Enchanter attacks, you may search your library "
            "for an enchantment card with mana value 3 or less, put it onto the battlefield, then shuffle."
        ),
        "type_line": "Legendary Creature - Human Wizard",
        "color_identity": ["W", "U", "B"],
    }
    curiosity = {
        "name": "Curiosity",
        "oracle_text": "Enchant creature. Whenever enchanted creature deals damage to an opponent, you may draw a card.",
        "type_line": "Enchantment - Aura",
        "cmc": 1,
    }

    quality = engine._recommendation_quality_metadata(curiosity, "enchantment", commander)
    reason = engine._generate_validated_recommendation_reason(
        curiosity,
        commander["name"],
        "enchantment",
        quality,
        commander,
    )

    assert quality["job"] == "card-draw aura"
    assert "tutorable_enchantment" in quality["evidence_tags"]
    assert "validated match" not in reason
    assert "supports the enchantment package" not in reason
    assert "card-draw Aura" in reason
    assert "mana value 1" in reason
    assert "combat damage into extra cards" in reason


def test_zur_non_aura_enchantments_can_clear_quality_gate_with_specific_roles():
    engine = make_engine()
    commander = {
        "name": "Zur the Enchanter",
        "oracle_text": (
            "Flying. Whenever Zur the Enchanter attacks, you may search your library "
            "for an enchantment card with mana value 3 or less, put it onto the battlefield, then shuffle."
        ),
        "type_line": "Legendary Creature - Human Wizard",
        "color_identity": ["W", "U", "B"],
    }
    mystic_remora = {
        "name": "Mystic Remora",
        "oracle_text": "Cumulative upkeep {1}. Whenever an opponent casts a noncreature spell, you may draw a card unless that player pays {4}.",
        "type_line": "Enchantment",
        "cmc": 1,
    }

    quality = engine._recommendation_quality_metadata(mystic_remora, "enchantment", commander)
    reason = engine._generate_validated_recommendation_reason(
        mystic_remora,
        commander["name"],
        "enchantment",
        quality,
        commander,
    )

    assert engine._card_matches_synergy(mystic_remora, "enchantment")
    assert quality["score"] >= 84
    assert quality["job"] == "tutorable card flow"
    assert "tutorable enchantment card flow" in reason
    assert "random draw step" in reason


def test_validated_recommendation_reasons_are_not_circular_across_synergies():
    engine = make_engine()
    cases = [
        (
            "artifact",
            {
                "name": "Artifact Commander",
                "oracle_text": "Whenever an artifact enters the battlefield under your control, draw a card.",
                "type_line": "Legendary Creature - Artificer",
                "color_identity": ["U"],
            },
            {
                "name": "Thought Monitor",
                "oracle_text": "Affinity for artifacts. Flying. When Thought Monitor enters the battlefield, draw two cards.",
                "type_line": "Artifact Creature - Construct",
                "cmc": 7,
            },
        ),
        (
            "creature",
            {
                "name": "Creature Commander",
                "oracle_text": "Whenever you cast a creature spell, draw a card.",
                "type_line": "Legendary Creature - Druid",
                "color_identity": ["G"],
            },
            {
                "name": "Elvish Visionary",
                "oracle_text": "When Elvish Visionary enters the battlefield, draw a card.",
                "type_line": "Creature - Elf Shaman",
                "cmc": 2,
            },
        ),
        (
            "board_conversion",
            {
                "name": "Board Commander",
                "oracle_text": "Creatures you control have base power and toughness 5/3 and are Juggernauts in addition to their other types.",
                "type_line": "Legendary Artifact Creature - Juggernaut",
                "color_identity": [],
            },
            {
                "name": "Myr Battlesphere",
                "oracle_text": "When Myr Battlesphere enters the battlefield, create four 1/1 colorless Myr artifact creature tokens.",
                "type_line": "Artifact Creature - Myr Construct",
                "cmc": 7,
            },
        ),
        (
            "sacrifice",
            {
                "name": "Sacrifice Commander",
                "oracle_text": "Whenever you sacrifice a creature, each opponent loses 1 life.",
                "type_line": "Legendary Creature - Vampire",
                "color_identity": ["B"],
            },
            {
                "name": "Viscera Seer",
                "oracle_text": "Sacrifice a creature: Scry 1.",
                "type_line": "Creature - Vampire Wizard",
                "cmc": 1,
            },
        ),
        (
            "counters",
            {
                "name": "Counter Commander",
                "oracle_text": "Whenever you proliferate, put a +1/+1 counter on target creature.",
                "type_line": "Legendary Creature - Advisor",
                "color_identity": ["G", "U"],
            },
            {
                "name": "Evolution Sage",
                "oracle_text": "Landfall - Whenever a land enters the battlefield under your control, proliferate.",
                "type_line": "Creature - Elf Druid",
                "cmc": 3,
            },
        ),
        (
            "blink",
            {
                "name": "Blink Commander",
                "oracle_text": "Whenever one or more permanents you control leave the battlefield, draw a card.",
                "type_line": "Legendary Creature - Spirit",
                "color_identity": ["W", "U"],
            },
            {
                "name": "Mulldrifter",
                "oracle_text": "Flying. When Mulldrifter enters the battlefield, draw two cards.",
                "type_line": "Creature - Elemental",
                "cmc": 5,
            },
        ),
        (
            "tokens",
            {
                "name": "Token Commander",
                "oracle_text": "Whenever one or more creature tokens enter under your control, put a +1/+1 counter on each creature you control.",
                "type_line": "Legendary Creature - Soldier",
                "color_identity": ["G", "W"],
            },
            {
                "name": "Adeline, Resplendent Cathar",
                "oracle_text": "Whenever you attack, for each opponent, create a 1/1 white Human creature token tapped and attacking.",
                "type_line": "Legendary Creature - Human Knight",
                "cmc": 3,
            },
        ),
        (
            "artifact_tokens",
            {
                "name": "Treasure Commander",
                "oracle_text": "Whenever you sacrifice an artifact, draw a card.",
                "type_line": "Legendary Creature - Pirate",
                "color_identity": ["R", "B"],
            },
            {
                "name": "Professional Face-Breaker",
                "oracle_text": "Whenever one or more creatures you control deal combat damage to a player, create a Treasure token.",
                "type_line": "Creature - Human Warrior",
                "cmc": 3,
            },
        ),
        (
            "exile",
            {
                "name": "Exile Commander",
                "oracle_text": "Whenever you cast a spell from exile, create a Treasure token.",
                "type_line": "Legendary Creature - Wizard",
                "color_identity": ["R"],
            },
            {
                "name": "Light Up the Stage",
                "oracle_text": "Exile the top two cards of your library. Until the end of your next turn, you may play those cards.",
                "type_line": "Sorcery",
                "cmc": 3,
            },
        ),
        (
            "landfall",
            {
                "name": "Landfall Commander",
                "oracle_text": "Landfall - Whenever a land enters the battlefield under your control, draw a card.",
                "type_line": "Legendary Creature - Elemental",
                "color_identity": ["G", "U"],
            },
            {
                "name": "Azusa, Lost but Seeking",
                "oracle_text": "You may play two additional lands on each of your turns.",
                "type_line": "Legendary Creature - Human Monk",
                "cmc": 3,
            },
        ),
        (
            "lifegain",
            {
                "name": "Life Commander",
                "oracle_text": "Whenever you gain life, put a +1/+1 counter on target creature.",
                "type_line": "Legendary Creature - Cleric",
                "color_identity": ["W", "B"],
            },
            {
                "name": "Ajani's Pridemate",
                "oracle_text": "Whenever you gain life, put a +1/+1 counter on Ajani's Pridemate.",
                "type_line": "Creature - Cat Soldier",
                "cmc": 2,
            },
        ),
        (
            "instant_sorcery",
            {
                "name": "Spell Commander",
                "oracle_text": "Whenever you cast an instant or sorcery spell, create a 1/1 creature token.",
                "type_line": "Legendary Creature - Wizard",
                "color_identity": ["U", "R"],
            },
            {
                "name": "Young Pyromancer",
                "oracle_text": "Whenever you cast an instant or sorcery spell, create a 1/1 red Elemental creature token.",
                "type_line": "Creature - Human Shaman",
                "cmc": 2,
            },
        ),
        (
            "voltron",
            {
                "name": "Voltron Commander",
                "oracle_text": "Whenever this creature deals combat damage to a player, draw a card.",
                "type_line": "Legendary Creature - Warrior",
                "color_identity": ["W"],
            },
            {
                "name": "Lightning Greaves",
                "oracle_text": "Equipped creature has haste and shroud. Equip 0.",
                "type_line": "Artifact - Equipment",
                "cmc": 2,
            },
        ),
    ]
    banned_fragments = [
        "validated match",
        "fits because it fits",
        "supports the package",
        "supports the enchantment package",
        "fills the",
        "is an enabler for the deck's",
    ]

    for synergy, commander, card in cases:
        quality = engine._recommendation_quality_metadata(card, synergy, commander)
        reason = engine._generate_validated_recommendation_reason(
            card,
            commander["name"],
            synergy,
            quality,
            commander,
        )
        lowered = reason.lower()

        assert len(reason.split()) >= 18, synergy
        assert card["name"] in reason, synergy
        assert commander["name"] in reason, synergy
        for fragment in banned_fragments:
            assert fragment not in lowered, (synergy, reason)


def test_mechanics_registry_loads_and_expands_search_terms():
    engine = make_engine()

    assert engine.mechanics_registry.count() >= 290
    bargain_query = engine.mechanics_registry.query_for_term("bargain")
    random_query = engine._build_random_commander_query(search_text="bargain")

    assert bargain_query
    assert bargain_query in random_query
    assert "(t:bargain OR o:bargain)" not in random_query


def test_registry_does_not_turn_flying_alone_into_a_theme():
    engine = make_engine()
    commander = {
        "name": "Flying Only Commander",
        "oracle_text": "Flying.",
        "type_line": "Legendary Creature - Bird",
        "color_identity": ["U"],
    }

    synergies = engine._detect_commander_synergies(commander)

    assert "voltron" not in synergies
    assert "counters" not in synergies


def test_registry_mechanic_focus_adds_specific_strategy_language():
    engine = make_engine()
    commander = {
        "name": "Bargain Commander",
        "oracle_text": "Bargain. Whenever you sacrifice an artifact, enchantment, or token, draw a card.",
        "type_line": "Legendary Creature - Warlock",
        "color_identity": ["B"],
    }

    synergies = engine._detect_commander_synergies(commander)
    tips = engine._generate_commander_strategy_tips(
        commander,
        synergies,
        engine._get_commander_constraints(commander),
    )

    assert "sacrifice" in synergies
    assert any("Mechanic Focus - Bargain" in tip for tip in tips)
    assert any("fodder" in tip.lower() or "sacrifice" in tip.lower() for tip in tips)


def test_reason_builder_names_exact_mechanic_when_it_adds_evidence():
    engine = make_engine()
    commander = {
        "name": "Artifact Token Commander",
        "oracle_text": "Whenever you sacrifice an artifact, draw a card.",
        "type_line": "Legendary Creature - Pirate",
        "color_identity": ["R", "B"],
    }
    card = {
        "name": "Professional Face-Breaker",
        "oracle_text": "Whenever one or more creatures you control deal combat damage to a player, create a Treasure token.",
        "type_line": "Creature - Human Warrior",
        "cmc": 3,
    }

    quality = engine._recommendation_quality_metadata(card, "artifact_tokens", commander)
    reason = engine._generate_validated_recommendation_reason(
        card,
        commander["name"],
        "artifact_tokens",
        quality,
        commander,
    )

    assert quality["mechanic"] == "Treasure"
    assert "Treasure" in reason
    assert "concrete evidence" in reason
    assert "validated match" not in reason


def test_archetype_registry_loads_composite_strategy_layer():
    engine = make_engine()

    assert engine.archetype_registry.count() >= 25
    archetype_ids = {entry.get("id") for entry in engine.archetype_registry.entries}

    assert "late_game_control_finisher" in archetype_ids
    assert "flash_reactive_control" in archetype_ids
    assert "hand_size_pressure_control" in archetype_ids
    assert "vanilla_creature_matters" in archetype_ids


def test_composite_control_finisher_detection_is_not_commander_specific():
    engine = make_engine()
    commander = {
        "name": "Synthetic Praetor",
        "type_line": "Legendary Creature - Praetor",
        "oracle_text": (
            "Flash. At the beginning of your end step, draw seven cards. "
            "Each opponent's maximum hand size is reduced by seven."
        ),
        "cmc": 10,
        "color_identity": ["U"],
    }

    signals = engine._extract_archetype_signals(commander)
    archetypes = {match["id"] for match in engine._detect_commander_archetypes(commander)}
    synergies = engine._detect_commander_synergies(commander)
    tips = engine._generate_commander_strategy_tips(
        commander,
        synergies,
        engine._get_commander_constraints(commander),
    )
    joined = " ".join(tips).lower()

    assert "high_mana_value_commander" in signals
    assert "large_card_draw" in signals
    assert "opponent_hand_size_pressure" in signals
    assert "late_game_control_finisher" in archetypes
    assert "hand_size_pressure_control" in archetypes
    assert "flash_reactive_control" in archetypes
    assert "control_finisher" in synergies
    assert "hand_size_pressure" in synergies
    assert "flash_control" in synergies
    assert "instant_sorcery" not in synergies
    assert "late-game control finisher" in joined
    assert "cheap cantrips" not in joined


def test_flash_alone_does_not_create_spell_trigger_plan():
    engine = make_engine()
    commander = {
        "name": "Flash Body",
        "type_line": "Legendary Creature - Wizard",
        "oracle_text": "Flash.",
        "cmc": 4,
        "color_identity": ["U"],
    }

    synergies = engine._detect_commander_synergies(commander)
    archetypes = engine._detect_commander_archetypes(commander)

    assert "instant_sorcery" not in synergies
    assert "flash_control" not in synergies
    assert archetypes == []


def test_hand_size_pressure_rejects_self_discard_looting():
    engine = make_engine()
    commander = {
        "name": "Hand Pressure Commander",
        "type_line": "Legendary Creature",
        "oracle_text": "Each opponent's maximum hand size is reduced by seven.",
        "cmc": 6,
        "color_identity": ["U"],
    }
    mask_of_memory = {
        "name": "Mask of Memory",
        "type_line": "Artifact - Equipment",
        "oracle_text": (
            "Whenever equipped creature deals combat damage to a player, "
            "you may draw two cards. If you do, discard a card."
        ),
        "cmc": 2,
    }

    assert not engine._card_matches_synergy(mask_of_memory, "hand_size_pressure")

    quality = engine._recommendation_quality_metadata(
        mask_of_memory,
        "hand_size_pressure",
        commander,
    )

    assert quality["score"] < 76
    assert quality["fit_tier"] == "Speculative"


def test_no_maximum_hand_size_is_not_opponent_hand_pressure():
    engine = make_engine()
    commander = {
        "name": "Hand Pressure Commander",
        "type_line": "Legendary Creature",
        "oracle_text": "Each opponent's maximum hand size is reduced by seven.",
        "cmc": 6,
        "color_identity": ["U"],
    }
    support_card = {
        "name": "Large Hand Support",
        "type_line": "Creature",
        "oracle_text": "You have no maximum hand size. Whenever an opponent casts a noncreature spell, draw a card.",
        "cmc": 7,
    }

    quality = engine._recommendation_quality_metadata(
        support_card,
        "hand_size_pressure",
        commander,
    )

    assert quality["job"] == "large-hand support"
    assert quality["score"] < 84
    assert "direct_synergy" not in quality["evidence_tags"]


def test_self_forced_attack_is_not_goad_or_forced_combat():
    engine = make_engine()
    toski_like = {
        "name": "Self Forced Attack Commander",
        "type_line": "Legendary Creature - Squirrel",
        "oracle_text": (
            "This spell can't be countered. Indestructible. "
            "Self Forced Attack Commander attacks each combat if able. "
            "Whenever a creature you control deals combat damage to a player, draw a card."
        ),
        "color_identity": ["G"],
    }
    true_goad = "Whenever this creature deals combat damage to a player, goad target creature that player controls."

    synergies = engine._detect_commander_synergies(toski_like)
    signals = engine._extract_archetype_signals(toski_like)

    assert "goad" not in synergies
    assert "forced_combat" not in signals
    assert "self_forced_attack_drawback" in signals
    assert engine._has_true_goad_text(true_goad)


def test_exile_zone_counters_do_not_become_counter_or_proliferate_plan():
    engine = make_engine()
    grolnok_like = {
        "name": "Zone Counter Commander",
        "type_line": "Legendary Creature - Frog",
        "oracle_text": (
            "Whenever a Frog you control attacks, mill three cards. "
            "Whenever a permanent card is put into your graveyard from your library, exile it with a croak counter on it. "
            "You may play lands and cast spells from among cards you own in exile with croak counters on them."
        ),
        "color_identity": ["G", "U"],
    }
    evolution_sage = {
        "name": "Evolution Sage",
        "type_line": "Creature - Elf Druid",
        "oracle_text": "Landfall - Whenever a land enters the battlefield under your control, proliferate.",
        "cmc": 3,
    }

    synergies = engine._detect_commander_synergies(grolnok_like)
    archetypes = engine._detect_commander_archetypes(grolnok_like)
    constraints = engine._get_commander_constraints(grolnok_like)
    tips = engine._generate_commander_strategy_tips(grolnok_like, synergies, constraints)
    joined = " ".join(tips).lower()

    assert engine._counter_plan_for_text(engine._combined_oracle_text(grolnok_like)) == "zone_counters"
    assert "counters" not in synergies
    assert "exile" in synergies
    assert "graveyard_reanimator" not in {archetype["id"] for archetype in archetypes}
    assert "graveyard_recursion" not in engine._extract_archetype_signals(grolnok_like)
    assert constraints["zone_counter_plan"] is True
    assert "counter_plan" not in constraints
    assert not engine._card_matches_commander_context(evolution_sage, "counters", grolnok_like)
    assert "proliferate" not in joined


def test_timing_drawback_text_does_not_create_generic_exile_card_access():
    engine = make_engine()
    timing_commander = {
        "name": "Timing Commander",
        "type_line": "Legendary Creature",
        "oracle_text": (
            "Tap: End the turn. "
            "Whenever you create a token, exile it at the beginning of the next end step."
        ),
        "color_identity": ["U", "B"],
    }

    synergies = engine._detect_commander_synergies(timing_commander)
    tips = engine._generate_commander_strategy_tips(
        timing_commander,
        synergies,
        engine._get_commander_constraints(timing_commander),
    )
    joined = " ".join(tips).lower()

    assert "temporary_drawback" in synergies
    assert "exile" not in synergies
    assert "exile should be treated as card access" not in joined


def test_vanilla_creature_plan_rejects_normal_value_creatures():
    engine = make_engine()
    ruxa_like = {
        "name": "No-Ability Commander",
        "type_line": "Legendary Creature - Bear",
        "oracle_text": (
            "When No-Ability Commander enters the battlefield, return target creature card with no abilities "
            "from your graveyard to your hand. Creatures you control with no abilities get +1/+1. "
            "You may have creatures you control with no abilities assign their combat damage as though they weren't blocked."
        ),
        "color_identity": ["G"],
    }
    normal_value_creature = {
        "name": "Elvish Visionary",
        "type_line": "Creature - Elf Shaman",
        "oracle_text": "When Elvish Visionary enters the battlefield, draw a card.",
        "cmc": 2,
    }
    vanilla_body = {
        "name": "Gigantosaurus",
        "type_line": "Creature - Dinosaur",
        "oracle_text": "",
        "cmc": 5,
    }
    vanilla_payoff = {
        "name": "Muraganda Petroglyphs",
        "type_line": "Enchantment",
        "oracle_text": "Creatures with no abilities get +2/+2.",
        "cmc": 4,
    }

    synergies = engine._detect_commander_synergies(ruxa_like)
    archetypes = engine._detect_commander_archetypes(ruxa_like)
    payoff_quality = engine._recommendation_quality_metadata(vanilla_payoff, "vanilla_creatures", ruxa_like)
    body_quality = engine._recommendation_quality_metadata(vanilla_body, "vanilla_creatures", ruxa_like)

    assert synergies[0] == "vanilla_creatures"
    assert archetypes[0]["id"] == "vanilla_creature_matters"
    assert not engine._card_matches_commander_context(normal_value_creature, "creature", ruxa_like)
    assert engine._card_matches_commander_context(vanilla_body, "creature", ruxa_like)
    assert engine._card_matches_synergy(vanilla_payoff, "vanilla_creatures")
    assert payoff_quality["job"] == "no-ability payoff"
    assert body_quality["job"] == "no-ability creature"


def test_donation_archetype_outranks_incidental_combat_and_counters():
    engine = make_engine()
    jon_like = {
        "name": "Control Exchange Commander",
        "type_line": "Legendary Creature - Human Wizard",
        "oracle_text": (
            "At the beginning of your end step, target opponent gains control of up to one target creature you control. "
            "Put two +1/+1 counters on it and tap it. It's goaded for the rest of the game and gains "
            "\"This creature can't be sacrificed.\" Whenever a creature you own but don't control attacks, you draw a card."
        ),
        "color_identity": ["U", "B"],
    }

    archetypes = engine._detect_commander_archetypes(jon_like)
    synergies = engine._detect_commander_synergies(jon_like)
    tips = engine._generate_commander_strategy_tips(
        jon_like,
        synergies,
        engine._get_commander_constraints(jon_like),
    )
    joined = " ".join(tips).lower()

    assert archetypes[0]["id"] == "donation_drawback_abuse"
    assert synergies[0] == "donation"
    assert "goad" in synergies
    assert "control-exchange plan" in joined
    assert "counter cards" not in joined
