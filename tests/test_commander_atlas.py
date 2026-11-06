import asyncio
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


from services.commander_atlas import CommanderAtlas
from services.commander_profile_registry import CommanderProfileRegistry
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


def _card(name, oracle_id, colors, cmc, oracle_text, type_line="Legendary Creature — Human"):
    return {
        "name": name,
        "oracle_id": oracle_id,
        "color_identity": colors,
        "colors": colors,
        "cmc": cmc,
        "type_line": type_line,
        "oracle_text": oracle_text,
        "legalities": {"commander": "legal"},
        "image_uris": {"normal": f"https://cards.example/{oracle_id}.jpg"},
    }


class FakeProvider:
    def __init__(self, cards):
        self.cards = cards

    async def search_cards(self, _query, limit):
        return self.cards[:limit]

    def cache_identity(self):
        return ("fake-atlas", len(self.cards))

    def get_status(self):
        return {
            "type": "local_catalog",
            "catalog_version": "test-catalog",
            "source_updated_at": "2026-11-06T00:00:00Z",
        }


def test_reviewed_profiles_require_exact_oracle_identity():
    registry = CommanderProfileRegistry.load_default()
    profile = registry.match({
        "oracle_id": "0310dfdb-0498-488d-9f1a-279f8239e024",
        "name": "Meren of Clan Nel Toth",
    })
    wrong_identity = registry.match({
        "oracle_id": "not-meren",
        "name": "Meren of Clan Nel Toth",
    })

    assert profile["confidence"] == "core"
    assert "graveyard_reanimator" in profile["archetype_ids"]
    assert wrong_identity is None
    assert registry.count() >= 12


def test_reviewed_profile_adds_inspectable_archetype_evidence():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    card = _card(
        "Meren of Clan Nel Toth",
        "0310dfdb-0498-488d-9f1a-279f8239e024",
        ["B", "G"],
        4,
        "Whenever another creature you control dies, get an experience counter.",
    )

    synergies, archetypes, profile = engine._merge_reviewed_commander_profile(
        card,
        ["sacrifice"],
        [],
    )

    assert profile["name"] == "Meren of Clan Nel Toth"
    assert "graveyard" in synergies
    assert {entry["id"] for entry in archetypes} >= {
        "aristocrats_sacrifice_engine",
        "graveyard_reanimator",
    }
    assert all(
        "reviewed_commander_profile" in entry["evidence_sources"]
        for entry in archetypes
    )


def test_reviewed_profile_benchmark_has_actionable_evidence():
    registry = CommanderProfileRegistry.load_default()
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    registered_archetypes = {
        entry["id"] for entry in engine.archetype_registry.entries
    }

    for profile in registry.entries:
        assert set(profile["archetype_ids"]).issubset(registered_archetypes)
        assert profile["support_needs"]
        assert profile["common_failure_modes"]
        assert profile["win_paths"]
        assert profile["packages"]
        assert "oracle_text" in profile["evidence_sources"]
        assert all(
            similar["name"] and similar["reason"]
            for similar in profile["similar_commanders"]
        )


def test_atlas_filters_and_ranks_without_popularity_order():
    async def run():
        cards = [
            _card(
                "Talrand, Sky Summoner",
                "ea1eb902-a23c-44ff-9169-19baf71de238",
                ["U"],
                4,
                "Whenever you cast an instant or sorcery spell, create a Drake token.",
            ),
            _card(
                "Meren of Clan Nel Toth",
                "0310dfdb-0498-488d-9f1a-279f8239e024",
                ["B", "G"],
                4,
                "Whenever another creature you control dies, get an experience counter.",
            ),
            _card(
                "Atraxa, Grand Unifier",
                "abbcb153-0763-44c6-964f-b4ff0eb64257",
                ["W", "U", "B", "G"],
                7,
                "When Atraxa enters, reveal cards and put one of each card type into your hand.",
            ),
            _card(
                "Meren's Impostor",
                "wrong-identity",
                ["B"],
                3,
                "Whenever this attacks, draw a card.",
            ),
        ]
        provider = FakeProvider(cards)
        engine = EnhancedSuggestionEngine(
            scryfall_service=None,
            candidate_provider=provider,
        )
        atlas = CommanderAtlas(provider, engine)

        alphabetical = await atlas.search(page_size=10)
        exact_bg = await atlas.search(colors="BG", color_mode="exact", page_size=10)
        inclusive_u = await atlas.search(colors="U", color_mode="inclusive", page_size=10)
        graveyard = await atlas.search(archetype="graveyard", page_size=10)
        query = await atlas.search(query="meren clan", page_size=10)

        assert [row["name"] for row in alphabetical["commanders"]] == [
            "Atraxa, Grand Unifier",
            "Meren of Clan Nel Toth",
            "Meren's Impostor",
            "Talrand, Sky Summoner",
        ]
        assert [row["name"] for row in exact_bg["commanders"]] == [
            "Meren of Clan Nel Toth"
        ]
        assert {row["name"] for row in inclusive_u["commanders"]} == {
            "Atraxa, Grand Unifier",
            "Talrand, Sky Summoner",
        }
        assert [row["name"] for row in graveyard["commanders"]] == [
            "Meren of Clan Nel Toth"
        ]
        assert query["commanders"][0]["name"] == "Meren of Clan Nel Toth"
        assert query["catalog"]["catalog_version"] == "test-catalog"
        talrand = next(
            row for row in alphabetical["commanders"]
            if row["name"] == "Talrand, Sky Summoner"
        )
        assert talrand["playstyles"] == ["control", "value"]

    asyncio.run(run())
