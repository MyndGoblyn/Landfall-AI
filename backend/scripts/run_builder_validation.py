"""Run the Phase 5 golden build-intent suite against the frozen card catalog."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Mapping, Optional


BACKEND_PATH = Path(__file__).resolve().parents[1]
REPO_PATH = BACKEND_PATH.parent
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.build_intent import BuildIntent, normalize_build_intent
from services.builder_validation import (
    audit_golden_suite,
    evaluate_build_result,
    promotion_summary,
)
from services.candidate_provider import LocalCatalogCandidateProvider
from services.deck_constructor import DeckConstructor
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.scryfall_service import ScryfallService


DEFAULT_SUITE = REPO_PATH / "tests" / "fixtures" / "golden_builder_validation.json"
DEFAULT_REAL_DECK_DIR = (
    REPO_PATH / "tests" / "fixtures" / "real_deck_validation" / "2026-08-04"
)
DEFAULT_CATALOG = BACKEND_PATH / "data" / "scryfall_oracle_cards.json"


class FrozenCatalogScryfall(ScryfallService):
    """Scryfall-compatible resolver with no network or mutable database state."""

    def __init__(self, provider: LocalCatalogCandidateProvider):
        super().__init__(db=None)
        self.provider = provider

    async def search_card(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        del fuzzy
        return await self.provider.catalog.resolve_async(name)

    async def get_card_bulk(self, names):
        return await self.provider.catalog.resolve_many_async(names)

    async def search_cards_by_criteria(self, query: str, limit: int = 20):
        return await self.provider.search_cards(query, limit)


def _load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _target_bracket(profile: Mapping) -> int:
    reference = int(profile.get("power_level_max") or profile.get("power_level_min") or 6)
    if reference <= 2:
        return 1
    if reference <= 4:
        return 2
    if reference <= 6:
        return 3
    if reference <= 8:
        return 4
    return 5


def _playstyle(profile: Mapping) -> str:
    text = " ".join(
        str(profile.get(field) or "")
        for field in ("primary_strategy", "desired_experience")
    ).casefold()
    if any(token in text for token in ("storm", "combo", "compact win")):
        return "combo"
    if any(token in text for token in ("control", "draw-go", "interaction")):
        return "control"
    if any(token in text for token in ("aggro", "go-wide", "voltron", "tempo")):
        return "aggressive"
    return "value"


def _intent_for_case(case: Mapping, source_profile: Mapping) -> Dict:
    values = {
        "confirmed": True,
        "deck_name": case.get("label") or f"Phase 5 {case['case_id']}",
        "starting_point": "commander",
        "commander_name": case.get("commander"),
        "partner_name": case.get("partner"),
        "build_mode": "complete_draft",
        "playstyle": _playstyle(source_profile),
        "target_bracket": _target_bracket(source_profile),
        "budget_mode": source_profile.get("budget_mode") or "unrestricted",
        "budget_limit_usd": source_profile.get("budget_limit_usd"),
        "max_card_price_usd": source_profile.get("max_card_price_usd"),
        "build_shape": "full_deck",
        "collection_mode": "all_cards",
        "protected_cards": source_profile.get("protected_cards") or [],
        "protected_packages": source_profile.get("protected_packages") or [],
        "excluded_cards": source_profile.get("excluded_cards") or [],
        "intentional_constraints": source_profile.get("intentional_constraints") or [],
        "notes": source_profile.get("desired_experience") or case.get("label"),
    }
    if values["budget_mode"] == "target" and not (
        values["budget_limit_usd"] is not None
        or values["max_card_price_usd"] is not None
    ):
        values["budget_mode"] = "flexible"
    values.update(case.get("intent_overrides") or {})
    if values.get("budget_mode") == "strict" and values.get("max_card_price_usd") is None:
        values["max_card_price_usd"] = 1
    intent = BuildIntent.model_validate(values)
    return normalize_build_intent(intent)


async def execute(
    suite_path: Path,
    real_deck_dir: Path,
    catalog_path: Path,
    case_ids: Optional[set[str]] = None,
) -> Dict:
    suite = _load_json(suite_path)
    coverage = audit_golden_suite(suite)
    if not coverage["passed"]:
        return {"promoted": False, "coverage": coverage, "results": {}}

    source_manifest = _load_json(real_deck_dir / "review_manifest.json")
    source_by_id = {
        str(case.get("case_id")): case for case in source_manifest.get("cases") or []
    }
    provider = LocalCatalogCandidateProvider(catalog_path)
    await provider.prepare()
    scryfall = FrozenCatalogScryfall(provider)
    engine = EnhancedSuggestionEngine(
        scryfall,
        candidate_provider=provider,
        ranker_mode="v2",
        planner_mode="v3",
    )
    constructor = DeckConstructor(engine, scryfall, mode="complete")

    raw_results = {}
    evaluations = {}
    try:
        for case in suite.get("cases") or []:
            case_id = str(case.get("case_id"))
            if case_ids and case_id not in case_ids:
                continue
            source = source_by_id.get(str(case.get("source_case_id") or ""), {})
            profile = source.get("intent_profile") or {}
            normalized = _intent_for_case(case, profile)
            deck = {
                "name": case.get("label"),
                "commander": case.get("commander"),
                "commanders": [
                    value for value in (case.get("commander"), case.get("partner")) if value
                ],
                "cards": [],
                "color_identity": [],
            }
            result = await constructor.construct(deck, normalized)
            raw_results[case_id] = result
            evaluations[case_id] = evaluate_build_result(result, case)
    finally:
        await scryfall.close()

    summary = promotion_summary(suite, raw_results)
    if case_ids:
        summary["promoted"] = False
        summary["partial_run"] = True
    return {
        "suite_version": suite.get("suite_version"),
        "catalog": provider.get_status(),
        "coverage": coverage,
        "summary": summary,
        "evaluations": evaluations,
        "results": raw_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--real-deck-dir", type=Path, default=DEFAULT_REAL_DECK_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--details", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(execute(
        args.suite.resolve(),
        args.real_deck_dir.resolve(),
        args.catalog.resolve(),
        set(args.case_ids or []),
    ))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    display = report if args.details else {
        "suite_version": report.get("suite_version"),
        "catalog": report.get("catalog"),
        "coverage": report.get("coverage"),
        "summary": report.get("summary"),
        "evaluations": report.get("evaluations"),
    }
    print(json.dumps(display, indent=2, sort_keys=True))
    summary = report.get("summary") or {}
    evaluations = list((report.get("evaluations") or {}).values())
    passed = bool(evaluations) and all(value.get("passed") for value in evaluations)
    if not args.case_ids:
        passed = passed and bool(summary.get("promoted"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

