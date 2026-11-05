import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.portfolio_optimizer import EvidencePortfolioOptimizer
from services.recommendation_ranker import EvidenceRankerV2
from services.strategy_profile import (
    BalancedQueryPlanner,
    build_strategy_profile,
    query_specs_from_pairs,
)


def test_portfolio_order_credits_new_secondary_lane():
    optimizer = EvidencePortfolioOptimizer(EvidenceRankerV2())
    token_draw = {
        "card_name": "Token Draw",
        "role_tag": "draw",
        "score": 95,
        "evidence_tags": ["direct_synergy", "card_flow"],
        "penalty_tags": [],
        "matched_plan_lanes": ["tokens", "draw"],
        "cmc": 2,
    }
    generic_sweeper = {
        "card_name": "Generic Sweeper",
        "role_tag": "sweeper",
        "score": 90,
        "evidence_tags": ["role_gap", "interaction"],
        "penalty_tags": [],
        "matched_plan_lanes": ["sweeper"],
        "cmc": 4,
    }
    plan_sweeper = {
        "card_name": "Plan Sweeper",
        "role_tag": "sweeper",
        "score": 95,
        "evidence_tags": [
            "commander_theme_match",
            "creature_token_support",
            "role_gap_overlap",
        ],
        "penalty_tags": [],
        "matched_plan_lanes": ["tokens", "sweeper"],
        "cmc": 4,
    }

    ordered = optimizer._order_selected(
        [token_draw, generic_sweeper, plan_sweeper],
        "deck",
        "card_name",
    )

    assert [card["card_name"] for card in ordered].index(
        "Plan Sweeper"
    ) < [card["card_name"] for card in ordered].index("Generic Sweeper")


def test_balanced_planner_reserves_searches_for_measured_role_gaps():
    profile = build_strategy_profile(
        commander_names=["Test Commander"],
        commander_synergies=[
            "typal", "tokens", "sacrifice", "graveyard", "creature",
        ],
        commander_archetypes=[],
        gaps={"roles": {"draw": 4, "protection": 3, "interaction": 2}},
        deck_context={
            "synergy_counts": {},
            "role_quality": {
                "draw": {"target_min": 10, "effective_count": 6, "effective_gap": 4},
                "protection": {"target_min": 3, "effective_count": 0, "effective_gap": 3},
                "interaction": {"target_min": 5, "effective_count": 3, "effective_gap": 2},
            },
        },
        coverage_level="deep",
    )
    pairs = [
        (f"synergy:{lane}", f"query-{lane}")
        for lane in ["typal", "tokens", "sacrifice", "graveyard", "creature"]
    ]
    pairs.extend([
        ("draw", "query-draw"),
        ("protection", "query-protection"),
        ("interaction", "query-interaction"),
    ])

    selected, diagnostics = BalancedQueryPlanner().plan(
        query_specs_from_pairs(pairs),
        profile,
        5,
    )

    assert diagnostics["changed"]
    assert sum(spec.kind == "role" for spec in selected) >= 2
    assert sum(spec.kind == "synergy" for spec in selected) >= 2
    assert {spec.lane for spec in selected} & {"draw", "protection", "interaction"}


def test_explicit_category_order_is_preserved():
    profile = build_strategy_profile(
        commander_names=[],
        commander_synergies=[],
        commander_archetypes=[],
        gaps={"roles": {}},
    )
    specs = query_specs_from_pairs([
        ("draw", "query-draw"),
        ("ramp", "query-ramp"),
    ])
    selected, diagnostics = BalancedQueryPlanner().plan(
        specs,
        profile,
        1,
        explicit_categories=True,
    )
    assert [spec.key for spec in selected] == ["draw"]
    assert not diagnostics["changed"]


def test_portfolio_optimizer_values_plan_lane_coverage():
    ranker = EvidenceRankerV2()
    optimizer = EvidencePortfolioOptimizer(ranker, beam_width=32)
    candidates = [
        {
            "card_name": "Token Engine A",
            "score": 90,
            "cmc": 2,
            "role_tag": "tokens",
            "evidence_tags": ["direct_synergy", "repeatable_engine"],
            "penalty_tags": [],
            "matched_plan_lanes": ["tokens"],
        },
        {
            "card_name": "Token Engine B",
            "score": 89,
            "cmc": 2,
            "role_tag": "tokens",
            "evidence_tags": ["direct_synergy", "repeatable_engine"],
            "penalty_tags": [],
            "matched_plan_lanes": ["tokens"],
        },
        {
            "card_name": "Protection Piece",
            "score": 87,
            "cmc": 1,
            "role_tag": "protection",
            "evidence_tags": ["role_gap", "protection", "effective_role_gain"],
            "penalty_tags": [],
            "matched_plan_lanes": ["protection"],
            "effective_role_gain": 0.9,
        },
    ]

    selected = optimizer.select(candidates, 2, kind="deck")

    assert {card["card_name"] for card in selected} == {
        "Token Engine A",
        "Protection Piece",
    }
