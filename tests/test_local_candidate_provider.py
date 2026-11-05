import asyncio
import json
import sys
from pathlib import Path

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import (
    CatalogQueryError,
    LocalCardCatalog,
    compile_catalog_query,
)
from services.candidate_provider import (
    FallbackCandidateProvider,
    LocalCatalogCandidateProvider,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


RETRIEVAL_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "golden_candidate_retrieval.json"
)


def card(
    name,
    *,
    type_line="Artifact",
    oracle_text="",
    color_identity=None,
    rank=100,
    commander_legality="legal",
    cmc=2,
    keywords=None,
):
    return {
        "name": name,
        "oracle_id": name.lower().replace(" ", "-"),
        "type_line": type_line,
        "oracle_text": oracle_text,
        "color_identity": color_identity or [],
        "edhrec_rank": rank,
        "cmc": cmc,
        "keywords": keywords or [],
        "legalities": {"commander": commander_legality},
    }


def write_catalog(path: Path, cards, version="test-v1"):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "catalog_version": version,
                "source_updated_at": "2026-07-30T00:00:00Z",
                "cards": cards,
            }
        ),
        encoding="utf-8",
    )


class RecordingProvider:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    async def search_cards(self, query, limit):
        self.calls.append((query, limit))
        return self.results[:limit]


def test_catalog_applies_boolean_identity_legality_exclusion_and_popularity(tmp_path):
    path = tmp_path / "catalog.json"
    write_catalog(
        path,
        [
            card("Popular Draw", oracle_text="Draw two cards.", color_identity=["U"], rank=2),
            card("Mana Rock", oracle_text="{T}: Add one mana of any color.", rank=1),
            card("Less Popular Draw", oracle_text="Draw a card.", rank=30),
            card("Red Draw", oracle_text="Draw two cards.", color_identity=["R"], rank=3),
            card("Banned Draw", oracle_text="Draw three cards.", rank=4, commander_legality="banned"),
        ],
    )
    catalog = LocalCardCatalog(path)

    results = catalog.search(
        '(o:draw OR (t:artifact o:mana)) id<=u f:commander -!"Popular Draw"',
        limit=10,
    )

    assert [result["name"] for result in results] == ["Mana Rock", "Less Popular Draw"]
    assert catalog.get_status()["catalog_version"] == "test-v1"
    assert catalog.get_status()["card_count"] == 5


