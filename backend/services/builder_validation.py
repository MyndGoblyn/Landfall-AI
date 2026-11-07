"""Phase 5 promotion gates for deterministic complete-deck construction.

The constructor remains responsible for selecting cards.  This module is a
separate evaluator so a result cannot declare itself promotion-ready merely by
returning a successful status.  Golden-suite coverage, hard invariants,
reason-ledger completeness, mana sufficiency, and counterfactual direction are
reviewed independently.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Mapping, Optional


REQUIRED_COVERAGE = {
    "aggro",
    "control",
    "value",
    "combo",
    "typal",
    "spellslinger",
    "graveyard",
    "artifacts",
    "enchantments",
    "lands",
    "voltron",
    "politics",
    "intentional_jank",
    "budget",
    "high_power",
    "cedh",
    "partner_background",
    "colorless",
    "five_color",
    "expensive_commander",
    "unusual_mana_base",
    "negative_control",
}


def _quantity(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean(value) -> str:
    return " ".join(str(value or "").split())


def _allows_multiple(card: Mapping) -> bool:
    type_line = str(card.get("type_line") or "").casefold()
    oracle_text = str(card.get("oracle_text") or "").casefold()
    return (
        "basic land" in type_line
        or "a deck can have any number of cards named" in oracle_text
        or "a deck can have up to" in oracle_text
    )


def audit_golden_suite(manifest: Mapping) -> Dict:
    """Verify that the reviewed Phase 5 matrix covers the promotion contract."""
    cases = list(manifest.get("cases") or [])
    minimum_cases = max(24, int(manifest.get("minimum_cases") or 24))
    errors: List[str] = []
    case_ids = [_clean(case.get("case_id")) for case in cases]
    if manifest.get("schema_version") != 1:
        errors.append("Unsupported builder validation schema version")
    if len(cases) < minimum_cases:
        errors.append(
            f"Builder validation requires at least {minimum_cases} cases; found {len(cases)}"
        )
    if any(not case_id for case_id in case_ids):
        errors.append("Every builder validation case requires a stable case_id")
    duplicates = sorted(
        case_id for case_id, count in Counter(case_ids).items() if case_id and count > 1
    )
    if duplicates:
        errors.append("Duplicate builder validation case IDs: " + ", ".join(duplicates))

    observed_coverage = {
        _clean(tag).casefold()
        for case in cases
        for tag in case.get("coverage") or []
        if _clean(tag)
    }
    missing_coverage = sorted(REQUIRED_COVERAGE - observed_coverage)
    if missing_coverage:
        errors.append("Missing builder coverage: " + ", ".join(missing_coverage))

    counterfactual_groups = defaultdict(list)
    for case in cases:
        group = _clean(case.get("counterfactual_group"))
        if group:
            counterfactual_groups[group].append(case)
    paired_groups = {
        group: values for group, values in counterfactual_groups.items() if len(values) >= 2
    }
    if len(paired_groups) < 3:
        errors.append("At least three counterfactual groups require two or more cases")

    known_case_ids = set(case_ids)
    counterfactuals = list(manifest.get("counterfactuals") or [])
    valid_expectations = {"lower_budget", "different_portfolio", "stable_portfolio"}
    counterfactual_pairs = set()
    for check in counterfactuals:
        baseline_id = _clean(check.get("baseline_case_id"))
        variant_id = _clean(check.get("variant_case_id"))
        expectation = _clean(check.get("expectation"))
        if baseline_id not in known_case_ids or variant_id not in known_case_ids:
            errors.append("Counterfactual check references an unknown case")
        if baseline_id == variant_id:
            errors.append("Counterfactual check must compare two different cases")
        if expectation not in valid_expectations:
            errors.append(f"Unsupported counterfactual expectation: {expectation or 'missing'}")
        if baseline_id and variant_id:
            counterfactual_pairs.add(tuple(sorted((baseline_id, variant_id))))
    if len(counterfactual_pairs) < 3:
        errors.append("At least three explicit counterfactual pairs are required")

    negative_controls = [
        case for case in cases if "negative_control" in set(case.get("coverage") or [])
    ]
    if len(negative_controls) < 5:
        errors.append("At least five negative controls are required")

    return {
        "passed": not errors,
        "case_count": len(cases),
        "coverage": sorted(observed_coverage),
        "missing_coverage": missing_coverage,
        "counterfactual_groups": sorted(paired_groups),
        "counterfactual_pair_count": len(counterfactual_pairs),
        "negative_control_count": len(negative_controls),
        "errors": errors,
    }


def evaluate_build_result(result: Mapping, case: Optional[Mapping] = None) -> Dict:
    """Apply promotion gates to one constructor result.

    Incomplete and negative-control cases may intentionally abstain.  They must
    still preserve every hard constraint and explain all selected cards.
    """
    case = case or {}
    expected_outcome = case.get("expected_outcome", "complete")
    validation = result.get("validation") or {}
    checks = validation.get("checks") or {}
    scope = result.get("scope") or {}
    intent = result.get("intent") or {}
    proposed = list(result.get("proposed_main_deck") or [])
    selected = list(result.get("selected_cards") or [])
    errors: List[str] = []

    hard_checks = {
        "legality",
        "singleton",
        "budget",
        "protected_and_excluded",
        "collection",
        "deck_count",
    }
    if expected_outcome == "complete":
        hard_checks.add("mana_sources")
    if expected_outcome == "blocked":
        hard_checks = {"deck_count"}
    failed_checks = sorted(check for check in hard_checks if checks.get(check) is not True)
    if failed_checks:
        errors.append("Failed hard checks: " + ", ".join(failed_checks))

    if validation.get("errors") and expected_outcome not in {"blocked", "abstain"}:
        errors.append("Unexpected constructor validation errors")

    target = _quantity(scope.get("target_mainboard_slots"))
    proposed_slots = sum(_quantity(card.get("qty", 1)) for card in proposed)
    remaining = _quantity(scope.get("remaining_mainboard_slots"))
    if proposed_slots > target:
        errors.append(f"Proposed main deck has {proposed_slots} slots for a {target}-slot target")
    if expected_outcome == "complete":
        if result.get("status") != "ready_complete":
            errors.append("Expected a complete draft but the constructor abstained or remained partial")
        if remaining or proposed_slots != target:
            errors.append("Complete draft does not exactly match the main-deck target")
        if result.get("unresolved_slots"):
            errors.append("Complete draft contains unresolved slots")
    elif expected_outcome == "abstain" and result.get("status") == "ready_complete":
        errors.append("Negative control should abstain instead of returning a complete draft")
    elif expected_outcome == "blocked" and result.get("status") != "blocked":
        errors.append("Negative control was expected to block construction")
    elif expected_outcome == "blocked" and not validation.get("errors"):
        errors.append("Blocked negative control did not disclose its blocking error")

    for card in selected:
        if not _clean(card.get("reason")):
            errors.append(f"{card.get('name') or 'Selected card'} has no reason ledger")
        if not list(card.get("evidence") or []):
            errors.append(f"{card.get('name') or 'Selected card'} has no evidence ledger")
        confidence = card.get("confidence")
        if card.get("source") == "planner_v3" and confidence is None:
            errors.append(f"{card.get('name') or 'Planner card'} has no confidence value")

    names = Counter()
    representatives = {}
    for card in proposed:
        key = _clean(card.get("name")).casefold()
        if not key:
            errors.append("Proposed deck contains an unnamed card")
            continue
        names[key] += _quantity(card.get("qty", 1))
        representatives[key] = card
    duplicate_names = sorted(
        representatives[key].get("name") or key
        for key, count in names.items()
        if count > 1 and not _allows_multiple(representatives[key])
    )
    if duplicate_names:
        errors.append("Singleton violations: " + ", ".join(duplicate_names))

    protected = {
        _clean(name).casefold()
        for name in intent.get("protected_cards") or []
        if _clean(name)
    }
    for package in intent.get("protected_packages") or []:
        protected.update(
            _clean(name).casefold()
            for name in package.get("cards") or []
            if _clean(name)
        )
    missing_protected = sorted(protected - set(names))
    # A blocked request can fail precisely because a requested protected card
    # is illegal or violates another hard constraint.  Requiring that card to
    # appear in an intentionally empty blocked result would turn correct
    # abstention into a false validation failure.
    if expected_outcome != "blocked" and missing_protected:
        errors.append("Missing protected cards: " + ", ".join(missing_protected))

    excluded = {
        _clean(name).casefold()
        for name in intent.get("excluded_cards") or []
        if _clean(name)
    }
    present_excluded = sorted(excluded & set(names))
    if expected_outcome != "blocked" and present_excluded:
        errors.append("Excluded cards were selected: " + ", ".join(present_excluded))

    if expected_outcome != "blocked" and intent.get("collection_mode") == "owned_only":
        owned = {
            _clean(name).casefold()
            for name in intent.get("owned_card_names") or []
            if _clean(name)
        }
        command_zone = {
            _clean(name).casefold()
            for name in (result.get("commander") or {}).get("names") or []
        }
        outside_pool = sorted(set(names) - owned - command_zone)
        if outside_pool:
            errors.append("Owned-only draft selected outside the collection: " + ", ".join(outside_pool))

    land_count = sum(
        _quantity(card.get("qty", 1))
        for card in proposed
        if "land" in str(card.get("type_line") or "").casefold()
    )
    mana_target = _quantity((result.get("mana_base") or {}).get("target_lands"))
    if expected_outcome == "complete" and land_count < mana_target:
        errors.append(f"Mana floor requires {mana_target} lands but only {land_count} were selected")

    quality = result.get("quality") or {}
    if expected_outcome == "complete":
        if float(quality.get("reason_ledger_coverage") or 0) < 1:
            errors.append("Reason ledger does not cover every proposed slot")
        if float(quality.get("evidence_ledger_coverage") or 0) < 1:
            errors.append("Evidence ledger does not cover every proposed slot")
        planner_confidence = quality.get("average_planner_confidence")
        if planner_confidence is None or float(planner_confidence) < 0.72:
            errors.append("Average Planner V3 confidence is below the 0.72 promotion floor")

        case_coverage = set(case.get("coverage") or [])
        minimum_roles = 3 if "intentional_jank" in case_coverage else 4
        if _quantity(quality.get("distinct_non_mana_roles")) < minimum_roles:
            errors.append(
                f"Portfolio exposes fewer than {minimum_roles} distinct non-mana roles"
            )

        role_counts = {
            str(role).casefold(): _quantity(count)
            for role, count in (quality.get("role_counts") or {}).items()
        }

        def role_total(tokens: Iterable[str]) -> int:
            return sum(
                count
                for role, count in role_counts.items()
                if role != "mana base" and any(token in role for token in tokens)
            )

        card_flow = role_total(("draw", "card flow", "card velocity", "advantage"))
        ramp = role_total(("ramp", "acceleration", "mana rock"))
        interaction = role_total((
            "removal",
            "interaction",
            "counter",
            "sweeper",
            "protection",
        ))
        if card_flow < 5:
            errors.append(f"Card-flow role floor is 5; portfolio provides {card_flow}")
        if ramp < 6:
            errors.append(f"Ramp role floor is 6; portfolio provides {ramp}")
        if interaction < 8:
            errors.append(
                f"Interaction/protection role floor is 8; portfolio provides {interaction}"
            )

        average_mana_value = quality.get("average_nonland_mana_value")
        if average_mana_value is not None:
            curve_ceiling = 5.5 if "expensive_commander" in case_coverage else (
                3.6 if {"high_power", "cedh"} & case_coverage else 4.5
            )
            if float(average_mana_value) > curve_ceiling:
                errors.append(
                    f"Average nonland mana value {average_mana_value} exceeds the {curve_ceiling} case ceiling"
                )

    return {
        "passed": not errors,
        "case_id": case.get("case_id"),
        "expected_outcome": expected_outcome,
        "status": result.get("status"),
        "proposed_slots": proposed_slots,
        "target_slots": target,
        "land_count": land_count,
        "mana_target": mana_target,
        "quality": quality,
        "errors": list(dict.fromkeys(errors)),
    }


def evaluate_counterfactual_pair(
    baseline: Mapping,
    variant: Mapping,
    expectation: str,
) -> Dict:
    """Check that an intentional change moves the output in its requested direction."""
    baseline_budget = float((baseline.get("budget") or {}).get("verified_subtotal_usd") or 0)
    variant_budget = float((variant.get("budget") or {}).get("verified_subtotal_usd") or 0)
    baseline_names = {
        _clean(card.get("name")).casefold()
        for card in baseline.get("selected_cards") or []
    }
    variant_names = {
        _clean(card.get("name")).casefold()
        for card in variant.get("selected_cards") or []
    }
    errors = []
    if expectation == "lower_budget" and variant_budget > baseline_budget:
        errors.append("Budget-constrained variant became more expensive")
    if expectation == "different_portfolio" and variant_names == baseline_names:
        errors.append("Counterfactual intent did not change the selected portfolio")
    if expectation == "stable_portfolio" and not (baseline_names & variant_names):
        errors.append("Counterfactual caused unrelated total portfolio instability")
    return {
        "passed": not errors,
        "expectation": expectation,
        "shared_cards": len(baseline_names & variant_names),
        "baseline_budget": round(baseline_budget, 2),
        "variant_budget": round(variant_budget, 2),
        "errors": errors,
    }


def promotion_summary(
    manifest: Mapping,
    results: Mapping[str, Mapping],
) -> Dict:
    """Return the auditable decision used before enabling complete mode."""
    coverage = audit_golden_suite(manifest)
    evaluations = []
    cases_by_id = {
        str(case.get("case_id")): case for case in manifest.get("cases") or []
    }
    missing_results = sorted(set(cases_by_id) - set(results))
    for case_id, result in results.items():
        if case_id in cases_by_id:
            evaluations.append(evaluate_build_result(result, cases_by_id[case_id]))
    failed = [item for item in evaluations if not item["passed"]]
    counterfactual_checks = []
    missing_counterfactual_results = []
    for definition in manifest.get("counterfactuals") or []:
        baseline_id = str(definition.get("baseline_case_id") or "")
        variant_id = str(definition.get("variant_case_id") or "")
        if baseline_id not in results or variant_id not in results:
            missing_counterfactual_results.append({
                "baseline_case_id": baseline_id,
                "variant_case_id": variant_id,
                "expectation": definition.get("expectation"),
            })
            continue
        check = evaluate_counterfactual_pair(
            results[baseline_id],
            results[variant_id],
            str(definition.get("expectation") or ""),
        )
        counterfactual_checks.append({
            "baseline_case_id": baseline_id,
            "variant_case_id": variant_id,
            **check,
        })
    failed_counterfactuals = [
        check for check in counterfactual_checks if not check["passed"]
    ]
    return {
        "promoted": (
            coverage["passed"]
            and not missing_results
            and not failed
            and not missing_counterfactual_results
            and not failed_counterfactuals
            and len(evaluations) >= 24
        ),
        "coverage": coverage,
        "evaluated_cases": len(evaluations),
        "missing_results": missing_results,
        "failed_cases": [item.get("case_id") for item in failed],
        "counterfactual_checks": counterfactual_checks,
        "missing_counterfactual_results": missing_counterfactual_results,
        "failed_counterfactuals": failed_counterfactuals,
        "evaluations": evaluations,
    }

