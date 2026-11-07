"""Decision-safe execution helpers for reviewed recommendation actions.

The ranking engine owns which cards are suggested.  This module only verifies
that an action still refers to that frozen analysis, applies the smallest deck
mutation, and produces deterministic fingerprints for stale-write protection.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Dict, List, Mapping, Optional, Tuple


ACTION_WORKFLOW_VERSION = "recommendation-actions-v1"
EXPECTED_MAINBOARD_CARDS = 99


class RecommendationActionError(ValueError):
    """A recommendation action failed a deterministic safety gate."""


def _name(value) -> str:
    return " ".join(str(value or "").split())


def _key(value) -> str:
    return _name(value).casefold()


def _quantity(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def deck_source_fingerprint(deck: Mapping) -> str:
    """Fingerprint only state that can change recommendation applicability."""
    cards = sorted(
        (
            _key(card.get("name")),
            _quantity(card.get("qty", 1)),
        )
        for card in deck.get("cards") or []
        if isinstance(card, Mapping) and _key(card.get("name"))
    )
    commanders = sorted(
        _key(value)
        for value in (
            deck.get("commanders")
            or ([deck.get("commander")] if deck.get("commander") else [])
        )
        if _key(value)
    )
    source = {
        "cards": cards,
        "commanders": commanders,
        "color_identity": sorted(deck.get("color_identity") or []),
        "intent_profile": deck.get("intent_profile") or {},
        "build_intent": deck.get("build_intent") or {},
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str).encode()
    ).hexdigest()


def _find_suggestion(items, card_name: str) -> Optional[Dict]:
    wanted = _key(card_name)
    return next(
        (
            dict(item)
            for item in items or []
            if isinstance(item, Mapping) and _key(item.get("card_name")) == wanted
        ),
        None,
    )


def recommendation_reference(
    analysis: Mapping,
    action: str,
    *,
    add_card_name: Optional[str] = None,
    cut_card_name: Optional[str] = None,
) -> Dict:
    """Return the frozen recommendation evidence or reject the action."""
    if action == "add":
        add = _find_suggestion(analysis.get("suggestions_add"), add_card_name or "")
        if not add:
            raise RecommendationActionError(
                "The requested addition is not part of this analysis."
            )
        return {"add": add, "cut": None, "reason": add.get("reason")}

    if action == "cut":
        cut = _find_suggestion(analysis.get("suggestions_cut"), cut_card_name or "")
        if not cut:
            raise RecommendationActionError(
                "The requested cut is not part of this analysis."
            )
        return {"add": None, "cut": cut, "reason": cut.get("reason")}

    if action != "swap":
        raise RecommendationActionError("Unsupported recommendation action.")

    add_key = _key(add_card_name)
    cut_key = _key(cut_card_name)
    pair = next(
        (
            pair
            for pair in analysis.get("swap_pairs") or []
            if isinstance(pair, Mapping)
            and _key((pair.get("add") or {}).get("card_name")) == add_key
            and _key((pair.get("cut") or {}).get("card_name")) == cut_key
        ),
        None,
    )
    if not pair or not pair.get("add") or not pair.get("cut"):
        raise RecommendationActionError(
            "The requested swap is not a complete add-and-cut pair from this analysis."
        )
    return {
        "add": dict(pair["add"]),
        "cut": dict(pair["cut"]),
        "reason": pair.get("reason"),
    }


def canonical_deck_card(card: Mapping) -> Dict:
    """Map a verified Scryfall card to the persisted deck-card contract."""
    faces = card.get("card_faces") or []
    oracle_text = card.get("oracle_text")
    if not oracle_text and faces:
        oracle_text = " // ".join(
            _name(face.get("oracle_text"))
            for face in faces
            if _name(face.get("oracle_text"))
        )
    type_line = card.get("type_line")
    if not type_line and faces:
        type_line = " // ".join(
            _name(face.get("type_line"))
            for face in faces
            if _name(face.get("type_line"))
        )
    return {
        "name": _name(card.get("name")),
        "qty": 1,
        "set_code": card.get("set"),
        "collector_number": card.get("collector_number"),
        "type_line": type_line,
        "oracle_text": oracle_text,
        "cmc": card.get("cmc"),
        "colors": list(card.get("colors") or []),
        "color_identity": list(card.get("color_identity") or []),
        "tags": [],
    }


def _validate_added_card(deck: Mapping, card: Mapping, requested_name: str):
    canonical_name = _name(card.get("name"))
    if not canonical_name or _key(canonical_name) != _key(requested_name):
        raise RecommendationActionError(
            "The recommended card could not be resolved exactly. Run a fresh analysis."
        )
    if (card.get("legalities") or {}).get("commander") != "legal":
        raise RecommendationActionError(
            f"{canonical_name} is not currently legal in Commander."
        )
    deck_identity = set(deck.get("color_identity") or [])
    card_identity = set(card.get("color_identity") or [])
    if not card_identity.issubset(deck_identity):
        raise RecommendationActionError(
            f"{canonical_name} is outside this deck's color identity."
        )
    commander_keys = {
        _key(value)
        for value in (
            deck.get("commanders")
            or ([deck.get("commander")] if deck.get("commander") else [])
        )
    }
    if _key(canonical_name) in commander_keys:
        raise RecommendationActionError("A commander cannot be added to the main deck.")


def apply_recommendation_action(
    deck: Mapping,
    action: str,
    reference: Mapping,
    *,
    resolved_add_card: Optional[Mapping] = None,
) -> Tuple[List[Dict], Dict]:
    """Apply one verified action without re-ranking or filling other slots."""
    cards = [deepcopy(dict(card)) for card in deck.get("cards") or []]
    before_total = sum(_quantity(card.get("qty", 1)) for card in cards)
    add_name = _name((reference.get("add") or {}).get("card_name"))
    cut_name = _name((reference.get("cut") or {}).get("card_name"))

    if action in {"cut", "swap"}:
        cut_key = _key(cut_name)
        cut_index = next(
            (index for index, card in enumerate(cards) if _key(card.get("name")) == cut_key),
            None,
        )
        if cut_index is None:
            raise RecommendationActionError(
                f"{cut_name} is no longer present in the deck. Run a fresh analysis."
            )
        quantity = _quantity(cards[cut_index].get("qty", 1))
        if quantity > 1:
            cards[cut_index]["qty"] = quantity - 1
        else:
            cards.pop(cut_index)

    if action in {"add", "swap"}:
        if not resolved_add_card:
            raise RecommendationActionError("The recommended addition could not be verified.")
        _validate_added_card(deck, resolved_add_card, add_name)
        canonical = canonical_deck_card(resolved_add_card)
        add_key = _key(canonical["name"])
        existing_index = next(
            (index for index, card in enumerate(cards) if _key(card.get("name")) == add_key),
            None,
        )
        is_basic = "basic" in _key(canonical.get("type_line")) and "land" in _key(
            canonical.get("type_line")
        )
        allows_any_number = (
            "a deck can have any number of cards named"
            in _key(canonical.get("oracle_text"))
        )
        if existing_index is not None and not (is_basic or allows_any_number):
            raise RecommendationActionError(
                f"{canonical['name']} is already in the deck; Commander singleton rules block another copy."
            )
        if existing_index is not None:
            cards[existing_index]["qty"] = _quantity(cards[existing_index].get("qty", 1)) + 1
        else:
            cards.append(canonical)

    after_total = sum(_quantity(card.get("qty", 1)) for card in cards)
    if after_total > EXPECTED_MAINBOARD_CARDS:
        raise RecommendationActionError(
            "This addition would exceed the 99-card Commander main deck. Apply a reviewed swap or cut first."
        )

    return cards, {
        "action": action,
        "added": [{"name": add_name, "qty": 1}] if add_name else [],
        "removed": [{"name": cut_name, "qty": 1}] if cut_name else [],
        "mainboard_before": before_total,
        "mainboard_after": after_total,
        "reason": reference.get("reason"),
    }
