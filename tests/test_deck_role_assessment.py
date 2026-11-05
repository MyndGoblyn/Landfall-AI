import asyncio
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.deck_role_assessment import DeckRoleAssessor
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


class NoopScryfall:
    pass


class RankedScryfall:
    def __init__(self, cards):
        self.cards = cards

    async def search_card(self, name):
        return None

    async def search_cards_by_criteria(self, query, limit=20):
        return self.cards[:limit]

    def extract_card_data(self, card):
        return {
            **card,
            "colors": card.get("colors", []),
            "prices": card.get("prices", {}),
        }


def _engine(mode="effective"):
    engine = EnhancedSuggestionEngine(NoopScryfall(), ranker_mode="legacy")
    engine.deck_role_assessment_mode = mode
    return engine


def _card(name, text, type_line="Instant", cmc=2, qty=1):
    return {
        "name": name,
        "oracle_text": text,
        "type_line": type_line,
        "cmc": cmc,
        "qty": qty,
    }


def test_conditional_cantrips_do_not_hide_a_draw_quality_gap():
    engine = _engine()
    cards = [
        _card(f"Cantrip {index}", "Draw a card.", cmc=1)
        for index in range(10)
    ]

    stats = engine._calculate_stats(cards, None, [])
    gaps = engine._identify_gaps(stats, [], [])
    draw = stats["role_quality"]["draw"]

    assert stats["role_counts"]["draw"] == 10
    assert draw["effective_count"] == 7.3
    assert draw["status"] == "quality_gap"
    assert draw["recommended_additions"] == 3
    assert gaps["roles"]["draw"] == 3
    assert "draw" in stats["hidden_role_quality_gaps"]


def test_reliable_repeatable_sources_satisfy_the_same_raw_count():
    engine = _engine()
    cards = [
        _card(
            f"Engine {index}",
            "At the beginning of your upkeep, draw a card.",
            type_line="Enchantment",
            cmc=2,
        )
        for index in range(10)
    ]

    stats = engine._calculate_stats(cards, None, [])
    gaps = engine._identify_gaps(stats, [], [])

    assert stats["role_quality"]["draw"]["effective_count"] == 10.0
    assert stats["role_quality"]["draw"]["status"] == "healthy"
    assert "draw" not in gaps["roles"]


def test_raw_mode_is_an_immediate_gap_detection_rollback():
    engine = _engine(mode="raw")
    cards = [
        _card(f"Cantrip {index}", "Draw a card.", cmc=1)
        for index in range(10)
    ]

    stats = engine._calculate_stats(cards, None, [])
    gaps = engine._identify_gaps(stats, [], [])

    assert stats["role_quality"]["draw"]["status"] == "quality_gap"
    assert "draw" not in gaps["roles"]
    assert gaps["effective_role_gaps"] == ["draw", "interaction", "protection", "ramp", "removal", "sweeper"]


def test_gap_shadow_telemetry_records_roles_without_deck_or_card_identity():
    engine = _engine(mode="shadow")
    cards = [
        _card(f"Cantrip {index}", "Draw a card.", cmc=1)
        for index in range(10)
    ]

    stats = engine._calculate_stats(cards, None, [])
    engine._identify_gaps(stats, [], [])
    status = engine.get_deck_role_status()

    assert status["counters"]["gap_comparisons"] == 1
    assert status["counters"]["changed_gap_sets"] == 1
    assert status["rates"]["changed_gap_sets"] == 1.0
    change = status["recent_gap_changes"][0]
    assert change["added_by_quality"] == ["draw"]
    assert set(change) == {
        "raw_gaps",
        "effective_gaps",
        "added_by_quality",
        "removed_by_quality",
    }


def test_marginal_utility_rewards_reliable_multi_role_gap_coverage():
    assessor = DeckRoleAssessor({"draw": (10, 12), "protection": (3, 5)})
    assessment = {
        "roles": {
            "draw": {"effective_count": 8.0, "effective_gap": 2.0, "target_min": 10},
            "protection": {"effective_count": 2.0, "effective_gap": 1.0, "target_min": 3},
        }
    }
    card = _card(
        "Protective Insight",
        "Target creature gains indestructible until end of turn. Draw two cards.",
        cmc=2,
    )

    utility = assessor.marginal_utility(
        card,
        assessment,
        detected_roles=["draw", "protection"],
        primary_role="draw",
    )

    assert utility["primary_gain"] >= 0.9
    assert utility["gap_roles"] == ["draw", "protection"]
    assert utility["score"] >= 90


def test_swap_pairing_does_not_cut_a_scarce_role_source():
    engine = _engine()
    scarce_protection = _card(
        "Only Protection",
        "Target creature gains indestructible until end of turn.",
        cmc=1,
    )
    off_plan = _card(
        "Off-plan Beater",
        "Vigilance.",
        type_line="Creature - Giant",
        cmc=6,
    )
    cards = [scarce_protection, off_plan]
    stats = engine._calculate_stats(cards, None, [])
    addition = {
        "card_name": "Reliable Draw",
        "role_tag": "draw",
        "cmc": 2,
        "confidence": 0.9,
        "role_gains": {"draw": 0.95},
    }
    cuts = [
        {
            "card_name": "Only Protection",
            "role_tag": "synergy_optimization",
            "cmc": 1,
            "confidence": 0.6,
        },
        {
            "card_name": "Off-plan Beater",
            "role_tag": "curve_optimization",
            "cmc": 6,
            "confidence": 0.75,
        },
    ]

    pairs = engine._pair_additions_with_safe_cuts([addition], cuts, cards, stats)

    assert pairs[0]["cut"]["card_name"] == "Off-plan Beater"
    assert "role floors intact" in pairs[0]["reason"]


def test_replacement_suggestion_ranks_the_pool_instead_of_returning_first_hit():
    search_results = [
        {
            "name": "Expensive Insight",
            "oracle_text": "At the beginning of your upkeep, draw a card.",
            "type_line": "Enchantment",
            "cmc": 7,
            "color_identity": ["U"],
        },
        {
            "name": "Reliable Insight",
            "oracle_text": "At the beginning of your upkeep, draw a card.",
            "type_line": "Enchantment",
            "cmc": 2,
            "color_identity": ["U"],
        },
    ]
    engine = EnhancedSuggestionEngine(
        RankedScryfall(search_results),
        ranker_mode="legacy",
    )
    deck = {
        "cards": [],
        "commander": None,
        "color_identity": ["U"],
    }

    replacement = asyncio.run(engine.get_replacement_suggestion(
        deck,
        dismissed_cards=[],
        role_tag="draw",
    ))

    assert replacement["card_name"] == "Reliable Insight"
    assert replacement["marginal_utility"] > 0
    assert "effective draw source" in replacement["reason"]
