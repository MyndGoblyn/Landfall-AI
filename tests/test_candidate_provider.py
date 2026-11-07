import asyncio
import sys
from pathlib import Path

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.candidate_provider import ScryfallCandidateProvider
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


class RecordingScryfall:
    def __init__(self):
        self.calls = []

    async def search_cards_by_criteria(self, query, limit=20):
        self.calls.append((query, limit))
        return [{"name": "Candidate"}]


class InjectedProvider:
    def __init__(self):
        self.calls = []

    async def search_cards(self, query, limit):
        self.calls.append((query, limit))
        return []


class ConcurrentProvider:
    def __init__(self):
        self.calls = []
        self.active = 0
        self.max_active = 0

    async def search_cards(self, query, limit):
        self.calls.append((query, limit))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return []
        finally:
            self.active -= 1


def test_scryfall_candidate_provider_preserves_live_search_contract():
    scryfall = RecordingScryfall()
    provider = ScryfallCandidateProvider(scryfall)

    result = asyncio.run(provider.search_cards("t:artifact", limit=32))

    assert result == [{"name": "Candidate"}]
    assert scryfall.calls == [("t:artifact", 32)]


def test_enhanced_engine_accepts_injected_candidate_provider():
    scryfall = RecordingScryfall()
    provider = InjectedProvider()
    engine = EnhancedSuggestionEngine(scryfall, candidate_provider=provider)

    with pytest.raises(ValueError, match="No commanders found"):
        asyncio.run(
            engine.get_random_commander(colors=["U"], search_text="artifacts")
        )

    assert provider.calls
    assert not scryfall.calls


def test_deck_addition_search_is_parallel_but_bounded():
    provider = ConcurrentProvider()
    engine = EnhancedSuggestionEngine(
        RecordingScryfall(),
        candidate_provider=provider,
    )

    results = asyncio.run(engine._generate_additions(
        gaps={"roles": {}},
        commander=None,
        color_identity=["U"],
        current_cards=[],
        commander_synergies=[],
        commander_data=None,
        categories=[
            "ramp",
            "draw",
            "removal",
            "counter",
            "recursion",
            "tutor",
            "protection",
        ],
        search_budget=7,
        search_concurrency=3,
    ))

    assert results == []
    assert len(provider.calls) == 7
    assert provider.max_active == 3


def test_construction_ramp_search_includes_mana_rocks_without_changing_public_query():
    public_provider = InjectedProvider()
    construction_provider = InjectedProvider()
    public_engine = EnhancedSuggestionEngine(
        RecordingScryfall(),
        candidate_provider=public_provider,
    )
    construction_engine = EnhancedSuggestionEngine(
        RecordingScryfall(),
        candidate_provider=construction_provider,
    )

    asyncio.run(public_engine._generate_additions(
        gaps={"roles": {"ramp": {}}},
        commander=None,
        color_identity=["U"],
        current_cards=[],
        commander_synergies=[],
        commander_data=None,
        categories=["ramp"],
    ))
    asyncio.run(construction_engine._generate_additions(
        gaps={"roles": {"ramp": {}}},
        commander=None,
        color_identity=["U"],
        current_cards=[],
        commander_synergies=[],
        commander_data=None,
        categories=["ramp"],
        construction_context=True,
    ))

    assert 't:mana' in public_provider.calls[0][0]
    assert 'o:"add {"' not in public_provider.calls[0][0]
    assert 'o:"add {"' in construction_provider.calls[0][0]
