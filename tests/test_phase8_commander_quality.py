import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import LocalCardCatalog
from services.card_function_profile import classify_card_functions
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def make_engine():
    return EnhancedSuggestionEngine(scryfall_service=None)


def commander(name, oracle_text, colors):
    return {
        "name": name,
        "type_line": "Legendary Creature",
        "oracle_text": oracle_text,
        "cmc": 4,
        "color_identity": colors,
        "legalities": {"commander": "legal"},
    }


def tier_map(engine, card):
    detected = engine._detect_commander_synergies(card)
    actionable, evidence = engine._actionable_commander_themes(card, detected)
    return actionable, {item["id"]: item["tier"] for item in evidence}


def test_sacrifice_functions_distinguish_repeatable_outlets_from_one_shot_costs():
    free_outlet = classify_card_functions({
        "type_line": "Creature",
        "oracle_text": "Sacrifice another creature: Scry 1.",
        "cmc": 1,
    })
    paid_outlet = classify_card_functions({
        "type_line": "Enchantment",
        "oracle_text": "{1}{B}, Sacrifice a creature: You gain 1 life and draw a card.",
        "cmc": 1,
    })
    one_shot = classify_card_functions({
        "type_line": "Instant",
        "oracle_text": "As an additional cost to cast this spell, sacrifice a creature. Draw two cards.",
        "cmc": 1,
    })

    assert free_outlet.has("repeatable_sacrifice_outlet")
    assert free_outlet.has("mana_free_sacrifice_outlet")
    assert paid_outlet.has("repeatable_sacrifice_outlet")
    assert not paid_outlet.has("mana_free_sacrifice_outlet")
    assert one_shot.has("one_shot_sacrifice_cost")
    assert not one_shot.has("repeatable_sacrifice_outlet")


def test_one_shot_sacrifice_reason_never_calls_the_card_a_repeatable_outlet():
    engine = make_engine()
    meren = commander(
        "Meren of Clan Nel Toth",
        "Whenever another creature you control dies, you get an experience counter. At the beginning of your end step, return target creature card from your graveyard.",
        ["B", "G"],
    )
    rites = {
        "name": "Village Rites",
        "type_line": "Instant",
        "oracle_text": "As an additional cost to cast this spell, sacrifice a creature. Draw two cards.",
        "cmc": 1,
    }

    quality = engine._recommendation_quality_metadata(
        rites,
        "sacrifice",
        meren,
        precise_sacrifice_roles=True,
    )
    reason = engine._generate_validated_recommendation_reason(
        rites,
        meren["name"],
        "sacrifice",
        quality,
        meren,
    )

    assert quality["job"] == "one-shot sacrifice value"
    assert "one-shot" in reason
    assert "rather than a reusable outlet" in reason
    assert "real sacrifice outlet" not in reason


def test_theme_evidence_separates_primary_supporting_and_incidental_signals():
    engine = make_engine()
    zedruu = commander(
        "Zedruu the Greathearted",
        "At the beginning of your upkeep, you gain X life and draw X cards, where X is the number of permanents you own that your opponents control. {R}{W}{U}: Target opponent gains control of target permanent you control.",
        ["R", "W", "U"],
    )
    vadrik = commander(
        "Vadrik, Astral Archmage",
        "Whenever day becomes night or night becomes day, put a +1/+1 counter on Vadrik. Instant and sorcery spells you cast cost {X} less to cast, where X is Vadrik's power.",
        ["U", "R"],
    )
    meren = commander(
        "Meren of Clan Nel Toth",
        "Whenever another creature you control dies, you get an experience counter. At the beginning of your end step, return target creature card from your graveyard to your hand or the battlefield.",
        ["B", "G"],
    )

    zedruu_evidence = engine._commander_theme_evidence(
        zedruu,
        ["donation", "lifegain"],
    )
    zedruu_tiers = {item["id"]: item["tier"] for item in zedruu_evidence}
    zedruu_actionable = [
        item["id"] for item in zedruu_evidence if item["tier"] != "incidental"
    ]
    vadrik_actionable, vadrik_tiers = tier_map(engine, vadrik)
    meren_actionable, meren_tiers = tier_map(engine, meren)

    assert zedruu_tiers["donation"] == "primary"
    assert zedruu_tiers["lifegain"] == "incidental"
    assert "lifegain" not in zedruu_actionable
    assert vadrik_tiers["instant_sorcery"] == "primary"
    assert vadrik_tiers["counters"] == "supporting"
    assert meren_tiers["graveyard"] == "primary"
    assert meren_tiers["sacrifice"] == "primary"


def test_commander_selection_copy_contains_no_ranker_or_portfolio_jargon():
    engine = make_engine()
    card = {
        "name": "Example Engine",
        "job": "token payoff",
        "role": "tokens",
        "score": 88,
        "cmc": 3,
        "evidence_tags": ["direct_synergy", "payoff"],
        "penalty_tags": [],
        "matched_plan_lanes": ["tokens", "attack_triggers"],
        "reason": "It turns attacks into more creatures.",
    }

    engine._annotate_v2_selection([card])
    engine._annotate_v3_selection([card])
    public_copy = f"{card['reason']} {card['selection_reason']}"

    assert "It made the list" in public_copy
    assert "V2" not in public_copy
    assert "Portfolio fit" not in public_copy
    assert "ranked #" not in public_copy
    assert "measured" not in public_copy


def test_commander_portfolio_reserves_four_of_five_slots_for_plan_cards():
    engine = make_engine()
    engine.portfolio_optimizer.select = lambda cards, limit, kind: list(cards)[:limit]
    plan = [{"name": f"Plan {index}", "recommendation_lane": "plan"} for index in range(5)]
    support = [{"name": f"Support {index}", "recommendation_lane": "support"} for index in range(3)]

    selected = engine._select_commander_portfolio(plan, support, 5)

    assert [card["recommendation_lane"] for card in selected] == [
        "plan", "plan", "plan", "plan", "support"
    ]


def test_catalog_batch_search_matches_individual_query_results(tmp_path):
    path = tmp_path / "catalog.json"
    cards = [
        {
            "name": "Popular Draw",
            "oracle_id": "draw",
            "type_line": "Sorcery",
            "oracle_text": "Draw two cards.",
            "color_identity": ["U"],
            "edhrec_rank": 1,
            "legalities": {"commander": "legal"},
        },
        {
            "name": "Mana Rock",
            "oracle_id": "rock",
            "type_line": "Artifact",
            "oracle_text": "{T}: Add {C}.",
            "color_identity": [],
            "edhrec_rank": 2,
            "legalities": {"commander": "legal"},
        },
        {
            "name": "Token Maker",
            "oracle_id": "token",
            "type_line": "Instant",
            "oracle_text": "Create two creature tokens.",
            "color_identity": ["W"],
            "edhrec_rank": 3,
            "legalities": {"commander": "legal"},
        },
    ]
    path.write_text(json.dumps({
        "schema_version": 1,
        "catalog_version": "phase8-test",
        "cards": cards,
    }), encoding="utf-8")
    catalog = LocalCardCatalog(path)
    requests = [("o:draw f:commander", 5), ("t:artifact f:commander", 5)]

    batched = catalog.search_many(requests)

    for query, limit in requests:
        assert batched[query] == catalog.search(query, limit)
