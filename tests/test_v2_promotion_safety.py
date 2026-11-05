import asyncio
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_intent import (
    apply_intent_to_suggestion,
    build_budget_context,
    normalize_intent_profile,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


class StaticScryfall:
    def __init__(self, results=None, by_name=None):
        self.results = list(results or [])
        self.by_name = {
            name.casefold(): card for name, card in (by_name or {}).items()
        }

    async def search_cards_by_criteria(self, query, limit=20):
        return self.results[:limit]

    async def search_card(self, name, fuzzy=True):
        del fuzzy
        return self.by_name.get(str(name).casefold())

    def extract_card_data(self, card):
        return {
            "name": card.get("name"),
            "type_line": card.get("type_line", ""),
            "oracle_text": card.get("oracle_text", ""),
            "cmc": card.get("cmc", 0),
            "colors": card.get("colors", []),
            "color_identity": card.get("color_identity", []),
            "prices": card.get("prices", {}),
            "legalities": card.get("legalities", {"commander": "legal"}),
        }


def candidate(name, text="Draw a card.", cmc=2, price="0.25"):
    return {
        "name": name,
        "type_line": "Instant",
        "oracle_text": text,
        "mana_cost": "{1}{U}",
        "cmc": cmc,
        "colors": ["U"],
        "color_identity": ["U"],
        "prices": {"usd": price},
        "legalities": {"commander": "legal"},
    }


def test_active_commander_is_excluded_before_either_ranker():
    commander = candidate("Grist, the Hunger Tide")
    valid = candidate("Quick Study", "Draw two cards.", cmc=3)
    engine = EnhancedSuggestionEngine(StaticScryfall([commander, valid]), ranker_mode="v2")

    results = asyncio.run(engine._generate_additions(
        gaps={"roles": {"draw": 2}, "lands": {}, "synergy": []},
        commander="Grist, the Hunger Tide",
        color_identity=["U"],
        current_cards=[],
        commander_synergies=[],
        commander_data=commander,
        categories=["draw"],
        commander_constraints={"commander_color_identity": ["U"]},
        search_budget=1,
    ))

    assert "Grist, the Hunger Tide" not in {
        row["card_name"] for row in results
    }


def test_confirmed_negative_cedh_language_does_not_enable_competitive_lane():
    profile = normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "tune",
        "primary_strategy": "Budget Ninja typal tempo",
        "desired_experience": "Improve it without converting the list into cEDH.",
    })

    assert "competitive" not in profile["strategy_priorities"]
    assert "cedh" not in profile["experience_tags"]


def test_total_budget_context_penalizes_large_single_card_share():
    profile = normalize_intent_profile({
        "confirmed": True,
        "optimization_mode": "tune",
        "budget_mode": "target",
        "budget_limit_usd": 25,
    })
    context = build_budget_context([], profile)
    result = apply_intent_to_suggestion(
        {
            "card_name": "Expensive Upgrade",
            "role_tag": "draw",
            "cmc": 2,
            "price": 8,
            "score": 90,
            "confidence": 0.9,
            "evidence_tags": ["direct_synergy"],
            "penalty_tags": [],
            "reason": "Draw engine.",
        },
        {"name": "Expensive Upgrade", "oracle_text": "Draw a card.", "cmc": 2},
        profile,
        budget_context=context,
    )

    assert result["budget_ratio"] == 0.32
    assert "total_budget_outlier" in result["penalty_tags"]
    assert result["score"] == 62


def test_budget_text_without_numeric_cap_uses_disclosed_soft_proxy():
    profile = normalize_intent_profile({
        "confirmed": True,
        "budget_mode": "target",
        "optimization_mode": "competitive",
        "primary_strategy": "Budget spell-chain storm",
        "desired_experience": "Retain budget spell-chain lines.",
    })
    context = build_budget_context([], profile)
    assert context["proxy_card_target_usd"] == 10

    result = apply_intent_to_suggestion(
        {
            "card_name": "Premium Generic Spell",
            "price": 30,
            "score": 80,
            "confidence": 0.9,
            "role_tag": "interaction",
            "evidence_tags": ["competitive_evidence"],
        },
        {
            "name": "Premium Generic Spell",
            "oracle_text": "Counter target spell.",
            "cmc": 1,
        },
        profile,
        budget_context=context,
    )

    assert result["budget_proxy_card_target_usd"] == 10
    assert "implicit_budget_outlier" in result["penalty_tags"]
    assert result["confidence"] <= 0.54
    assert result["score"] == 58

    unpriced = apply_intent_to_suggestion(
        {
            "card_name": "Unpriced Premium Spell",
            "score": 80,
            "confidence": 0.9,
            "role_tag": "interaction",
            "evidence_tags": ["competitive_evidence"],
        },
        {
            "name": "Unpriced Premium Spell",
            "oracle_text": "Counter target spell.",
            "cmc": 1,
        },
        profile,
        budget_context=context,
    )
    assert "implicit_budget_unpriced" in unpriced["penalty_tags"]
    assert unpriced["confidence"] <= 0.56


def test_low_power_preservation_rejects_curated_power_outlier():
    profile = normalize_intent_profile({
        "confirmed": True,
        "power_level_max": 4,
        "optimization_mode": "preserve",
        "intentional_constraints": ["intentional_jank"],
    })
    result = apply_intent_to_suggestion(
        {
            "card_name": "Gilded Drake",
            "role_tag": "donation",
            "cmc": 2,
            "price": 100,
            "score": 90,
            "confidence": 0.9,
            "evidence_tags": ["direct_synergy"],
            "penalty_tags": [],
            "reason": "Exchange control.",
        },
        {"name": "Gilded Drake", "oracle_text": "Exchange control."},
        profile,
        power_outlier=True,
    )

    assert result is None


def test_semantic_hydration_protects_transform_engine_from_cut():
    urabrask = {
        "name": "Urabrask // The Great Work",
        "type_line": "Legendary Creature — Praetor",
        "oracle_text": "",
        "cmc": 4,
    }
    hydrated = {
        **urabrask,
        "card_faces": [{
            "name": "Urabrask",
            "type_line": "Legendary Creature — Praetor",
            "oracle_text": (
                "Whenever you cast an instant or sorcery spell, add {R}."
            ),
        }],
    }
    engine = EnhancedSuggestionEngine(
        StaticScryfall(by_name={urabrask["name"]: hydrated})
    )
    cards = asyncio.run(engine._hydrate_semantic_cards([urabrask]))
    cuts = asyncio.run(engine._generate_cuts(
        cards,
        {"roles": {}, "lands": {}},
        {"role_counts": {}, "role_quality": {}},
        ["instant_sorcery"],
        ["spellslinger"],
        normalize_intent_profile({
            "confirmed": True,
            "primary_strategy": "spell-chain storm",
        }),
    ))

    assert cards[0].get("card_faces")
    assert not cuts


def test_self_only_protection_keyword_is_not_a_deck_protection_source():
    engine = EnhancedSuggestionEngine(StaticScryfall())

    assert not engine._has_protection_role_text(
        "Protection from blue.",
        "Creature — Goblin Warrior",
    )
    assert engine._has_protection_role_text(
        "Creatures you control gain hexproof until end of turn.",
        "Artifact",
    )
