"""Run labeled recommendation benchmark cases through the current engine."""

from __future__ import annotations

import asyncio
from typing import Dict, List

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.recommendation_benchmark import (
    RecommendationBenchmarkCase,
    RecommendationBenchmarkResult,
    evaluate_recommendations,
)


class StaticBenchmarkScryfall:
    """Minimal Scryfall adapter backed by a benchmark's frozen card pool."""

    def __init__(self, cards: List[Dict]):
        self.cards = cards
        self.queries = []

    def extract_card_data(self, card: Dict) -> Dict:
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

    async def search_cards_by_criteria(self, query: str, limit: int = 20) -> List[Dict]:
        self.queries.append((query, limit))
        return self.cards[:limit]


async def execute_engine_benchmark_case_async(
    case: RecommendationBenchmarkCase,
    ranker_mode: str = "legacy",
) -> RecommendationBenchmarkResult:
    """Execute one frozen case through real filtering, scoring, and reasoning."""
    payload = case.payload
    cards = list(payload.get("cards") or [])
    scryfall = StaticBenchmarkScryfall(cards)
    engine = EnhancedSuggestionEngine(scryfall, ranker_mode=ranker_mode)

    if case.mode == "commander":
        commander = dict(payload["commander"])
        synergy = str(payload["synergy"])
        recommendations = await engine._search_commander_recommendations(
            commander_card=commander,
            synergies=[synergy],
            color_identity=commander.get("color_identity", []),
            commander_constraints=engine._get_commander_constraints(commander),
            max_cards=case.top_k,
            search_budget=1,
            per_synergy_limit=max(case.top_k, len(cards)),
            query_limit=len(cards),
            minimum_score=int(payload.get("minimum_score", 72)),
        )
    else:
        recommendations = await engine._generate_additions(
            gaps=dict(payload["gaps"]),
            commander=None,
            color_identity=list(payload.get("color_identity") or []),
            current_cards=list(payload.get("current_cards") or []),
            commander_synergies=[],
            commander_data=None,
            categories=list(payload.get("categories") or []),
            commander_constraints={},
            search_budget=1,
        )

    return evaluate_recommendations(
        case,
        recommendations,
        retrieved_names=[card["name"] for card in cards],
    )


def execute_engine_benchmark_case(
    case: RecommendationBenchmarkCase,
    ranker_mode: str = "legacy",
) -> RecommendationBenchmarkResult:
    """Synchronous entry point for tests and command-line reporting."""
    return asyncio.run(
        execute_engine_benchmark_case_async(case, ranker_mode=ranker_mode)
    )


async def execute_engine_benchmark_async(
    cases: List[RecommendationBenchmarkCase],
    ranker_mode: str = "legacy",
) -> List[RecommendationBenchmarkResult]:
    """Execute cases serially to keep reports deterministic and easy to debug."""
    results = []
    for case in cases:
        results.append(
            await execute_engine_benchmark_case_async(
                case,
                ranker_mode=ranker_mode,
            )
        )
    return results


def execute_engine_benchmark(
    cases: List[RecommendationBenchmarkCase],
    ranker_mode: str = "legacy",
) -> List[RecommendationBenchmarkResult]:
    return asyncio.run(
        execute_engine_benchmark_async(cases, ranker_mode=ranker_mode)
    )
