import asyncio
import importlib
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.in_memory_db import InMemoryDB
from services.scryfall_service import ScryfallService


class StubCollectionService(ScryfallService):
    def __init__(self, missing=None):
        super().__init__()
        self.collection_request_interval = 0
        self.collection_batches = []
        self.missing = {self._normalize_key(name) for name in (missing or [])}
        self.fuzzy_fallbacks = []

    async def _fetch_collection_batch(self, names):
        self.collection_batches.append(list(names))
        return {
            self._normalize_key(name): {
                "name": name,
                "type_line": "Instant",
                "oracle_text": "Draw a card.",
                "cmc": 1,
            }
            for name in names
            if self._normalize_key(name) not in self.missing
        }

    async def _search_card_with_source(self, name, fuzzy=True):
        self.fuzzy_fallbacks.append(name)
        return {
            "name": "Lightning Bolt",
            "type_line": "Instant",
            "oracle_text": "Lightning Bolt deals 3 damage to any target.",
            "cmc": 1,
        }, "test-fuzzy"


class FakeCollectionResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False

    async def json(self):
        return self.body


class FakeCollectionSession:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeCollectionResponse(self.body)


def test_scryfall_client_uses_meaningful_api_headers():
    async def run():
        service = ScryfallService()
        session = await service.get_session()
        try:
            assert session.headers["User-Agent"].startswith("LandfallAI/")
            assert "application/json" in session.headers["Accept"]
        finally:
            await service.close()

    asyncio.run(run())


def test_slim_card_preserves_engine_fields_and_trims_unused_payload():
    service = ScryfallService()
    card = {
        "name": "Test // Back",
        "oracle_id": "oracle-1",
        "type_line": "Legendary Creature",
        "oracle_text": "Draw a card.",
        "mana_cost": "{1}{U}",
        "cmc": 2,
        "power": "1",
        "toughness": "3",
        "colors": ["U"],
        "color_identity": ["U"],
        "set": "tst",
        "collector_number": "1",
        "prices": {"usd": "0.10", "eur": "0.09"},
        "keywords": ["Flying"],
        "legalities": {"commander": "legal", "standard": "not_legal"},
        "image_uris": {"normal": "front.jpg", "art_crop": "large-unused.jpg"},
        "scryfall_uri": "https://scryfall.com/card/test",
        "purchase_uris": {"tcgplayer": "unused"},
        "all_parts": [{"name": "unused"}],
        "card_faces": [
            {
                "name": "Test",
                "type_line": "Legendary Creature",
                "oracle_text": "Front text.",
                "mana_cost": "{1}{U}",
                "cmc": 2,
                "colors": ["U"],
                "image_uris": {"normal": "front.jpg"},
                "artist": "unused",
            },
            {
                "name": "Back",
                "type_line": "Enchantment",
                "oracle_text": "Back text.",
                "mana_cost": "",
                "cmc": 2,
                "colors": ["U"],
                "image_uris": {"normal": "back.jpg"},
                "purchase_uris": {"tcgplayer": "unused"},
            },
        ],
    }

    slim = service._slim_card(card)

    assert slim["name"] == "Test // Back"
    assert slim["card_faces"][0]["image_uris"]["normal"] == "front.jpg"
    assert slim["card_faces"][1]["oracle_text"] == "Back text."
    assert "purchase_uris" not in slim
    assert "all_parts" not in slim
    assert slim["prices"] == {"usd": "0.10"}
    assert slim["legalities"] == {"commander": "legal"}
    assert slim["image_uris"] == {"normal": "front.jpg"}
    assert "artist" not in slim["card_faces"][0]
    assert "purchase_uris" not in slim["card_faces"][1]


def test_l2_card_cache_supports_fuzzy_alias_without_exact_alias():
    async def run():
        db = InMemoryDB()
        service = ScryfallService(db=db)
        card = {
            "name": "Vivi Ornitier",
            "oracle_id": "vivi-oracle",
            "type_line": "Legendary Creature",
            "oracle_text": "Whenever you cast a noncreature spell, create a Treasure token.",
            "cmc": 3,
            "color_identity": ["U", "R"],
            "legalities": {"commander": "legal"},
        }

        await service._write_card_to_l2(card, lookup_key="viv")

        fuzzy_hit = await service._read_card_from_l2("Viv", fuzzy=True)
        exact_alias_miss = await service._read_card_from_l2("Viv", fuzzy=False)
        exact_canonical_hit = await service._read_card_from_l2("Vivi Ornitier", fuzzy=False)

        assert fuzzy_hit["name"] == "Vivi Ornitier"
        assert exact_alias_miss is None
        assert exact_canonical_hit["name"] == "Vivi Ornitier"

    asyncio.run(run())


