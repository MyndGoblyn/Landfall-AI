import asyncio
import importlib
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def test_deck_intent_endpoint_persists_validated_profile():
    async def run():
        env_keys = [
            "USE_IN_MEMORY_DB",
            "CAPTCHA_REQUIRED",
            "REQUIRE_EMAIL_VERIFICATION",
            "RESET_ACCOUNTS_KEY",
            "CANDIDATE_CATALOG_ENABLED",
        ]
        previous_env = {key: os.environ.get(key) for key in env_keys}
        previous_server = sys.modules.get("server")
        try:
            os.environ["USE_IN_MEMORY_DB"] = "true"
            os.environ["CAPTCHA_REQUIRED"] = "false"
            os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
            os.environ["RESET_ACCOUNTS_KEY"] = "intent-test-key"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")
            deck = server.Deck(user_id="user-1", name="Intent Test")
            deck_document = deck.model_dump()
            deck_document["created_at"] = deck_document["created_at"].isoformat()
            await server.db.decks.insert_one(deck_document)

            profile = server.DeckIntentProfile(
                confirmed=True,
                power_level_min=6,
                power_level_max=7,
                budget_mode="strict",
                max_card_price_usd=5,
                optimization_mode="tune",
                protected_cards=["Pet Card"],
                intentional_constraints=["typal_core"],
            )
            updated = await server.update_deck_intent(
                deck.id,
                profile,
                current_user={"id": "user-1"},
            )

            assert updated["intent_profile"]["confirmed"]
            assert updated["intent_profile"]["max_card_price_usd"] == 5
            stored = await server.db.decks.find_one({"id": deck.id})
            assert stored["intent_profile"]["protected_cards"] == ["Pet Card"]
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
