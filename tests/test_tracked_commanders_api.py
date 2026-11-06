import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def _commander_card():
    return {
        "id": "printing-1",
        "oracle_id": "0310dfdb-0498-488d-9f1a-279f8239e024",
        "name": "Meren of Clan Nel Toth",
        "type_line": "Legendary Creature — Human Shaman",
        "oracle_text": "Whenever another creature you control dies, you get an experience counter.",
        "cmc": 4,
        "color_identity": ["B", "G"],
        "legalities": {"commander": "legal"},
        "image_uris": {"normal": "https://cards.example/meren.jpg"},
    }


def test_tracked_commander_crud_is_idempotent_and_user_scoped():
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
            os.environ["RESET_ACCOUNTS_KEY"] = "tracked-test-key"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")

            async def search_card(_name):
                return _commander_card()

            server.scryfall_service.search_card = search_card
            user_one = {"id": "user-1"}
            user_two = {"id": "user-2"}
            request = server.TrackCommanderCreate(
                commander_name="  Meren of Clan Nel Toth  ",
                source="discover",
            )

            created = await server.track_commander(request, current_user=user_one)
            duplicate = await server.track_commander(request, current_user=user_one)

            assert created.commander_oracle_id == _commander_card()["oracle_id"]
            assert created.name == "Meren of Clan Nel Toth"
            assert duplicate.id == created.id
            assert await server.db.tracked_commanders.count_documents(
                {"user_id": "user-1"}
            ) == 1

            tracked = await server.get_tracked_commanders(current_user=user_one)
            assert [item.name for item in tracked] == ["Meren of Clan Nel Toth"]
            assert await server.get_tracked_commander(
                created.commander_oracle_id,
                current_user=user_one,
            ) == duplicate

            updated = await server.update_tracked_commander_note(
                created.commander_oracle_id,
                server.TrackCommanderNoteUpdate(note="  Budget recursion shell  "),
                current_user=user_one,
            )
            assert updated.note == "Budget recursion shell"

            with pytest.raises(HTTPException) as exc_info:
                await server.get_tracked_commander(
                    created.commander_oracle_id,
                    current_user=user_two,
                )
            assert exc_info.value.status_code == 404

            await server.untrack_commander(
                created.commander_oracle_id,
                current_user=user_one,
            )
            assert await server.get_tracked_commanders(current_user=user_one) == []
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


def test_account_reset_includes_tracked_commanders():
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
            os.environ["RESET_ACCOUNTS_KEY"] = "tracked-test-key"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")
            await server.db.tracked_commanders.insert_one({
                "id": "tracked-1",
                "user_id": "user-1",
            })

            result = await server.reset_accounts(x_reset_key="tracked-test-key")

            assert result.deleted["tracked_commanders"] == 1
            assert await server.db.tracked_commanders.count_documents({}) == 0
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
