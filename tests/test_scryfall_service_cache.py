import asyncio
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.in_memory_db import InMemoryDB
from services.scryfall_service import ScryfallService


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
        "prices": {"usd": "0.10"},
        "keywords": ["Flying"],
        "legalities": {"commander": "legal"},
        "image_uris": {"normal": "front.jpg"},
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
