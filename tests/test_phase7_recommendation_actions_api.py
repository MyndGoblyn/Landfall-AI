import asyncio
import importlib
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def _with_server(run):
    async def wrapped():
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


def _deck_card(name, qty=1, *, type_line="Creature"):
    return {
        "name": name,
        "qty": qty,
        "type_line": type_line,
        "oracle_text": "Phase 7 fixture.",
        "cmc": 2,
        "colors": ["G"],
        "color_identity": ["G"],
        "tags": [],
    }


def _scryfall_card(name="Upgrade Card", *, identity=None, legal="legal"):
    return {
        "id": "printing-upgrade",
        "oracle_id": "oracle-upgrade",
        "name": name,
        "type_line": "Creature — Elf",
        "oracle_text": "A verified deterministic upgrade.",
        "cmc": 2,
        "colors": identity or ["G"],
        "color_identity": identity or ["G"],
        "set": "tst",
        "collector_number": "7",
        "legalities": {"commander": legal},
    }


def test_recommendation_swap_creates_private_revision_and_restores_safely():
    async def run(server):
        user = {"id": "phase7-user"}
        other = {"id": "phase7-other"}
        deck = await server.create_deck(
            server.DeckCreate(
                name="Reviewed deck",
                commander="Meren of Clan Nel Toth",
                commanders=["Meren of Clan Nel Toth"],
            ),
            current_user=user,
        )
        original_cards = [
            _deck_card("Cut Card"),
            _deck_card("Forest", 98, type_line="Basic Land — Forest"),
        ]
        await server.db.decks.update_one(
            {"id": deck.id, "user_id": user["id"]},
            {"$set": {
                "cards": original_cards,
                "color_identity": ["B", "G"],
            }},
        )
        stored_deck = await server.db.decks.find_one(
            {"id": deck.id, "user_id": user["id"]}, {"_id": 0}
        )
        analysis_id = "phase7-analysis"
        add = {
            "card_name": "Upgrade Card",
            "role_tag": "engine",
            "reason": "Repairs the measured engine gap.",
            "score": 94,
            "confidence": 0.88,
        }
        cut = {
            "card_name": "Cut Card",
            "role_tag": "flex",
            "reason": "Lowest-impact flexible slot.",
            "score": 45,
            "confidence": 0.81,
        }
        await server.db.analysis_runs.insert_one({
            "id": analysis_id,
            "deck_id": deck.id,
            "user_id": user["id"],
            "deck_source_fingerprint": server.deck_source_fingerprint(stored_deck),
            "suggestions_add": [add],
            "suggestions_cut": [cut],
            "swap_pairs": [{
                "add": add,
                "cut": cut,
                "reason": "Raise engine density without changing deck size.",
            }],
            "recommendation_planner": {"portfolio_version": "evidence-portfolio-v3"},
        })

        async def search_card(name, fuzzy=True):
            assert name == "Upgrade Card"
            assert fuzzy is False
            return _scryfall_card()

        server.scryfall_service.search_card = search_card
        applied = await server.apply_analysis_recommendation(
            deck.id,
            server.RecommendationActionApplyRequest(
                analysis_id=analysis_id,
                action="swap",
                add_card_name="Upgrade Card",
                cut_card_name="Cut Card",
                confirmed=True,
            ),
            current_user=user,
        )
        names = {card.name: card.qty for card in applied["deck"].cards}
        assert names == {"Forest": 98, "Upgrade Card": 1}
        assert applied["deck"].deck_revision == 1
        assert applied["revision"].change_summary["mainboard_before"] == 99
        assert applied["revision"].change_summary["mainboard_after"] == 99
        assert applied["revision"].recommendation_snapshot["planner"] == {
            "portfolio_version": "evidence-portfolio-v3"
        }

        feedback = await server.get_deck_feedback(deck.id, current_user=user)
        assert len(feedback) == 1
        assert feedback[0].action == "accept_swap"
        assert feedback[0].provenance["feedback_policy"]["production_ranking_influence"] is False

        try:
            await server.apply_analysis_recommendation(
                deck.id,
                server.RecommendationActionApplyRequest(
                    analysis_id=analysis_id,
                    action="swap",
                    add_card_name="Upgrade Card",
                    cut_card_name="Cut Card",
                    confirmed=True,
                ),
                current_user=user,
            )
            raise AssertionError("Expected stale-analysis guard")
        except server.HTTPException as exc:
            assert exc.status_code == 409
            assert "fresh analysis" in str(exc.detail)

        restored = await server.restore_deck_revision(
            deck.id,
            applied["revision"].id,
            server.DeckRevisionRestoreRequest(snapshot="before", confirmed=True),
            current_user=user,
        )
        restored_names = {card.name: card.qty for card in restored["deck"].cards}
        assert restored_names == {"Cut Card": 1, "Forest": 98}
        assert restored["deck"].deck_revision == 2
        assert restored["revision"].restored_from_revision_id == applied["revision"].id
        revisions = await server.get_deck_revisions(deck.id, current_user=user)
        assert [revision.revision for revision in revisions] == [2, 1]

        try:
            await server.get_deck_revisions(deck.id, current_user=other)
            raise AssertionError("Expected revision user isolation")
        except server.HTTPException as exc:
            assert exc.status_code == 404

        assert "deck_revisions" in server.RESET_ACCOUNT_COLLECTIONS
        await server.delete_deck(deck.id, current_user=user)
        assert await server.db.deck_revisions.count_documents({}) == 0

    _with_server(run)