def test_l2_search_cache_hydrates_ordered_slim_cards():
    async def run():
        db = InMemoryDB()
        service = ScryfallService(db=db)
        cards = [
            {"name": "Opt", "type_line": "Instant", "oracle_text": "Scry 1. Draw a card.", "cmc": 1},
            {"name": "Ponder", "type_line": "Sorcery", "oracle_text": "Look at the top three cards.", "cmc": 1},
        ]

        await service._write_search_to_l2("spells::2", "t:instant", 2, cards)
        hydrated = await service._read_search_from_l2("spells::2")

        assert [card["name"] for card in hydrated] == ["Opt", "Ponder"]

    asyncio.run(run())


def test_cache_status_tracks_l2_then_l1_hits():
    async def run():
        db = InMemoryDB()
        service = ScryfallService(db=db)
        await service._write_card_to_l2(
            {"name": "Opt", "type_line": "Instant", "oracle_text": "Scry 1. Draw a card.", "cmc": 1},
            lookup_key="opt",
        )

        _card, source = await service._search_card_with_source("Opt")
        assert source == "l2"
        _card, source = await service._search_card_with_source("Opt")
        assert source == "l1"

        status = service.get_cache_status()
        assert status["persistent_cache_enabled"] is True
        assert status["l1_valid_entries"] == 1
        assert status["counters"]["card_l2_hits"] == 1
        assert status["counters"]["card_l1_hits"] == 1

    asyncio.run(run())


def test_bulk_lookup_uses_collection_batches_and_preserves_input_order():
    async def run():
        service = StubCollectionService()
        names = [f"Card {index}" for index in range(80)] + ["Card 0"]

        cards = await service.get_card_bulk(names)

        assert [len(batch) for batch in service.collection_batches] == [75, 5]
        assert [card["name"] for card in cards] == names
        assert service.fuzzy_fallbacks == []

    asyncio.run(run())


def test_bulk_lookup_keeps_fuzzy_fallback_for_unresolved_names():
    async def run():
        service = StubCollectionService(missing={"Ligthning Bolt"})

        cards = await service.get_card_bulk(["Sol Ring", "Ligthning Bolt"])

        assert [card["name"] for card in cards] == ["Sol Ring", "Lightning Bolt"]
        assert service.fuzzy_fallbacks == ["Ligthning Bolt"]

    asyncio.run(run())


def test_collection_response_maps_results_around_not_found_identifiers():
    async def run():
        service = ScryfallService()
        session = FakeCollectionSession({
            "data": [
                {"name": "Fire // Ice", "type_line": "Instant", "cmc": 2},
                {"name": "Opt", "type_line": "Instant", "cmc": 1},
            ],
            "not_found": [{"name": "Missing Card"}],
        })

        async def get_fake_session():
            return session

        service.get_session = get_fake_session
        resolved = await service._fetch_collection_batch(
            ["Fire", "Missing Card", "Opt"]
        )

        assert resolved["fire"]["name"] == "Fire // Ice"
        assert "missing card" not in resolved
        assert resolved["opt"]["name"] == "Opt"
        assert session.calls[0]["json"] == {
            "identifiers": [
                {"name": "Fire"},
                {"name": "Missing Card"},
                {"name": "Opt"},
            ]
        }

    asyncio.run(run())


def test_admin_scryfall_cache_status_uses_existing_admin_key():
    async def run():
        env_keys = [
            "USE_IN_MEMORY_DB",
            "CAPTCHA_REQUIRED",
            "REQUIRE_EMAIL_VERIFICATION",
            "RESET_ACCOUNTS_KEY",
            "CANDIDATE_CATALOG_ENABLED",
            "RECOMMENDATION_RANKER_MODE",
            "DECK_ROLE_ASSESSMENT_MODE",
        ]
        previous_env = {key: os.environ.get(key) for key in env_keys}
        previous_server = sys.modules.get("server")
        try:
            os.environ["USE_IN_MEMORY_DB"] = "true"
            os.environ["CAPTCHA_REQUIRED"] = "false"
            os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
            os.environ["RESET_ACCOUNTS_KEY"] = "diagnostic-key"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            os.environ["RECOMMENDATION_RANKER_MODE"] = "shadow"
            os.environ["DECK_ROLE_ASSESSMENT_MODE"] = "effective"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")

            await server.scryfall_service._write_card_to_l2(
                {"name": "Sol Ring", "type_line": "Artifact", "oracle_text": "{T}: Add {C}{C}.", "cmc": 1},
                lookup_key="sol ring",
            )

            response = await server.scryfall_cache_status(x_reset_key="diagnostic-key")

            assert response.persistent_cache_enabled is True
            assert response.collection_counts["scryfall_cards"] == 1
            assert response.collection_counts["scryfall_searches"] == 0
            assert response.candidate_provider["type"] == "scryfall"
            assert response.recommendation_ranker["mode"] == "shadow"
            assert response.deck_role_assessment["mode"] == "effective"
        finally:
            sys.modules.pop("server", None)
            if previous_server is not None:
                sys.modules["server"] = previous_server
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    asyncio.run(run())
