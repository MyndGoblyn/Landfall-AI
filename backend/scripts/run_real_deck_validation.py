"""Run frozen real-deck fixtures through legacy and V2 recommendation paths."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional


BACKEND_PATH = Path(__file__).resolve().parents[1]
REPO_PATH = BACKEND_PATH.parent
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.candidate_provider import LocalCatalogCandidateProvider
from services.deck_input_assessment import (
    apply_recommendation_restraint,
    assess_deck_input,
)
from services.deck_intent import normalize_intent_profile
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


DEFAULT_FIXTURE_DIR = (
    REPO_PATH / "tests" / "fixtures" / "real_deck_validation" / "2026-08-04"
)
DEFAULT_CATALOG_PATH = BACKEND_PATH / "data" / "scryfall_oracle_cards.json"


class FrozenCatalogScryfall:
    """Scryfall subset backed entirely by the configured immutable catalog."""

    def __init__(self, cards_by_name: Mapping[str, Dict]):
        self.cards_by_name = cards_by_name

    async def search_card(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        del fuzzy
        return self.cards_by_name.get(str(name or "").strip().casefold())

    def extract_card_data(self, card: Mapping) -> Dict:
        return {
            "name": card.get("name"),
            "type_line": card.get("type_line", ""),
            "oracle_text": card.get("oracle_text", ""),
            "cmc": card.get("cmc", 0),
            "colors": card.get("colors", []),
            "color_identity": card.get("color_identity", []),
            "set_code": card.get("set"),
            "collector_number": card.get("collector_number"),
            "prices": card.get("prices", {}),
            "keywords": card.get("keywords", []),
            "legalities": card.get("legalities", {}),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plain_snapshot_contents(path: Path) -> Dict:
    commander = None
    cards = Counter()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(\d+)x?\s+(.+)$", line)
        if not match:
            raise ValueError(f"Invalid plain snapshot row in {path}: {line}")
        quantity = int(match.group(1))
        card_name = match.group(2).strip()
        if "*CMDR*" in card_name.upper():
            commander = re.sub(
                r"\*CMDR\*",
                "",
                card_name,
                flags=re.IGNORECASE,
            ).strip()
            continue
        cards[card_name] += quantity
    return {"commander": commander, "cards": cards}


def _input_expectation_result(
    assessment: Mapping,
    expected: Mapping,
) -> Dict:
    actual_codes = [issue["code"] for issue in assessment.get("issues") or []]
    expected_codes = list(expected.get("issue_codes") or [])
    checks = {
        "status": assessment.get("status") == expected.get("status"),
        "analysis_allowed": (
            assessment.get("analysis_allowed") == expected.get("analysis_allowed")
        ),
        "recommendations_allowed": (
            assessment.get("recommendations_allowed")
            == expected.get("recommendations_allowed")
        ),
        "issue_codes": set(expected_codes) <= set(actual_codes),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "expected_issue_codes": expected_codes,
        "actual_issue_codes": actual_codes,
    }


def _analysis_evidence(result: Mapping) -> Dict:
    return {
        "suggestions_add": result.get("suggestions_add") or [],
        "suggestions_cut": result.get("suggestions_cut") or [],
        "swap_pairs": result.get("swap_pairs") or [],
        "stats": result.get("stats") or {},
        "commander_synergies": result.get("commander_synergies") or [],
        "commander_archetypes": result.get("commander_archetypes") or [],
        "detected_themes": result.get("detected_themes") or [],
        "combo_suggestions": result.get("combo_suggestions") or [],
        "coverage_level": result.get("coverage_level"),
        "coverage_notes": result.get("coverage_notes"),
        "intent_summary": result.get("intent_summary") or {},
        "deck_invariants": result.get("deck_invariants") or {},
        "input_assessment": result.get("input_assessment") or {},
    }


async def _analyze(
    snapshot: Mapping,
    intent_profile: Mapping,
    ranker_mode: str,
    scryfall: FrozenCatalogScryfall,
    provider: LocalCatalogCandidateProvider,
) -> Dict:
    deck = {
        "commander": snapshot.get("commander"),
        "color_identity": snapshot.get("color_identity") or [],
        "cards": snapshot.get("cards") or [],
        "intent_profile": intent_profile,
    }
    assessment = assess_deck_input(deck)
    if not assessment["analysis_allowed"]:
        return {"input_assessment": assessment, "blocked": True}
    engine = EnhancedSuggestionEngine(
        scryfall,
        candidate_provider=provider,
        ranker_mode=ranker_mode,
    )
    result = await engine.analyze_deck(deck, deep=False)
    result = apply_recommendation_restraint(result, assessment)
    return _analysis_evidence(result)


async def execute(
    fixture_dir: Path,
    catalog_path: Path,
) -> Dict:
    fixture_dir = fixture_dir.resolve()
    catalog_path = catalog_path.resolve()
    index = _load_json(fixture_dir / "snapshot_index.json")
    manifest = _load_json(fixture_dir / "review_manifest.json")
    index_by_id = {case["case_id"]: case for case in index["cases"]}

    provider = LocalCatalogCandidateProvider(catalog_path)
    provider.catalog._ensure_loaded()
    cards_by_name = {
        str(card.get("name") or "").strip().casefold(): card
        for card in provider.catalog._cards
        if card.get("name")
    }
    scryfall = FrozenCatalogScryfall(cards_by_name)

    results = []
    for case in manifest["cases"]:
        case_id = case["case_id"]
        index_case = index_by_id[case_id]
        snapshot_path = fixture_dir / case["snapshot_file"]
        plain_path = fixture_dir / index_case["plain_text_file"]
        integrity = {
            "snapshot_hash_matches": (
                _sha256(snapshot_path) == index_case["snapshot_sha256"]
            ),
            "plain_text_hash_matches": (
                _sha256(plain_path) == index_case["plain_text_sha256"]
            ),
        }
        snapshot = _load_json(snapshot_path)
        plain_contents = _plain_snapshot_contents(plain_path)
        snapshot_cards = Counter({
            str(card.get("name") or "").strip(): int(card.get("qty", 1) or 1)
            for card in snapshot.get("cards") or []
        })
        integrity.update({
            "plain_text_commander_matches": (
                plain_contents["commander"] == snapshot.get("commander")
            ),
            "plain_text_quantities_match": (
                plain_contents["cards"] == snapshot_cards
            ),
            "index_counts_match": (
                sum(snapshot_cards.values()) == index_case["mainboard_cards"]
                and len(snapshot_cards) == index_case["unique_cards"]
            ),
        })
        intent_profile = normalize_intent_profile(case.get("intent_profile"))
        assessment = assess_deck_input(snapshot)
        input_expectation = _input_expectation_result(
            assessment,
            case["expected_input"],
        )
        legacy = await _analyze(
            snapshot,
            intent_profile,
            "legacy",
            scryfall,
            provider,
        )
        v2 = await _analyze(
            snapshot,
            intent_profile,
            "v2",
            scryfall,
            provider,
        )
        legacy_top = [
            item.get("card_name") for item in legacy.get("suggestions_add") or []
        ]
        v2_top = [
            item.get("card_name") for item in v2.get("suggestions_add") or []
        ]
        results.append({
            "case_id": case_id,
            "label": case["label"],
            "snapshot_file": case["snapshot_file"],
            "review_focus": case.get("review_focus") or [],
            "integrity": {
                **integrity,
                "passed": all(integrity.values()),
            },
            "input_expectation": input_expectation,
            "input_assessment": assessment,
            "intent_profile": intent_profile,
            "legacy": legacy,
            "v2": v2,
            "ranking_comparison": {
                "same_top_choice": legacy_top[:1] == v2_top[:1],
                "same_top_five_order": legacy_top[:5] == v2_top[:5],
                "legacy_top_five": legacy_top[:5],
                "v2_top_five": v2_top[:5],
            },
        })

    catalog_status = provider.get_status()
    return {
        "schema_version": 1,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "validation_date": manifest["validation_date"],
        "fixture_dir": str(fixture_dir.relative_to(REPO_PATH)),
        "candidate_catalog": {
            "path": str(catalog_path.relative_to(REPO_PATH)),
            **catalog_status,
        },
        "ranker_modes": ["legacy", "v2"],
        "analysis_depth": "fast",
        "case_count": len(results),
        "integrity_passed": all(case["integrity"]["passed"] for case in results),
        "input_expectations_passed": all(
            case["input_expectation"]["passed"] for case in results
        ),
        "changed_top_choice_case_ids": [
            case["case_id"]
            for case in results
            if not case["ranking_comparison"]["same_top_choice"]
        ],
        "cases": results,
    }


def main() -> int:
    args = parse_args()
    report = asyncio.run(execute(args.fixture_dir, args.catalog))
    payload = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["integrity_passed"] and report["input_expectations_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