def test_recommendation_actions_block_old_analysis_overflow_and_illegal_cards():
    async def run(server):
        user = {"id": "phase7-gates"}
        deck = await server.create_deck(
            server.DeckCreate(
                name="Gate deck",
                commander="Meren of Clan Nel Toth",
                commanders=["Meren of Clan Nel Toth"],
            ),
            current_user=user,
        )
        cards = [_deck_card("Forest", 99, type_line="Basic Land — Forest")]
        await server.db.decks.update_one(
            {"id": deck.id, "user_id": user["id"]},
            {"$set": {"cards": cards, "color_identity": ["B", "G"]}},
        )
        current = await server.db.decks.find_one(
            {"id": deck.id, "user_id": user["id"]}, {"_id": 0}
        )
        add = {
            "card_name": "Upgrade Card",
            "role_tag": "engine",
            "reason": "Reviewed addition.",
        }
        await server.db.analysis_runs.insert_one({
            "id": "old-analysis",
            "deck_id": deck.id,
            "user_id": user["id"],
            "suggestions_add": [add],
            "suggestions_cut": [],
            "swap_pairs": [],
        })
        await server.db.analysis_runs.insert_one({
            "id": "current-analysis",
            "deck_id": deck.id,
            "user_id": user["id"],
            "deck_source_fingerprint": server.deck_source_fingerprint(current),
            "suggestions_add": [add],
            "suggestions_cut": [],
            "swap_pairs": [],
        })

        async def legal_card(name, fuzzy=True):
            return _scryfall_card()

        server.scryfall_service.search_card = legal_card
        for analysis_id, expected in (
            ("old-analysis", "predates"),
            ("current-analysis", "99-card"),
        ):
            try:
                await server.apply_analysis_recommendation(
                    deck.id,
                    server.RecommendationActionApplyRequest(
                        analysis_id=analysis_id,
                        action="add",
                        add_card_name="Upgrade Card",
                        confirmed=True,
                    ),
                    current_user=user,
                )
                raise AssertionError("Expected recommendation action gate")
            except server.HTTPException as exc:
                assert exc.status_code == 409
                assert expected in str(exc.detail)

        # Open one slot, refresh the fingerprint, and verify color identity again.
        await server.db.decks.update_one(
            {"id": deck.id, "user_id": user["id"]},
            {"$set": {"cards": [_deck_card("Forest", 98, type_line="Basic Land — Forest")]}},
        )
        open_deck = await server.db.decks.find_one(
            {"id": deck.id, "user_id": user["id"]}, {"_id": 0}
        )
        await server.db.analysis_runs.update_one(
            {"id": "current-analysis"},
            {"$set": {"deck_source_fingerprint": server.deck_source_fingerprint(open_deck)}},
        )

        async def illegal_identity(name, fuzzy=True):
            return _scryfall_card(identity=["U"])

        server.scryfall_service.search_card = illegal_identity
        try:
            await server.apply_analysis_recommendation(
                deck.id,
                server.RecommendationActionApplyRequest(
                    analysis_id="current-analysis",
                    action="add",
                    add_card_name="Upgrade Card",
                    confirmed=True,
                ),
                current_user=user,
            )
            raise AssertionError("Expected color-identity gate")
        except server.HTTPException as exc:
            assert exc.status_code == 409
            assert "color identity" in str(exc.detail)

        assert await server.db.deck_revisions.count_documents({}) == 0

    _with_server(run)


def test_recommendation_action_respects_oracle_any_number_exception():
    from services.recommendation_actions import apply_recommendation_action

    deck = {
        "commander": "Athreos, God of Passage",
        "commanders": ["Athreos, God of Passage"],
        "color_identity": ["B", "W"],
        "cards": [
            _deck_card("Shadowborn Apostle", 2),
            _deck_card("Plains", 95, type_line="Basic Land — Plains"),
        ],
    }
    card = _scryfall_card(name="Shadowborn Apostle", identity=["B"])
    card["oracle_text"] = (
        "A deck can have any number of cards named Shadowborn Apostle."
    )
    after, summary = apply_recommendation_action(
        deck,
        "add",
        {
            "add": {"card_name": "Shadowborn Apostle"},
            "cut": None,
            "reason": "Supports the explicit Apostle package.",
        },
        resolved_add_card=card,
    )

    quantities = {item["name"]: item["qty"] for item in after}
    assert quantities["Shadowborn Apostle"] == 3
    assert summary["mainboard_before"] == 97
    assert summary["mainboard_after"] == 98
