import json
import sys
from copy import deepcopy
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


from services.builder_validation import (
    audit_golden_suite,
    evaluate_build_result,
    evaluate_counterfactual_pair,
    promotion_summary,
)


FIXTURE = Path(__file__).parent / "fixtures" / "golden_builder_validation.json"


def complete_result():
    nonlands = [
        {
            "name": f"Evidence Card {index}",
            "qty": 1,
            "type_line": "Artifact",
            "oracle_text": "",
        }
        for index in range(63)
    ]
    island = {
        "name": "Island",
        "qty": 36,
        "type_line": "Basic Land — Island",
        "oracle_text": "",
    }
    return {
        "status": "ready_complete",
        "scope": {
            "target_mainboard_slots": 99,
            "remaining_mainboard_slots": 0,
        },
        "commander": {"names": ["Talrand, Sky Summoner"]},
        "intent": {
            "protected_cards": ["Evidence Card 0"],
            "protected_packages": [],
            "excluded_cards": ["Swords to Plowshares"],
            "collection_mode": "all_cards",
            "owned_card_names": [],
        },
        "selected_cards": [
            {
                "name": "Evidence Card 0",
                "qty": 1,
                "source": "planner_v3",
                "reason": "It fills the measured card-flow role.",
                "evidence": ["card flow", "role gap"],
                "confidence": 0.91,
            },
            {
                **island,
                "source": "mana_baseline",
                "reason": "Measured blue mana-symbol demand.",
                "evidence": ["mana-symbol demand"],
                "confidence": 0.9,
            },
        ],
        "proposed_main_deck": [*nonlands, island],
        "unresolved_slots": [],
        "validation": {
            "passed": True,
            "errors": [],
            "checks": {
                "legality": True,
                "singleton": True,
                "budget": True,
                "protected_and_excluded": True,
                "collection": True,
                "deck_count": True,
                "mana_sources": True,
            },
        },
        "mana_base": {"target_lands": 36},
        "budget": {"verified_subtotal_usd": 40},
        "quality": {
            "role_counts": {
                "draw": 8,
                "ramp": 10,
                "removal": 6,
                "protection": 4,
                "engine": 20,
                "mana base": 36,
            },
            "distinct_non_mana_roles": 5,
            "average_nonland_mana_value": 2.8,
            "reason_ledger_coverage": 1.0,
            "evidence_ledger_coverage": 1.0,
            "average_planner_confidence": 0.91,
        },
    }


def test_phase_five_fixture_meets_required_coverage():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    audit = audit_golden_suite(manifest)

    assert audit["passed"], audit["errors"]
    assert audit["case_count"] == 26
    assert audit["negative_control_count"] >= 5
    assert len(audit["counterfactual_groups"]) >= 3
    assert audit["counterfactual_pair_count"] >= 3


def test_complete_result_passes_every_promotion_gate():
    evaluation = evaluate_build_result(
        complete_result(),
        {"case_id": "test", "expected_outcome": "complete"},
    )

    assert evaluation["passed"], evaluation["errors"]
    assert evaluation["proposed_slots"] == 99
    assert evaluation["land_count"] == 36


def test_reason_and_mana_failures_block_promotion():
    result = complete_result()
    result["selected_cards"][0]["reason"] = ""
    result["validation"]["checks"]["mana_sources"] = False

    evaluation = evaluate_build_result(
        result,
        {"case_id": "test", "expected_outcome": "complete"},
    )

    assert not evaluation["passed"]
    assert any("mana_sources" in error for error in evaluation["errors"])
    assert any("reason ledger" in error for error in evaluation["errors"])


def test_expected_block_is_valid_only_with_a_disclosed_error():
    result = complete_result()
    result["status"] = "blocked"
    result["validation"]["passed"] = False
    result["validation"]["errors"] = [{"code": "commander_illegal", "message": "Illegal"}]
    result["intent"]["protected_cards"] = ["Illegal Off-Color Card"]
    result["proposed_main_deck"] = []
    result["selected_cards"] = []
    result["scope"]["remaining_mainboard_slots"] = 99

    evaluation = evaluate_build_result(
        result,
        {"case_id": "negative", "expected_outcome": "blocked"},
    )

    assert evaluation["passed"], evaluation["errors"]


def test_counterfactual_budget_direction_and_instability_are_measured():
    baseline = complete_result()
    variant = deepcopy(baseline)
    variant["budget"]["verified_subtotal_usd"] = 25
    for index, card in enumerate(variant["selected_cards"]):
        card["name"] = f"Different Evidence Card {index}"

    assert evaluate_counterfactual_pair(baseline, variant, "lower_budget")["passed"]
    assert evaluate_counterfactual_pair(baseline, variant, "different_portfolio")["passed"]
    assert not evaluate_counterfactual_pair(baseline, variant, "stable_portfolio")["passed"]


def test_promotion_requires_a_result_for_every_reviewed_case():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = promotion_summary(manifest, {"B01": complete_result()})

    assert not report["promoted"]
    assert len(report["missing_results"]) == 25
    assert report["missing_counterfactual_results"]


def test_promotion_summary_executes_reviewed_counterfactual_contracts():
    manifest = {
        "schema_version": 1,
        "minimum_cases": 0,
        "cases": [
            {"case_id": "base", "expected_outcome": "complete"},
            {"case_id": "variant", "expected_outcome": "complete"},
        ],
        "counterfactuals": [
            {
                "baseline_case_id": "base",
                "variant_case_id": "variant",
                "expectation": "lower_budget",
            }
        ],
    }
    baseline = complete_result()
    variant = deepcopy(baseline)
    variant["budget"]["verified_subtotal_usd"] = 20

    report = promotion_summary(manifest, {"base": baseline, "variant": variant})

    assert report["counterfactual_checks"][0]["passed"]

