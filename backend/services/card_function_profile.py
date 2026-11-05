"""Shared deterministic card-function facts for recommendation safety.

The profile deliberately stays narrower than full rules interpretation.  A fact is
only emitted when Oracle text contains evidence strong enough for additions, cuts,
and explanations to use consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import FrozenSet, Mapping, Optional


ALTERNATE_COST_PHRASES = (
    "rather than pay this spell's mana cost",
    "rather than pay its mana cost",
    "rather than paying this spell's mana cost",
    "without paying its mana cost",
    "without paying their mana costs",
    "you may pay {0} rather than",
    "you may cast it for",
    "you may cast this spell for",
)

EXTRA_COMBAT_PHRASES = (
    "additional combat phase",
    "extra combat phase",
)

KNOWN_COUNTER_DOMAINS = (
    "+1/+1",
    "-1/-1",
    "age",
    "charge",
    "corpse",
    "credit",
    "energy",
    "experience",
    "fate",
    "finality",
    "flood",
    "foreshadow",
    "indestructible",
    "ki",
    "knowledge",
    "level",
    "lore",
    "loyalty",
    "oil",
    "page",
    "poison",
    "quest",
    "shield",
    "slime",
    "stun",
    "time",
    "verse",
)


@dataclass(frozen=True)
class CardFunctionProfile:
    mana_value: float
    practical_mana_value: float
    alternate_cast: bool
    counter_domains: FrozenSet[str]
    functions: FrozenSet[str]

    def has(self, function: str) -> bool:
        return function in self.functions


def combined_oracle_text(card: Mapping) -> str:
    values = [str(card.get("oracle_text") or "")]
    values.extend(
        str(face.get("oracle_text") or "")
        for face in card.get("card_faces") or []
        if isinstance(face, Mapping)
    )
    return "\n".join(value for value in values if value).casefold()


def combined_type_line(card: Mapping) -> str:
    values = [str(card.get("type_line") or "")]
    values.extend(
        str(face.get("type_line") or "")
        for face in card.get("card_faces") or []
        if isinstance(face, Mapping)
    )
    return "\n".join(value for value in values if value).casefold()


def has_alternate_cast(text: str) -> bool:
    source = str(text or "").casefold()
    return any(phrase in source for phrase in ALTERNATE_COST_PHRASES) or any(
        keyword in source
        for keyword in ("delve", "convoke", "improvise", "affinity for")
    )


def has_extra_combat(text: str) -> bool:
    source = str(text or "").casefold()
    return any(phrase in source for phrase in EXTRA_COMBAT_PHRASES)


def counter_domains(text: str) -> FrozenSet[str]:
    """Return explicitly named counter resources without merging their plans."""
    source = str(text or "").casefold()
    domains = {
        domain
        for domain in KNOWN_COUNTER_DOMAINS
        if f"{domain} counter" in source
    }
    if "+1/+1 counters" in source or "+1/+1 counter" in source:
        domains.add("+1/+1")
    if "-1/-1 counters" in source or "-1/-1 counter" in source:
        domains.add("-1/-1")
    ignored = {
        "additional", "any", "each", "fewer", "many", "more", "one",
        "several", "target", "that", "the", "those", "two", "three",
    }
    for match in re.finditer(r"\b([a-z][a-z-]{1,24}) counters?\b", source):
        term = match.group(1)
        if term not in ignored:
            domains.add(term)
    return frozenset(domains)


def counter_resources_compatible(
    commander_card: Mapping,
    candidate_card: Mapping,
) -> bool:
    """Require matching named resources; proliferate is support, not creation."""
    commander_text = combined_oracle_text(commander_card)
    candidate_text = combined_oracle_text(candidate_card)
    commander_domains = counter_domains(commander_text)
    candidate_domains = counter_domains(candidate_text)

    if not commander_domains:
        return True
    if "proliferate" in candidate_text:
        return True
    if candidate_domains:
        return bool(commander_domains & candidate_domains)
    generic_counter_language = any(
        phrase in candidate_text
        for phrase in (
            "counter on target",
            "counter on a creature",
            "counter on each",
            "counter on it",
            "counter on them",
            "for each counter",
            "move any number of counters",
        )
    )
    return generic_counter_language


def classify_card_functions(card: Mapping) -> CardFunctionProfile:
    text = combined_oracle_text(card)
    type_line = combined_type_line(card)
    try:
        mana_value = float(card.get("cmc") or 0)
    except (TypeError, ValueError):
        mana_value = 0.0

    alternate = has_alternate_cast(text)
    practical_mana_value = min(mana_value, 2.0) if alternate else mana_value
    functions = set()

    if has_extra_combat(text):
        functions.add("extra_combat")
    if "untap" in text or "vigilance" in text:
        functions.add("untap_support")

    fixing_signal = any(
        phrase in text
        for phrase in (
            "add one mana of any color",
            "add one mana of any type",
            "lands you control have",
            "mana of any color in your commander's color identity",
            "mana of any color among",
        )
    )
    conditional_fixing = any(
        phrase in text
        for phrase in (
            "exile target land card from a graveyard",
            "sacrifice a food: add one mana of any color",
            "sacrifice a food: add one mana",
            "creature tokens you control have",
            "create a treasure token",
            "create two treasure tokens",
            "create three treasure tokens",
            "sacrifice this artifact: add one mana of any color",
            "sacrifice this token: add one mana of any color",
            "spend this mana only",
        )
    )
    if fixing_signal and not conditional_fixing:
        functions.add("mana_fixing")
    elif fixing_signal:
        functions.add("conditional_mana_fixing")

    if any(
        phrase in text
        for phrase in (
            "creatures can't attack you unless",
            "creatures cannot attack you unless",
            "can't attack you or planeswalkers you control unless",
            "cannot attack you or planeswalkers you control unless",
            "prevent all combat damage that would be dealt to you",
        )
    ):
        functions.add("defensive_engine")

    if "search your library" in text and not any(
        phrase in text
        for phrase in (
            "basic land card",
            "land card",
            "plains card",
            "island card",
            "swamp card",
            "mountain card",
            "forest card",
        )
    ):
        functions.add("tutor")

    repeatable_markers = (
        "at the beginning of",
        "whenever you cast",
        "whenever a creature you control",
        "whenever one or more creatures you control",
        "whenever another creature",
        "whenever an artifact",
        "whenever an enchantment",
        "once during each of your turns",
        "you may cast permanent spells",
        "you may play lands",
    )
    resource_markers = (
        "draw a card",
        "draw that many cards",
        "add {",
        "create a treasure",
        "return target",
        "cast that card",
        "play that card",
        "cost {1} less",
        "costs {1} less",
    )
    if (
        any(marker in text for marker in repeatable_markers)
        and any(marker in text for marker in resource_markers)
    ) or "you may cast permanent spells of each permanent type from your graveyard" in text:
        functions.add("engine")

    closer_patterns = (
        r"creatures you control get \+[x0-9*]+/\+[x0-9*]+",
        r"creatures you control gain trample",
        r"each opponent loses .* life",
        r"you win the game",
        r"target player loses the game",
    )
    if has_extra_combat(text) or any(re.search(pattern, text) for pattern in closer_patterns):
        functions.add("closer")
    if "trample until end of turn" in text and "greatest power" in text:
        functions.add("closer")
    if "each other creature becomes a copy" in text:
        functions.add("closer")
        functions.add("board_copy_closer")
    if (
        "at the beginning of combat" in text
        and "become a copy of another target creature you control" in text
        and re.search(r"\bgains? haste\b", text)
    ):
        functions.add("combat_combo_enabler")

    interaction = any(
        phrase in text
        for phrase in (
            "counter target spell",
            "counter target activated",
            "counter target triggered",
            "exile target spell",
            "destroy target",
            "exile target permanent",
            "return target nonland permanent",
            "damage divided as you choose",
            "damage to any target",
            "damage to each creature",
            "destroy each nonland permanent",
        )
    )
    if interaction:
        functions.add("interaction")
    if interaction and (alternate or practical_mana_value <= 1):
        functions.add("free_interaction" if alternate else "efficient_interaction")
    if interaction and any(
        phrase in text
        for phrase in (
            "destroy each nonland permanent",
            "exile all",
            "destroy all",
            "can't be countered",
            "cannot be countered",
        )
    ):
        functions.add("high_leverage_interaction")

    if alternate:
        functions.add("alternate_cast")
    if "instant" in type_line and interaction and practical_mana_value <= 2:
        functions.add("efficient_interaction")

    return CardFunctionProfile(
        mana_value=mana_value,
        practical_mana_value=practical_mana_value,
        alternate_cast=alternate,
        counter_domains=counter_domains(text),
        functions=frozenset(functions),
    )


def strategic_cut_block_reason(
    card: Mapping,
    *,
    color_count: int = 0,
    strategy_priorities: Optional[set[str]] = None,
) -> Optional[str]:
    """Return why a heuristic cut is unsafe, otherwise allow further checks."""
    profile = classify_card_functions(card)
    priorities = strategy_priorities or set()

    if profile.alternate_cast and profile.has("interaction"):
        return "alternate-cost interaction must be evaluated by practical casting mode"
    if profile.has("mana_fixing") and color_count >= 3:
        return "mana fixing is a structural pillar in a multicolor deck"
    if profile.has("tutor"):
        return "typed library access has strategic package value"
    if profile.has("high_leverage_interaction"):
        return "high-leverage interaction is not a generic high-mana flex slot"
    if profile.has("closer") and priorities & {
        "go_wide", "typal", "combat_combo", "compact_wins",
    }:
        return "a declared closing payoff must be preserved"
    if profile.has("combat_combo_enabler") and "combat_combo" in priorities:
        return "a combat-copy enabler supports the declared compact combat plan"
    if profile.has("defensive_engine") and priorities & {"politics", "donation"}:
        return "political defense is part of the declared table-facing plan"
    if profile.has("engine") and priorities:
        return "repeatable resource engines require explicit replacement evidence"
    return None
