import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.recommendation_ranker import EvidenceRankerV2


def recommendation(
    name,
    *,
    score,
    evidence_tags,
    penalty_tags=None,
    cmc=2,
    job="engine",
    role="artifact",
    source_rank=10,
):
    return {
        "name": name,
        "score": score,
        "evidence_tags": evidence_tags,
        "penalty_tags": penalty_tags or [],
        "cmc": cmc,
        "job": job,
        "role": role,
        "_source_rank": source_rank,
    }


def test_v2_components_are_bounded_and_branch_score_is_not_dominant():
    ranker = EvidenceRankerV2()
    weak_high_branch = recommendation(
        "Weak High Branch",
        score=95,
        evidence_tags=["enabler"],
        penalty_tags=["generic_staple", "low_evidence"],
    )
    grounded_lower_branch = recommendation(
        "Grounded Lower Branch",
        score=82,
        evidence_tags=["direct_synergy", "card_flow", "repeatable_engine"],
    )

    weak = ranker.assess(weak_high_branch)
    grounded = ranker.assess(grounded_lower_branch)

    assert 0 <= weak.score <= 100
    assert 0 <= grounded.score <= 100
    assert grounded.score > weak.score
    assert grounded.components["plan_alignment"] <= 22
    assert grounded.components["legacy_quality"] <= 18


def test_v2_hard_context_penalty_overwhelms_superficial_evidence():
    ranker = EvidenceRankerV2()
    valid = recommendation(
        "Creature Token Maker",
        score=74,
        evidence_tags=["enabler", "creature_token_support"],
    )
    wrong_token = recommendation(
        "Treasure Maker",
        score=90,
        evidence_tags=["direct_synergy", "card_flow"],
        penalty_tags=["wrong_token_type"],
    )

    assert ranker.score(valid) > ranker.score(wrong_token)
    assert ranker.assess(wrong_token).components["penalties"] == -60


def test_v2_selection_applies_material_job_diversity():
    ranker = EvidenceRankerV2()
    candidates = [
        recommendation(
            "Engine One",
            score=88,
            evidence_tags=["direct_synergy", "card_flow"],
            job="card engine",
            source_rank=1,
        ),
        recommendation(
            "Engine Two",
            score=87,
            evidence_tags=["direct_synergy", "card_flow"],
            job="card engine",
            source_rank=2,
        ),
        recommendation(
            "Protection Piece",
            score=84,
            evidence_tags=["direct_synergy", "protection"],
            job="protection",
            source_rank=3,
        ),
    ]

    selected = ranker.select(candidates, max_cards=2, kind="commander")

    assert selected[0]["name"] == "Engine One"
    assert selected[1]["name"] == "Protection Piece"


def test_shadow_mode_preserves_legacy_output_and_records_comparison():
    engine = EnhancedSuggestionEngine(scryfall_service=None, ranker_mode="shadow")
    candidates = [
        recommendation(
            "Legacy Favorite",
            score=95,
            evidence_tags=["enabler"],
            penalty_tags=["low_evidence"],
            source_rank=1,
        ),
        recommendation(
            "Evidence Favorite",
            score=82,
            evidence_tags=["direct_synergy", "card_flow", "repeatable_engine"],
            source_rank=2,
        ),
    ]

    selected = engine._select_ranked_recommendations(candidates, max_cards=1)
    status = engine.get_ranker_status()

    assert selected[0]["name"] == "Legacy Favorite"
    assert status["counters"]["comparisons"] == 1
    assert status["counters"]["changed_top_choice"] == 1
    assert status["rates"]["changed_top_choice"] == 1.0
    assert status["by_kind"]["commander"]["comparisons"] == 1
    assert status["by_kind"]["commander"]["rates"]["candidate_overlap"] == 0.0
    assert status["recent_changes"][0]["v2"] == ["Evidence Favorite"]


def test_v2_mode_uses_evidence_order_with_same_candidates():
    engine = EnhancedSuggestionEngine(scryfall_service=None, ranker_mode="v2")
    candidates = [
        recommendation(
            "Legacy Favorite",
            score=95,
            evidence_tags=["enabler"],
            penalty_tags=["low_evidence"],
            source_rank=1,
        ),
        recommendation(
            "Evidence Favorite",
            score=82,
            evidence_tags=["direct_synergy", "card_flow", "repeatable_engine"],
            source_rank=2,
        ),
    ]

    selected = engine._select_ranked_recommendations(candidates, max_cards=1)

    assert selected[0]["name"] == "Evidence Favorite"


def test_deck_portfolio_defers_budget_pressure_when_clean_choices_exist():
    ranker = EvidenceRankerV2()
    pressured = {
        "card_name": "Pressured Plan Card",
        "score": 95,
        "evidence_tags": ["direct_synergy", "competitive_evidence"],
        "penalty_tags": ["implicit_budget_pressure"],
        "cmc": 1,
        "role_tag": "tutor",
        "_source_rank": 1,
    }
    clean = {
        "card_name": "Affordable Interaction",
        "score": 82,
        "evidence_tags": ["competitive_evidence", "efficient_interaction"],
        "penalty_tags": [],
        "cmc": 1,
        "role_tag": "interaction",
        "_source_rank": 2,
    }

    selected = ranker.select([pressured, clean], max_cards=1, kind="deck")

    assert selected[0]["card_name"] == "Affordable Interaction"


def test_close_plan_specific_card_leads_over_generic_role_fix():
    ranker = EvidenceRankerV2()
    generic = {
        "card_name": "Generic Ramp",
        "score": 90,
        "evidence_tags": ["mana_development", "needed_role"],
        "penalty_tags": [],
        "cmc": 2,
        "role_tag": "ramp",
        "_source_rank": 1,
    }
    plan_card = {
        "card_name": "Tutorable Aura",
        "score": 84,
        "evidence_tags": ["direct_synergy", "declared_strategy_priority"],
        "penalty_tags": [],
        "cmc": 2,
        "role_tag": "enchantment",
        "_source_rank": 2,
    }

    selected = ranker.select([generic, plan_card], max_cards=1, kind="deck")

    assert selected[0]["card_name"] == "Tutorable Aura"
