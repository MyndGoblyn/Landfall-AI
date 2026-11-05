import asyncio
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.deck_parser import DeckParser


class StubScryfall:
    def __init__(self):
        self.searches = []

    async def search_card(self, name):
        self.searches.append(name)
        return None

    async def get_card_bulk(self, names):
        return []


def archidekt_row(name, categories, quantity=1, colors=None):
    return {
        "quantity": quantity,
        "categories": categories,
        "card": {
            "collectorNumber": "1",
            "edition": {"editioncode": "TST"},
            "oracleCard": {
                "name": name,
                "text": "Draw a card.",
                "cmc": 2,
                "colors": colors or ["Blue"],
                "colorIdentity": colors or ["Blue"],
                "superTypes": [],
                "types": ["Creature"],
                "subTypes": ["Wizard"],
                "keywords": [],
            },
        },
    }


def moxfield_entry(name, quantity=1, board_type="mainboard"):
    return {
        "quantity": quantity,
        "boardType": board_type,
        "card": {
            "name": name,
            "type_line": "Instant",
            "oracle_text": "Draw a card.",
            "cmc": 1,
            "colors": ["U"],
            "color_identity": ["U"],
            "set": "tst",
            "cn": "1",
        },
    }


def test_archidekt_normalizes_to_mainboard_only():
    scryfall = StubScryfall()
    parser = DeckParser(scryfall)
    payload = {
        "categories": [
            {"name": "Maybeboard", "includedInDeck": False},
            {"name": "Main", "includedInDeck": True},
        ],
        "cards": [
            archidekt_row("Talrand, Sky Summoner", ["Commander"]),
            archidekt_row("Island", ["Main"], quantity=30),
            archidekt_row("Uncategorized Card", None),
            archidekt_row("Maybe Card", ["Maybeboard"]),
            archidekt_row("Sideboard Card", ["Sideboard"]),
        ],
    }

    result = asyncio.run(parser._parse_archidekt_payload(payload))

    assert result["commander"] == "Talrand, Sky Summoner"
    assert result["color_identity"] == ["U"]
    assert [(card["name"], card["qty"]) for card in result["cards"]] == [
        ("Island", 30),
        ("Uncategorized Card", 1),
    ]
    assert scryfall.searches == []


def test_moxfield_current_boards_shape_uses_embedded_card_data():
    scryfall = StubScryfall()
    parser = DeckParser(scryfall)
    payload = {
        "boards": {
            "commanders": {
                "count": 1,
                "cards": {
                    "commander": moxfield_entry(
                        "Talrand, Sky Summoner", board_type="commanders"
                    )
                },
            },
            "mainboard": {
                "count": 99,
                "cards": {"island": moxfield_entry("Island", quantity=30)},
            },
            "maybeboard": {
                "count": 1,
                "cards": {"maybe": moxfield_entry("Maybe Card")},
            },
        }
    }

    result = asyncio.run(parser._parse_moxfield_payload(payload))

    assert result["commander"] == "Talrand, Sky Summoner"
    assert result["color_identity"] == ["U"]
    assert [(card["name"], card["qty"]) for card in result["cards"]] == [
        ("Island", 30)
    ]
    assert result["cards"][0]["collector_number"] == "1"
    assert scryfall.searches == []


def test_moxfield_legacy_shape_remains_supported():
    parser = DeckParser(StubScryfall())
    payload = {
        "commanders": [moxfield_entry("Talrand, Sky Summoner")],
        "mainboard": {"island": moxfield_entry("Island", quantity=30)},
    }

    result = asyncio.run(parser._parse_moxfield_payload(payload))

    assert result["commander"] == "Talrand, Sky Summoner"
    assert result["cards"][0]["qty"] == 30


def test_moxfield_preserves_paired_commanders_and_combined_identity():
    parser = DeckParser(StubScryfall())
    first = moxfield_entry("Partner One")
    first["card"]["color_identity"] = ["U"]
    second = moxfield_entry("Partner Two")
    second["card"]["color_identity"] = ["R"]
    payload = {
        "commanders": [first, second],
        "mainboard": {"island": moxfield_entry("Island", quantity=30)},
    }

    result = asyncio.run(parser._parse_moxfield_payload(payload))

    assert result["commander"] == "Partner One"
    assert result["commanders"] == ["Partner One", "Partner Two"]
    assert result["color_identity"] == ["U", "R"]
