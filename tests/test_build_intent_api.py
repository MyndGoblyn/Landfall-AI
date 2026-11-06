import asyncio
import importlib
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def test_build_intent_preview_create_migrate_and_update():
    async def run():
        env_keys = [
            "USE_IN_MEMORY_DB",
            "CAPTCHA_REQUIRED",
            "REQUIRE_EMAIL_VERIFICATION",
            "CANDIDATE_CATALOG_ENABLED",
        ]
        previous_env = {key: os.environ.get(key) for key in env_keys}
        previous_server = sys.modules.get("server")
        try:
            os.environ["USE_IN_MEMORY_DB"] = "true"
            os.environ["CAPTCHA_REQUIRED"] = "false"
            os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")
            user = {"id": "build-user"}
            intent = server.BuildIntent(
                confirmed=True,
                deck_name="Talrand control",
                starting_point="commander",
                commander_name="Talrand, Sky Summoner",
                playstyle="control",
                target_bracket=3,
                budget_mode="target",
                budget_limit_usd=120,
                build_shape="core_shell",
            )

            preview = await server.preview_build_intent(intent, current_user=user)
            assert preview["mapping"]["construction"]["enabled"] is False
            created = await server.create_deck(
                server.DeckCreate(
                    name="Talrand control",
                    commander="Talrand, Sky Summoner",
                    build_intent=intent,
                ),
                current_user=user,
            )
            stored = await server.db.decks.find_one({"id": created.id})
            assert stored["build_intent"]["schema_version"] == 1
            assert stored["intent_profile"]["confirmed"]
            assert stored["intent_profile"]["strategy_priorities"][:2] == [
                "stack_interaction",
                "card_velocity",
            ]

            legacy = server.Deck(
                user_id=user["id"],
                name="Legacy Deck",
                commander="Meren of Clan Nel Toth",
                intent_profile=server.DeckIntentProfile(
                    confirmed=True,
                    budget_mode="strict",
                    max_card_price_usd=4,
                ),
            )
            legacy_document = legacy.model_dump()
            legacy_document.pop("build_intent", None)
            legacy_document["created_at"] = legacy_document["created_at"].isoformat()
            await server.db.decks.insert_one(legacy_document)

            migrated = await server.get_deck_build_intent(legacy.id, current_user=user)
            assert migrated["source"] == "migrated_deck_intent_v1"
            assert migrated["intent"]["existing_deck_id"] == legacy.id

            updated_intent = server.BuildIntent.model_validate({
                **migrated["intent"],
                "confirmed": True,
                "notes": "Keep the creature toolbox intact.",
            })
            updated = await server.update_deck_build_intent(
                legacy.id,
                updated_intent,
                current_user=user,
            )
            assert updated["build_intent"]["notes"] == "Keep the creature toolbox intact."
            assert updated["intent_profile"]["confirmed"]
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
