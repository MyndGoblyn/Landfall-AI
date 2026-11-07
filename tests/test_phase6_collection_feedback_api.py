import asyncio
import importlib
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def _card(name, oracle_id, *, type_line="Artifact", colors=None):
    return {
        "id": f"printing-{oracle_id}",
        "oracle_id": oracle_id,
        "name": name,
        "type_line": type_line,
        "oracle_text": "Deterministic Phase 6 fixture.",
        "cmc": 1,
        "color_identity": colors or [],
        "legalities": {"commander": "legal"},
        "image_uris": {"normal": f"https://cards.example/{oracle_id}.jpg"},
    }


def _with_server(run):
    async def wrapped():
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
            os.environ["RESET_ACCOUNTS_KEY"] = "phase6-test-key"
            os.environ["CANDIDATE_CATALOG_ENABLED"] = "false"
            sys.modules.pop("server", None)
            server = importlib.import_module("server")
            await run(server)
        finally:
            sys.modules.pop("server", None)
            if previous_server is not None:
                sys.modules["server"] = previous_server
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    asyncio.run(wrapped())


def test_collection_import_is_canonical_user_scoped_and_builder_ready():
    async def run(server):
        cards = {
            "sol ring": _card("Sol Ring", "oracle-sol-ring"),
            "forest": _card(
                "Forest",
                "oracle-forest",
                type_line="Basic Land — Forest",
                colors=["G"],
            ),
        }

        async def get_card_bulk(names):
            return [cards.get(name.casefold()) for name in names]

        server.scryfall_service.get_card_bulk = get_card_bulk
        user_one = {"id": "collection-user-1"}
        user_two = {"id": "collection-user-2"}

        first = await server.import_card_collection(
            server.CollectionImportRequest(
                mode="merge",
                entries=[
                    server.CollectionImportEntry(card_name="Sol Ring", quantity=1),
                    server.CollectionImportEntry(card_name="Forest", quantity=12),
                ],
            ),
            current_user=user_one,
        )
        assert [(card.name, card.quantity) for card in first] == [
            ("Forest", 12),
            ("Sol Ring", 1),
        ]

        # Merge sets the supplied canonical quantity and is safe to retry.
        await server.import_card_collection(
            server.CollectionImportRequest(
                mode="merge",
                entries=[server.CollectionImportEntry(card_name="Sol Ring", quantity=2)],
            ),
            current_user=user_one,
        )
        summary = await server.get_card_collection_summary(current_user=user_one)
        assert summary["unique_cards"] == 2
        assert summary["total_copies"] == 14
        assert summary["builder_behavior"]["ranking_training"] is False

        await server.import_card_collection(
            server.CollectionImportRequest(
                mode="merge",
                entries=[server.CollectionImportEntry(card_name="Forest", quantity=3)],
            ),
            current_user=user_two,
        )
        replaced = await server.import_card_collection(
            server.CollectionImportRequest(
                mode="replace",
                entries=[server.CollectionImportEntry(card_name="Forest", quantity=20)],
            ),
            current_user=user_one,
        )
        assert [(card.name, card.quantity) for card in replaced] == [("Forest", 20)]
        assert (await server.get_card_collection(current_user=user_two))[0].quantity == 3

        normalized = await server.preview_build_intent(
            server.BuildIntent(
                confirmed=True,
                deck_name="Collection build",
                starting_point="commander",
                commander_name="Meren of Clan Nel Toth",
                build_mode="complete_draft",
                collection_mode="owned_only",
                collection_source="saved_collection",
            ),
            current_user=user_one,
        )
        assert normalized["intent"]["owned_card_quantities"] == {}
        assert normalized["mapping"]["collection"]["owned_card_count"] == 1
        assert normalized["mapping"]["collection"]["snapshot_copy_count"] == 20
        assert normalized["mapping"]["construction"]["availability"] == "phase_5_promoted"

        assert "card_collection" in server.RESET_ACCOUNT_COLLECTIONS

    _with_server(run)


def test_feedback_is_private_idempotent_and_never_a_ranking_signal():
    async def run(server):
        user_one = {"id": "feedback-user-1"}
        user_two = {"id": "feedback-user-2"}
        deck = await server.create_deck(
            server.DeckCreate(name="Feedback deck"),
            current_user=user_one,
        )
        analysis_id = "analysis-phase6"
        await server.db.analysis_runs.insert_one({
            "id": analysis_id,
            "deck_id": deck.id,
            "user_id": user_one["id"],
            "analysis_depth": "deep",
            "created_at": "2026-11-07T00:00:00+00:00",
            "recommendation_planner": {"portfolio_version": "evidence-portfolio-v3"},
            "suggestions_add": [{
                "card_name": "Victimize",
                "role_tag": "recursion",
                "reason": "Supports the reviewed recursion plan.",
                "score": 91,
                "confidence": 0.82,
            }],
            "suggestions_cut": [],
            "swap_pairs": [],
        })

        accepted = await server.record_recommendation_feedback(
            deck.id,
            server.RecommendationFeedbackCreate(
                analysis_id=analysis_id,
                action="accept_add",
                card_name="Victimize",
                reason_code="fit",
            ),
            current_user=user_one,
        )
        changed = await server.record_recommendation_feedback(
            deck.id,
            server.RecommendationFeedbackCreate(
                analysis_id=analysis_id,
                action="reject_add",
                card_name="Victimize",
                reason_code="strategy",
            ),
            current_user=user_one,
        )
        assert changed.id == accepted.id
        history = await server.get_deck_feedback(deck.id, current_user=user_one)
        assert len(history) == 1
        assert history[0].action == "reject_add"
        assert history[0].provenance["feedback_policy"]["production_ranking_influence"] is False
        assert history[0].provenance["suggestion"]["score"] == 91

        try:
            await server.get_deck_feedback(deck.id, current_user=user_two)
            raise AssertionError("Expected user-scoped feedback history")
        except server.HTTPException as exc:
            assert exc.status_code == 404

        policy = await server.get_feedback_policy(current_user=user_one)
        assert policy["automatic_learning"] is False
        assert policy["aggregation"]["enabled"] is False
        assert "recommendation_feedback" in server.RESET_ACCOUNT_COLLECTIONS

        deleted = await server.delete_feedback_history(current_user=user_one)
        assert deleted["deleted"] == 1
        assert await server.db.recommendation_feedback.count_documents({}) == 0

    _with_server(run)
