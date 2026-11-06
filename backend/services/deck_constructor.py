"""Deterministic, evidence-bounded Commander scaffold construction.

Phase 4 deliberately reuses the served recommendation engine rather than
creating a second card-ranking stack.  The constructor fixes user-owned cards,
adds protected intent, selects only Planner V3 recommendations that survive
hard gates, and fills a conservative basic-land baseline.  Any remaining work
is returned as an unresolved slot instead of lowering an evidence threshold.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from services.build_intent import normalize_build_intent


BASIC_LANDS = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
    "C": "Wastes",
}
INVALID_MAIN_DECK_TYPES = {
    "conspiracy",
    "dungeon",
    "emblem",
    "phenomenon",
    "plane",
    "scheme",
    "token",
    "vanguard",
}


class ConstructorUnavailable(ValueError):
    """The requested construction mode is intentionally not promoted."""


def _quantity(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _name(value: Any) -> str:
    return " ".join(str(value or "").split())


def _price(card: Mapping) -> Optional[float]:
    prices = card.get("prices") or {}
    value = prices.get("usd") if isinstance(prices, Mapping) else None
    try:
        return round(float(value), 2) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def _images(card: Mapping) -> Dict[str, Optional[str]]:
    direct = card.get("image_uris") or {}
    faces = card.get("card_faces") or []
    front = direct.get("normal") if isinstance(direct, Mapping) else None
    back = None
    if not front and faces:
        front = (faces[0].get("image_uris") or {}).get("normal")
    if len(faces) > 1:
        back = (faces[1].get("image_uris") or {}).get("normal")
    return {"front": front, "back": back}


def _deck_card(card: Mapping, qty: int = 1) -> Dict:
    return {
        "name": card.get("name"),
        "qty": qty,
        "set_code": card.get("set"),
        "collector_number": card.get("collector_number"),
        "type_line": card.get("type_line"),
        "oracle_text": card.get("oracle_text") or "",
        "cmc": card.get("cmc") or 0,
        "colors": card.get("colors") or [],
        "color_identity": card.get("color_identity") or [],
        "tags": [],
    }


def _allows_multiple(card: Mapping) -> bool:
    type_line = str(card.get("type_line") or "").casefold()
    oracle_text = str(card.get("oracle_text") or "").casefold()
    return (
        "basic land" in type_line
        or "a deck can have any number of cards named" in oracle_text
        or "a deck can have up to" in oracle_text
    )


def _is_land(card: Mapping) -> bool:
    return "land" in str(card.get("type_line") or "").casefold()


def _main_deck_eligible(card: Mapping) -> bool:
    type_line = str(card.get("type_line") or "").casefold()
    return not any(card_type in type_line for card_type in INVALID_MAIN_DECK_TYPES)


def _commander_eligible(card: Mapping) -> bool:
    type_line = str(card.get("type_line") or "").casefold()
    oracle_text = str(card.get("oracle_text") or "").casefold()
    legal = (card.get("legalities") or {}).get("commander") in {"legal", "restricted"}
    return legal and (
        ("legendary" in type_line and "creature" in type_line)
        or "can be your commander" in oracle_text
        or ("background" in type_line and "legendary enchantment" in type_line)
    )


def _compatible_commanders(cards: Sequence[Mapping]) -> bool:
    if len(cards) <= 1:
        return True
    if len(cards) != 2:
        return False
    first, second = cards
    first_text = str(first.get("oracle_text") or "").casefold()
    second_text = str(second.get("oracle_text") or "").casefold()
    first_type = str(first.get("type_line") or "").casefold()
    second_type = str(second.get("type_line") or "").casefold()
    if "background" in first_type and "choose a background" in second_text:
        return True
    if "background" in second_type and "choose a background" in first_text:
        return True
    if "doctor's companion" in first_text and "doctor" in second_type:
        return True
    if "doctor's companion" in second_text and "doctor" in first_type:
        return True
    generic_partner = re.compile(r"\bpartner\b(?!\s+with)")
    if (
        generic_partner.search(first_text)
        and generic_partner.search(second_text)
    ) or ("friends forever" in first_text and "friends forever" in second_text):
        return True
    partner_with = re.compile(r"partner with ([^\n(]+)")
    first_partner = partner_with.search(first_text)
    second_partner = partner_with.search(second_text)
    return bool(
        first_partner
        and first_partner.group(1).strip() in str(second.get("name") or "").casefold()
    ) or bool(
        second_partner
        and second_partner.group(1).strip() in str(first.get("name") or "").casefold()
    )


def _issue(code: str, message: str, *, card_name: Optional[str] = None) -> Dict:
    result = {"code": code, "message": message}
    if card_name:
        result["card_name"] = card_name
    return result


def _largest_remainder(weights: Mapping[str, float], total: int) -> Dict[str, int]:
    if total <= 0 or not weights:
        return {}
    normalized = {key: max(0.0, float(value)) for key, value in weights.items()}
    weight_total = sum(normalized.values())
    if weight_total <= 0:
        normalized = {key: 1.0 for key in normalized}
        weight_total = float(len(normalized))
    exact = {key: total * weight / weight_total for key, weight in normalized.items()}
    result = {key: int(math.floor(value)) for key, value in exact.items()}
    remaining = total - sum(result.values())
    order = sorted(
        normalized,
        key=lambda key: (-(exact[key] - result[key]), key),
    )
    for key in order[:remaining]:
        result[key] += 1
    return {key: count for key, count in result.items() if count > 0}


class DeckConstructor:
    VERSION = "deterministic-scaffold-v1"

    def __init__(
        self,
        suggestion_engine,
        scryfall_service,
        *,
        mode: str = "scaffold",
        max_scaffold_slots: int = 40,
    ):
        if mode not in {"disabled", "shadow", "scaffold", "complete"}:
            mode = "disabled"
        self.engine = suggestion_engine
        self.scryfall = scryfall_service
        self.mode = mode
        self.max_scaffold_slots = max(1, min(99, int(max_scaffold_slots)))

    def get_status(self) -> Dict:
        return {
            "version": self.VERSION,
            "mode": self.mode,
            "max_scaffold_slots": self.max_scaffold_slots,
            "complete_drafts_enabled": self.mode == "complete",
        }

    def source_fingerprint(self, deck: Mapping, normalized_build: Mapping) -> str:
        cards = sorted(
            (
                _name(card.get("name")).casefold(),
                _quantity(card.get("qty", 1)),
            )
            for card in deck.get("cards") or []
            if _name(card.get("name"))
        )
        source = {
            "intent": normalized_build.get("intent") or normalized_build,
            "commander": _name(deck.get("commander")),
            "commanders": [_name(value) for value in deck.get("commanders") or []],
            "cards": cards,
        }
        encoded = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def _resolve(self, names: Iterable[str]) -> Dict[str, Optional[Dict]]:
        ordered = list(dict.fromkeys(_name(value) for value in names if _name(value)))
        if not ordered:
            return {}
        cards = await self.scryfall.get_card_bulk(ordered)
        return {
            submitted.casefold(): card
            for submitted, card in zip(ordered, cards)
        }

    @staticmethod
    def _protected_sources(intent: Mapping) -> Dict[str, Dict]:
        protected: Dict[str, Dict] = {}
        for card_name in intent.get("protected_cards") or []:
            cleaned = _name(card_name)
            if cleaned:
                protected.setdefault(cleaned.casefold(), {
                    "name": cleaned,
                    "sources": [],
                })["sources"].append("protected card")
        for package in intent.get("protected_packages") or []:
            package_name = _name(package.get("name")) or "protected package"
            for card_name in package.get("cards") or []:
                cleaned = _name(card_name)
                if cleaned:
                    protected.setdefault(cleaned.casefold(), {
                        "name": cleaned,
                        "sources": [],
                    })["sources"].append(package_name)
        return protected

    @staticmethod
    def _card_legality_errors(card: Mapping, color_identity: Sequence[str]) -> List[str]:
        problems = []
        if (card.get("legalities") or {}).get("commander") not in {"legal", "restricted"}:
            problems.append("is not Commander legal")
        if not _main_deck_eligible(card):
            problems.append("is not a Commander main-deck card")
        allowed = set(color_identity or [])
        actual = set(card.get("color_identity") or [])
        if not actual.issubset(allowed):
            problems.append("falls outside the commander's color identity")
        return problems

    @staticmethod
    def _allocation(lanes: Sequence[Mapping], slots: int) -> List[Dict]:
        active = [
            lane for lane in lanes
            if lane.get("id") and lane.get("status") != "established"
        ][:8]
        if not active or slots <= 0:
            return []
        counts = _largest_remainder(
            {str(lane["id"]): max(1.0, float(lane.get("priority") or 1)) for lane in active},
            slots,
        )
        return [
            {
                "lane": lane["id"],
                "kind": lane.get("kind") or "role",
                "slots": counts.get(str(lane["id"]), 0),
                "priority": lane.get("priority"),
                "evidence": lane.get("evidence") or [],
            }
            for lane in active
            if counts.get(str(lane["id"]), 0)
        ]

    @staticmethod
    def _mana_target(
        commander_cards: Sequence[Mapping],
        main_cards: Sequence[Mapping],
        intent: Mapping,
    ) -> int:
        nonlands = [card for card in main_cards if not _is_land(card)]
        average_cmc = (
            sum(float(card.get("cmc") or 0) for card in nonlands) / len(nonlands)
            if nonlands else 3.0
        )
        commander_cmc = max(
            [float(card.get("cmc") or 0) for card in commander_cards] or [0]
        )
        target = 36
        if average_cmc >= 4:
            target += 2
        if commander_cmc >= 6:
            target += 1
        priorities = set(intent.get("custom_strategy_priorities") or [])
        if "landfall" in priorities:
            target += 2
        if int(intent.get("target_bracket") or 3) >= 4:
            target -= 1
        return max(32, min(40, target))

    @staticmethod
    def _mana_demand(cards: Sequence[Mapping], color_identity: Sequence[str]) -> Dict[str, float]:
        demand = Counter({color: 0.0 for color in color_identity if color in "WUBRG"})
        for card in cards:
            mana_cost = str(card.get("mana_cost") or "")
            qty = max(1, _quantity(card.get("qty", 1)))
            for color in re.findall(r"\{([WUBRG])\}", mana_cost):
                if color in demand:
                    demand[color] += qty
        if not demand:
            return {"C": 1.0}
        if sum(demand.values()) <= 0:
            return {color: 1.0 for color in demand}
        return dict(demand)

    @staticmethod
    def _record(
        card: Mapping,
        *,
        qty: int,
        source: str,
        reason: str,
        role: Optional[str] = None,
        evidence: Optional[Sequence[str]] = None,
        confidence: Optional[float] = None,
    ) -> Dict:
        image = _images(card)
        return {
            "name": card.get("name"),
            "qty": qty,
            "source": source,
            "role": role,
            "reason": reason,
            "evidence": list(evidence or []),
            "confidence": confidence,
            "price_usd": _price(card),
            "type_line": card.get("type_line"),
            "cmc": card.get("cmc") or 0,
            "image_url": image["front"],
            "image_url_back": image["back"],
            "deck_card": _deck_card(card, qty),
        }

    async def construct(self, deck: Mapping, build_value: Mapping) -> Dict:
        normalized = (
            build_value
            if build_value.get("intent") and build_value.get("mapping")
            else normalize_build_intent(build_value)
        )
        intent = normalized["intent"]
        if not intent.get("confirmed"):
            raise ConstructorUnavailable("Confirm the build intent before construction")
        if self.mode in {"disabled", "shadow"}:
            raise ConstructorUnavailable("Deterministic scaffolds are not enabled")
        if intent.get("build_mode") == "manual":
            raise ConstructorUnavailable("This build is configured for manual construction")
        if intent.get("build_mode") == "complete_draft" and self.mode != "complete":
            raise ConstructorUnavailable(
                "Complete drafts remain disabled until Phase 5 portfolio validation"
            )

        errors: List[Dict] = []
        warnings: List[Dict] = []
        rejected: List[Dict] = []
        commanders = [
            _name(value)
            for value in (
                intent.get("commander_name") or deck.get("commander"),
                intent.get("partner_name"),
            )
            if _name(value)
        ]
        commanders = list(dict.fromkeys(commanders))
        if not commanders:
            errors.append(_issue("commander_missing", "Choose a legal commander before building."))

        fixed_cards = [
            dict(card)
            for card in deck.get("cards") or []
            if _name(card.get("name")) and _quantity(card.get("qty", 1))
        ]
        protected = self._protected_sources(intent)
        names_to_resolve = [*commanders]
        names_to_resolve.extend(card["name"] for card in fixed_cards)
        names_to_resolve.extend(value["name"] for value in protected.values())
        resolved = await self._resolve(names_to_resolve)

        commander_cards = []
        for commander_name in commanders:
            card = resolved.get(commander_name.casefold())
            if not card:
                errors.append(_issue(
                    "commander_unresolved",
                    f"{commander_name} could not be resolved in the current catalog.",
                    card_name=commander_name,
                ))
                continue
            if not _commander_eligible(card):
                errors.append(_issue(
                    "commander_illegal",
                    f"{card.get('name')} is not eligible in the Commander zone.",
                    card_name=card.get("name"),
                ))
                continue
            commander_cards.append(card)
        if len(commander_cards) > 1 and not _compatible_commanders(commander_cards):
            errors.append(_issue(
                "commander_pair_incompatible",
                "The selected commanders do not expose a compatible partner/background rule.",
            ))

        color_identity = sorted({
            color
            for card in commander_cards
            for color in card.get("color_identity") or []
        })
        excluded = {
            _name(value).casefold()
            for value in intent.get("excluded_cards") or []
            if _name(value)
        }
        owned = {
            _name(value).casefold()
            for value in intent.get("owned_card_names") or []
            if _name(value)
        }
        if any(name.casefold() in excluded for name in commanders):
            errors.append(_issue(
                "commander_excluded",
                "The selected commander is also excluded by this build intent.",
            ))

        hydrated_fixed: List[Dict] = []
        fixed_records: List[Dict] = []
        fixed_names: Counter = Counter()
        fixed_price = 0.0
        unknown_fixed_prices = []
        max_card_price = intent.get("max_card_price_usd")
        strict_budget = intent.get("budget_mode") == "strict"
        for raw in fixed_cards:
            submitted_name = _name(raw.get("name"))
            qty = _quantity(raw.get("qty", 1))
            card = resolved.get(submitted_name.casefold())
            if not card:
                errors.append(_issue(
                    "fixed_card_unresolved",
                    f"{submitted_name} could not be verified and remains fixed.",
                    card_name=submitted_name,
                ))
                hydrated = {**raw, "name": submitted_name, "qty": qty}
                hydrated_fixed.append(hydrated)
                fixed_records.append({
                    "name": submitted_name,
                    "qty": qty,
                    "source": "fixed",
                    "role": None,
                    "reason": "Already present in the deck; catalog facts were unavailable.",
                    "evidence": ["fixed user input"],
                    "confidence": None,
                    "price_usd": None,
                    "type_line": raw.get("type_line"),
                    "cmc": raw.get("cmc") or 0,
                    "image_url": None,
                    "image_url_back": None,
                    "deck_card": hydrated,
                })
                fixed_names[submitted_name.casefold()] += qty
                unknown_fixed_prices.append(submitted_name)
                continue
            canonical_name = str(card.get("name"))
            fixed_names[canonical_name.casefold()] += qty
            legality = self._card_legality_errors(card, color_identity)
            for problem in legality:
                errors.append(_issue(
                    "fixed_card_illegal",
                    f"{canonical_name} {problem}.",
                    card_name=canonical_name,
                ))
            if canonical_name.casefold() in excluded:
                errors.append(_issue(
                    "fixed_card_excluded",
                    f"{canonical_name} is fixed in the deck but excluded by the build intent.",
                    card_name=canonical_name,
                ))
            card_price = _price(card)
            if card_price is None:
                unknown_fixed_prices.append(canonical_name)
            else:
                fixed_price += card_price * qty
                if strict_budget and max_card_price is not None and card_price > max_card_price:
                    errors.append(_issue(
                        "fixed_card_over_cap",
                        f"{canonical_name} exceeds the strict per-card ceiling.",
                        card_name=canonical_name,
                    ))
            hydrated = {**card, "qty": qty}
            hydrated_fixed.append(hydrated)
            fixed_records.append(self._record(
                card,
                qty=qty,
                source="fixed",
                reason="Already present in the deck and preserved as a fixed input.",
                evidence=["fixed user input"],
            ))

        for key, qty in fixed_names.items():
            representative = next(
                (card for card in hydrated_fixed if str(card.get("name") or "").casefold() == key),
                {},
            )
            if qty > 1 and not _allows_multiple(representative):
                errors.append(_issue(
                    "singleton_violation",
                    f"{representative.get('name') or key} appears {qty} times without a quantity exception.",
                    card_name=representative.get("name") or key,
                ))
        if strict_budget and unknown_fixed_prices:
            errors.append(_issue(
                "strict_budget_unverified",
                "Strict budget verification requires prices for every fixed card.",
            ))

        command_zone_slots = len(commander_cards)
        target_mainboard = max(0, 100 - command_zone_slots)
        fixed_slots = sum(_quantity(card.get("qty", 1)) for card in hydrated_fixed)
        if fixed_slots > target_mainboard:
            errors.append(_issue(
                "mainboard_oversized",
                f"The fixed main deck already has {fixed_slots} cards; the target is {target_mainboard}.",
            ))
        open_slots = max(0, target_mainboard - fixed_slots)
        shape_limit = int(normalized["mapping"]["build_shape"]["maximum_requested_slots"])
        runtime_limit = shape_limit if self.mode == "complete" else self.max_scaffold_slots
        request_limit = min(open_slots, shape_limit, runtime_limit)

        selected_records: List[Dict] = []
        selected_facts: List[Dict] = []
        selected_names = set(fixed_names)
        running_price = fixed_price
        total_budget = intent.get("budget_limit_usd")

        def accept_price(card: Mapping, qty: int, *, protected_card: bool = False) -> bool:
            nonlocal running_price
            card_name = str(card.get("name"))
            card_price = _price(card)
            if strict_budget and card_price is None:
                target = errors if protected_card else rejected
                target.append(_issue(
                    "strict_budget_price_missing",
                    f"{card_name} has no verifiable price for the strict budget.",
                    card_name=card_name,
                ))
                return False
            if strict_budget and max_card_price is not None and card_price is not None and card_price > max_card_price:
                target = errors if protected_card else rejected
                target.append(_issue(
                    "strict_budget_card_cap",
                    f"{card_name} exceeds the strict per-card ceiling.",
                    card_name=card_name,
                ))
                return False
            next_price = running_price + (card_price or 0) * qty
            if strict_budget and total_budget is not None and next_price > total_budget:
                target = errors if protected_card else rejected
                target.append(_issue(
                    "strict_budget_total",
                    f"Adding {card_name} would exceed the strict total budget.",
                    card_name=card_name,
                ))
                return False
            running_price = next_price
            return True

        for key, protected_value in protected.items():
            if key in selected_names or key in {name.casefold() for name in commanders}:
                continue
            if len(selected_records) >= request_limit:
                errors.append(_issue(
                    "protected_card_outside_scope",
                    f"{protected_value['name']} cannot fit inside the requested scaffold scope.",
                    card_name=protected_value["name"],
                ))
                continue
            if intent.get("collection_mode") == "owned_only" and key not in owned:
                errors.append(_issue(
                    "protected_card_not_owned",
                    f"{protected_value['name']} is protected but absent from the owned-only pool.",
                    card_name=protected_value["name"],
                ))
                continue
            card = resolved.get(key)
            if not card:
                errors.append(_issue(
                    "protected_card_unresolved",
                    f"{protected_value['name']} could not be verified.",
                    card_name=protected_value["name"],
                ))
                continue
            legality = self._card_legality_errors(card, color_identity)
            if legality:
                errors.append(_issue(
                    "protected_card_illegal",
                    f"{card.get('name')} {' and '.join(legality)}.",
                    card_name=card.get("name"),
                ))
                continue
            if not accept_price(card, 1, protected_card=True):
                continue
            reason = "Protected by confirmed intent"
            if protected_value["sources"]:
                reason += ": " + ", ".join(dict.fromkeys(protected_value["sources"]))
            selected_records.append(self._record(
                card,
                qty=1,
                source="protected",
                role="protected package",
                reason=reason + ".",
                evidence=["confirmed build constraint"],
                confidence=1.0,
            ))
            selected_facts.append({**card, "qty": 1})
            selected_names.add(str(card.get("name")).casefold())

        analysis = {
            "suggestions_add": [],
            "strategy_profile": {"lanes": []},
            "coverage_level": "unavailable",
            "recommendation_planner": {},
        }
        can_analyze = commander_cards and intent.get("build_shape") != "mana_base"
        if can_analyze and len(selected_records) < request_limit:
            analysis_deck = {
                "commander": commander_cards[0].get("name"),
                "commanders": [card.get("name") for card in commander_cards],
                "cards": [_deck_card(card, _quantity(card.get("qty", 1))) for card in hydrated_fixed],
                "color_identity": color_identity,
                "intent_profile": normalized["deck_intent_profile"],
            }
            analysis = await self.engine.analyze_deck(analysis_deck, deep=True)

        suggestions = [
            suggestion for suggestion in analysis.get("suggestions_add") or []
            if suggestion.get("card_name") and not suggestion.get("action_only")
        ]
        suggestion_facts = await self._resolve(
            suggestion["card_name"] for suggestion in suggestions
        )
        collection_mode = intent.get("collection_mode")

        def suggestion_key(suggestion: Mapping) -> tuple:
            card_key = _name(suggestion.get("card_name")).casefold()
            owned_bonus = 6 if collection_mode == "prefer_owned" and card_key in owned else 0
            return (
                -(float(suggestion.get("score") or 0) + owned_bonus),
                int(suggestion.get("selection_position") or 999),
                card_key,
            )

        for suggestion in sorted(suggestions, key=suggestion_key):
            if len(selected_records) >= request_limit:
                break
            card_name = _name(suggestion.get("card_name"))
            key = card_name.casefold()
            if key in selected_names or key in excluded:
                continue
            if collection_mode == "owned_only" and key not in owned:
                rejected.append(_issue(
                    "owned_only_rejection",
                    f"{card_name} is outside the owned-only candidate pool.",
                    card_name=card_name,
                ))
                continue
            card = suggestion_facts.get(key)
            if not card:
                rejected.append(_issue(
                    "candidate_unresolved",
                    f"{card_name} could not be re-verified before construction.",
                    card_name=card_name,
                ))
                continue
            legality = self._card_legality_errors(card, color_identity)
            if legality:
                rejected.append(_issue(
                    "candidate_illegal",
                    f"{card.get('name')} {' and '.join(legality)}.",
                    card_name=card.get("name"),
                ))
                continue
            if not accept_price(card, 1):
                continue
            evidence = [
                *list(suggestion.get("evidence_tags") or []),
                *list(suggestion.get("matched_plan_lanes") or []),
            ]
            selected_records.append(self._record(
                card,
                qty=1,
                source="planner_v3",
                role=suggestion.get("role_tag"),
                reason=suggestion.get("reason") or "Selected by the evidence portfolio.",
                evidence=list(dict.fromkeys(evidence)),
                confidence=suggestion.get("confidence"),
            ))
            selected_records[-1]["selection_reason"] = suggestion.get("selection_reason")
            selected_records[-1]["portfolio_version"] = suggestion.get("portfolio_version")
            selected_facts.append({**card, "qty": 1})
            selected_names.add(str(card.get("name")).casefold())

        fixed_land_count = sum(
            _quantity(card.get("qty", 1)) for card in hydrated_fixed if _is_land(card)
        )
        land_target = self._mana_target(
            commander_cards,
            [*hydrated_fixed, *selected_facts],
            intent,
        )
        land_needed = max(0, land_target - fixed_land_count - sum(
            _quantity(card.get("qty", 1)) for card in selected_facts if _is_land(card)
        ))
        allow_mana = intent.get("build_shape") in {"full_deck", "missing_slots", "mana_base"}
        mana_capacity = max(0, request_limit - sum(record["qty"] for record in selected_records))
        mana_slots = min(land_needed, mana_capacity) if allow_mana else 0
        mana_allocation: Dict[str, int] = {}
        if mana_slots:
            demand = self._mana_demand(
                [*commander_cards, *hydrated_fixed, *selected_facts],
                color_identity,
            )
            mana_allocation = _largest_remainder(demand, mana_slots)
            basic_names = [BASIC_LANDS[color] for color in mana_allocation]
            basic_cards = await self._resolve(basic_names)
            for color in sorted(mana_allocation, key=lambda value: "WUBRGC".index(value)):
                qty = mana_allocation[color]
                basic_name = BASIC_LANDS[color]
                card = basic_cards.get(basic_name.casefold())
                if not card:
                    warnings.append(_issue(
                        "basic_land_unresolved",
                        f"{basic_name} could not be verified, so {qty} mana slots remain unresolved.",
                        card_name=basic_name,
                    ))
                    continue
                if not accept_price(card, qty):
                    continue
                selected_records.append(self._record(
                    card,
                    qty=qty,
                    source="mana_baseline",
                    role="mana base",
                    reason=(
                        f"Baseline {basic_name} allocation follows measured {color} mana-symbol "
                        "demand. Nonbasic fixing remains a separately reviewable slot."
                    ),
                    evidence=["color identity", "mana-symbol demand", "basic-land baseline"],
                    confidence=0.9,
                ))
                selected_facts.append({**card, "qty": qty})

        selected_slots = sum(record["qty"] for record in selected_records)
        proposed_slots = fixed_slots + selected_slots
        remaining_mainboard = max(0, target_mainboard - proposed_slots)
        unresolved_within_scope = max(0, request_limit - selected_slots)
        deferred_slots = max(0, open_slots - request_limit)
        role_allocation = self._allocation(
            (analysis.get("strategy_profile") or {}).get("lanes") or [],
            max(0, request_limit - min(land_needed, request_limit)),
        )
        covered_lanes = Counter()
        for record in selected_records:
            if record.get("role"):
                covered_lanes[str(record["role"])] += record["qty"]

        unresolved_slots = []
        if unresolved_within_scope:
            unresolved_slots.append({
                "lane": "evidence-qualified additions",
                "count": unresolved_within_scope,
                "reason": (
                    "No remaining candidate cleared every evidence, legality, intent, budget, "
                    "collection, and portfolio gate."
                ),
            })
        if allow_mana and land_needed > mana_slots:
            unresolved_slots.append({
                "lane": "mana base",
                "count": land_needed - mana_slots,
                "reason": "The bounded scaffold did not have enough slots for the full land baseline.",
            })

        if total_budget is not None and intent.get("budget_mode") in {"target", "flexible"} and running_price > total_budget:
            warnings.append(_issue(
                "budget_target_exceeded",
                "The proposed scaffold exceeds the declared soft total-budget target.",
            ))
        if proposed_slots < target_mainboard:
            warnings.append(_issue(
                "partial_scaffold",
                f"The scaffold leaves {remaining_mainboard} main-deck slots open for later validated passes.",
            ))
        if unknown_fixed_prices and not strict_budget:
            warnings.append(_issue(
                "budget_partially_unpriced",
                "Some fixed cards have no current USD price, so the displayed total is partial.",
            ))

        proposed_main_deck = [record["deck_card"] for record in [*fixed_records, *selected_records]]
        status = "blocked" if errors else "ready_partial" if remaining_mainboard else "ready_complete"
        if not selected_records and not errors:
            status = "abstained"
        confidence_values = [
            float(record["confidence"])
            for record in selected_records
            if record.get("confidence") is not None
        ]
        evidence_confidence = (
            round(sum(confidence_values) / len(confidence_values), 3)
            if confidence_values else None
        )
        return {
            "constructor_version": self.VERSION,
            "status": status,
            "source_fingerprint": self.source_fingerprint(deck, normalized),
            "scope": {
                "build_shape": intent.get("build_shape"),
                "target_mainboard_slots": target_mainboard,
                "fixed_slots": fixed_slots,
                "open_slots_before": open_slots,
                "request_slot_limit": request_limit,
                "selected_slots": selected_slots,
                "deferred_slots": deferred_slots,
                "remaining_mainboard_slots": remaining_mainboard,
                "runtime_mode": self.mode,
            },
            "commander": {
                "names": [card.get("name") for card in commander_cards],
                "color_identity": color_identity,
            },
            "intent": intent,
            "fixed_cards": fixed_records,
            "selected_cards": selected_records,
            "proposed_main_deck": proposed_main_deck,
            "role_allocation": role_allocation,
            "covered_roles": dict(covered_lanes),
            "mana_base": {
                "target_lands": land_target,
                "fixed_lands": fixed_land_count,
                "basic_land_allocation": {
                    BASIC_LANDS[color]: count for color, count in mana_allocation.items()
                },
            },
            "unresolved_slots": unresolved_slots,
            "validation": {
                "passed": not errors,
                "errors": errors,
                "warnings": warnings,
                "rejected_candidates": rejected,
                "checks": {
                    "legality": not any("illegal" in issue["code"] for issue in errors),
                    "singleton": not any(issue["code"] == "singleton_violation" for issue in errors),
                    "budget": not any("budget" in issue["code"] for issue in errors),
                    "protected_and_excluded": not any(
                        issue["code"].startswith(("protected_", "fixed_card_excluded"))
                        for issue in errors
                    ),
                    "collection": not any("owned" in issue["code"] for issue in errors),
                    "deck_count": proposed_slots <= target_mainboard,
                },
            },
            "budget": {
                "mode": intent.get("budget_mode"),
                "verified_subtotal_usd": round(running_price, 2),
                "total_limit_usd": total_budget,
                "per_card_limit_usd": max_card_price,
                "unpriced_fixed_cards": unknown_fixed_prices,
            },
            "evidence": {
                "coverage_level": analysis.get("coverage_level"),
                "average_selected_confidence": evidence_confidence,
                "planner": analysis.get("recommendation_planner") or {},
            },
        }


def build_revision_diff(previous: Optional[Mapping], current: Mapping) -> Dict:
    """Explain selected-card changes between deterministic draft revisions."""

    def selected(value: Optional[Mapping]) -> Counter:
        return Counter({
            str(card.get("name")): _quantity(card.get("qty", 1))
            for card in (value or {}).get("selected_cards") or []
            if card.get("name")
        })

    before = selected(previous)
    after = selected(current)
    return {
        "added": [
            {"name": name, "qty": qty}
            for name, qty in sorted((after - before).items())
        ],
        "removed": [
            {"name": name, "qty": qty}
            for name, qty in sorted((before - after).items())
        ],
        "unchanged": sorted(set(before) & set(after)),
    }
