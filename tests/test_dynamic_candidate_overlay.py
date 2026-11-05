import asyncio
import sys
from pathlib import Path

BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


class OverlayScryfall:
    def __init__(self, cards=None, error=None):
        self.cards = cards or []
        self.error = error

    async def get_card_bulk(self, names):
        if self.error:
            raise self.error
        return self.cards


def fresh_card(name, price="1.00", colors=None, legality="legal"):
    return {
        "name": name,
        "type_line": "Instant",
        "color_identity": colors or [],
        "legalities": {"commander": legality},
        "prices": {"usd": price},
    }


def test_dynamic_overlay_refreshes_price_and_rejects_newly_illegal_card():
    service = OverlayScryfall([
        fresh_card("Safe Choice", "2.25", ["U"]),
        fresh_card("Banned Choice", "1.00", ["U"], "banned"),
    ])
    engine = EnhancedSuggestionEngine(service, planner_mode="v3")

    result = asyncio.run(
        engine._apply_dynamic_candidate_overlay(
            [
                {"card_name": "Safe Choice", "price": 9.0},
                {"card_name": "Banned Choice", "price": 1.0},
            ],
            None,
            ["U"],
        )
    )

    assert [item["card_name"] for item in result] == ["Safe Choice"]
    assert result[0]["price"] == 2.25
    assert result[0]["data_freshness"]["dynamic_source"] == "live_scryfall"
    assert result[0]["data_freshness"]["live_checked"] is True


def test_dynamic_overlay_enforces_refreshed_strict_budget():
    service = OverlayScryfall([fresh_card("Price Spike", "7.00")])
    engine = EnhancedSuggestionEngine(service, planner_mode="v3")

    result = asyncio.run(
        engine._apply_dynamic_candidate_overlay(
            [{"card_name": "Price Spike", "price": 2.0}],
            {
                "budget_mode": "strict",
                "max_card_price_usd": 5,
                "confirmed": True,
            },
            [],
        )
    )

    assert result == []


def test_dynamic_overlay_falls_back_without_changing_selection():
    service = OverlayScryfall(error=RuntimeError("network unavailable"))
    engine = EnhancedSuggestionEngine(service, planner_mode="v3")

    result = asyncio.run(
        engine._apply_dynamic_candidate_overlay(
            [{"card_name": "Offline Choice", "price": 3.0}],
            None,
            [],
        )
    )

    assert result[0]["card_name"] == "Offline Choice"
    assert result[0]["price"] == 3.0
    assert result[0]["data_freshness"] == {
        "semantic_source": "reviewed_catalog",
        "dynamic_source": "catalog_snapshot",
        "live_checked": False,
    }