def test_golden_candidate_retrieval_cases_clear_recall_and_rejection_gates(tmp_path):
    payload = json.loads(RETRIEVAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert len(payload["cases"]) >= 4

    failures = {}
    for case_value in payload["cases"]:
        path = tmp_path / f'{case_value["id"]}.json'
        write_catalog(path, case_value["cards"], version=case_value["id"])
        results = LocalCardCatalog(path).search(case_value["query"], case_value["limit"])
        names = [result["name"] for result in results]
        missing = set(case_value["required_names"]) - set(names)
        rejected = set(case_value["rejected_names"]) & set(names)
        wrong_order = names[: len(case_value["expected_order"])] != case_value["expected_order"]
        if missing or rejected or wrong_order:
            failures[case_value["id"]] = {
                "missing": sorted(missing),
                "rejected": sorted(rejected),
                "actual_order": names,
            }

    assert not failures


def test_catalog_searches_double_faces_and_vanilla_regex(tmp_path):
    path = tmp_path / "catalog.json"
    double_faced = card("Front // Back", type_line="Creature", color_identity=["G"], rank=2)
    double_faced["card_faces"] = [
        {"name": "Front", "type_line": "Creature", "oracle_text": ""},
        {"name": "Back", "type_line": "Enchantment", "oracle_text": "Creatures with no abilities get +2/+2."},
    ]
    vanilla = card(
        "Plain Bear",
        type_line="Creature — Bear",
        oracle_text="",
        color_identity=["G"],
        rank=1,
    )
    write_catalog(path, [double_faced, vanilla])
    catalog = LocalCardCatalog(path)

    face_results = catalog.search('t:enchantment o:"no abilities" id<=g', 10)
    vanilla_results = catalog.search("t:creature -o:/./ id<=g", 10)

    assert [result["name"] for result in face_results] == ["Front // Back"]
    assert [result["name"] for result in vanilla_results] == ["Plain Bear"]


def test_catalog_supports_engine_generated_query_families():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    synergy_names = [
        "enchantment",
        "counters",
        "typal",
        "colorless_big_mana",
        "target_spells",
        "control_finisher",
        "hand_size_pressure",
        "flash_control",
        "vanilla_creatures",
        "artifact",
        "board_conversion",
        "blink",
        "combat_damage",
        "attack_triggers",
        "extra_combat",
        "creature",
        "donation",
        "exile",
        "forced_reanimation",
        "goad",
        "graveyard",
        "instant_sorcery",
        "landfall",
        "lifegain",
        "sacrifice",
        "temporary_drawback",
        "tokens",
        "artifact_tokens",
        "voltron",
    ]
    constraints = {"typal_types": ["Dragon"], "counter_plan": "board_counters"}
    queries = [
        engine._build_query_for_synergy(name, ["U", "R"], constraints)
        for name in synergy_names
    ]
    queries.extend(
        engine._build_query_for_role(role, ["U"], ["artifact"], {})
        for role in ["draw", "ramp", "removal", "sweeper", "interaction", "protection", "synergy"]
    )
    random_terms = [
        "artifacts",
        "enchantments",
        "graveyard",
        "recursion",
        "reanimator",
        "aristocrats",
        "tokens",
        "treasure",
        "lifegain",
        "counters",
        "spellslinger",
        "blink",
        "exile",
        "card draw",
        "mill",
    ]
    queries.extend(
        engine._build_random_commander_query(colors=["U"], search_text=term)
        for term in random_terms
    )

    for query in queries:
        assert query
        compile_catalog_query(query)

    for entry in engine.mechanics_registry.entries:
        for query in entry.get("scryfall_query_terms") or []:
            compile_catalog_query(query)


def test_local_provider_expands_engine_pool_without_changing_display_count(tmp_path):
    path = tmp_path / "catalog.json"
    cards = [card(f"Draw {index}", oracle_text="Draw a card.", rank=index) for index in range(1, 101)]
    write_catalog(path, cards)
    provider = LocalCatalogCandidateProvider(path, expansion_factor=4, maximum_limit=80)
    engine = EnhancedSuggestionEngine(scryfall_service=None, candidate_provider=provider)

    results = asyncio.run(engine._search_candidate_cards("o:draw f:commander", limit=20))

    assert len(results) == 80
    assert results[0]["name"] == "Draw 1"
    assert results[-1]["name"] == "Draw 80"


def test_catalog_identity_and_results_change_after_atomic_snapshot_refresh(tmp_path):
    path = tmp_path / "catalog.json"
    write_catalog(path, [card("Old Draw", oracle_text="Draw a card.")], version="v1")
    provider = LocalCatalogCandidateProvider(path)
    first = asyncio.run(provider.search_cards("o:draw", 10))
    first_identity = provider.cache_identity()

    write_catalog(
        path,
        [card("Newer Draw Candidate", oracle_text="Draw two cards.")],
        version="version-two",
    )
    second = asyncio.run(provider.search_cards("o:draw", 10))

    assert [result["name"] for result in first] == ["Old Draw"]
    assert [result["name"] for result in second] == ["Newer Draw Candidate"]
    assert provider.cache_identity() != first_identity


def test_fallback_provider_uses_live_search_for_missing_catalog(tmp_path):
    local = LocalCatalogCandidateProvider(tmp_path / "missing.json")
    live = RecordingProvider([card("Live Candidate")])
    provider = FallbackCandidateProvider(local, live)

    results = asyncio.run(provider.search_cards("o:draw", limit=20))

    assert [result["name"] for result in results] == ["Live Candidate"]
    assert live.calls == [("o:draw", 20)]
    assert provider.get_status()["counters"]["primary_errors"] == 1


def test_fallback_provider_uses_live_search_for_unsupported_query(tmp_path):
    path = tmp_path / "catalog.json"
    write_catalog(path, [card("Local Candidate")])
    live = RecordingProvider([card("Live Candidate")])
    provider = FallbackCandidateProvider(LocalCatalogCandidateProvider(path), live)

    results = asyncio.run(provider.search_cards("artist:someone", limit=5))

    assert [result["name"] for result in results] == ["Live Candidate"]
    assert provider.get_status()["counters"]["primary_errors"] == 1


def test_unsupported_local_query_fails_closed():
    with pytest.raises(CatalogQueryError, match="Unsupported candidate-query field"):
        compile_catalog_query("artist:someone")
