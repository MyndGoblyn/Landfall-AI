import asyncio
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


class FakeConstructor:
    VERSION = "test-constructor-v1"

    def __init__(self):
        self.calls = 0

    def source_fingerprint(self, deck, normalized):
        source = {
            "cards": [
                [card.get("name"), card.get("qty", 1)]
                for card in deck.get("cards") or []
            ],
            "intent": normalized["intent"],
        }
        return hashlib.sha256(
            json.dumps(source, sort_keys=True).encode()
        ).hexdigest()

    async def construct(self, deck, normalized):
        self.calls += 1
        name = "Viscera Seer" if self.calls == 1 else "Victimize"
        deck_card = {
            "name": name,
            "qty": 1,
            "type_line": "Creature" if name == "Viscera Seer" else "Sorcery",
            "oracle_text": "Deterministic test card.",
            "cmc": 1 if name == "Viscera Seer" else 3,
            "colors": ["B"],
            "color_identity": ["B"],
            "tags": [],
        }
        return {
            "constructor_version": self.VERSION,
            "status": "ready_partial",
            "source_fingerprint": self.source_fingerprint(deck, normalized),
            "scope": {"remaining_mainboard_slots": 98},
            "commander": {
                "names": ["Meren of Clan Nel Toth"],
                "color_identity": ["B", "G"],
            },
            "fixed_cards": [],
            "selected_cards": [{"name": name, "qty": 1}],
            "proposed_main_deck": [deck_card],
            "validation": {
                "passed": True,
                "errors": [],
                "warnings": [],
                "checks": {"legality": True},
            },
        }


def test_build_draft_revisions_apply_and_stale_guard():
    async def run():
        env_keys = [
            "USE_IN_MEMORY_DB",
            "CAPTCHA_REQUIRED",
            "REQUIRE_EMAIL_VERIFICATION",
            "CANDIDATE_CATALOG_ENABLED",
            "BUILD_CONSTRUCTOR_MODE",
        ]
        previous_env = {key: os.environ.get(key) for key in env_keys}
        previous_server = sys.modules.get("server")
        try:
            os.environ["USE_IN_MEMORY_DB"] = "true"
            os.environ["CAPTCHA_REQUIRED"] = "false"
            os.environ["REQUIRE_EMAIL_VERIFICATION"] = "false"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            os.environ["BUILD_CONSTRUCTOR_MODE"] = "scaffold"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")
            server.deck_constructor = FakeConstructor()
            user = {"id": "constructor-user"}
            deck = await server.create_deck(
                server.DeckCreate(
                    name="Meren scaffold",
                    commander="Meren of Clan Nel Toth",
                    commanders=["Meren of Clan Nel Toth"],
                    build_intent=server.BuildIntent(
                        confirmed=True,
                        deck_name="Meren scaffold",
                        starting_point="commander",
                        commander_name="Meren of Clan Nel Toth",
                        build_mode="guided_scaffold",
                        playstyle="value",
                        target_bracket=3,
                        build_shape="core_shell",
                    ),
                ),
                current_user=user,
            )

            first = await server.create_build_draft(deck.id, current_user=user)
            second = await server.create_build_draft(deck.id, current_user=user)

            assert first.revision == 1
            assert second.revision == 2
            assert second.change_summary["added"] == [{"name": "Victimize", "qty": 1}]
            assert second.change_summary["removed"] == [{"name": "Viscera Seer", "qty": 1}]
            drafts = await server.get_build_drafts(deck.id, current_user=user)
            assert [draft.revision for draft in drafts] == [2, 1]

            updated = await server.apply_build_draft(
                deck.id,
                second.id,
                server.BuildDraftApplyRequest(confirmed=True),
                current_user=user,
            )
            assert [card["name"] for card in updated["cards"]] == ["Victimize"]
            assert updated["last_build_draft_id"] == second.id
            assert updated["build_draft_revision"] == 2

            try:
                await server.apply_build_draft(
                    deck.id,
                    second.id,
                    server.BuildDraftApplyRequest(confirmed=True),
                    current_user=user,
                )
                raise AssertionError("Expected stale scaffold rejection")
            except server.HTTPException as exc:
                assert exc.status_code == 409
                assert "regenerate" in str(exc.detail)

            assert "build_drafts" in server.RESET_ACCOUNT_COLLECTIONS
            await server.delete_deck(deck.id, current_user=user)
            assert await server.db.build_drafts.count_documents({}) == 0
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
