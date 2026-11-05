"""Measurable deck-plan invariants for safe additions, cuts, and swaps."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Mapping, Optional

from services.deck_dependencies import (
    build_dependency_graph,
    dependency_cut_requirements,
    dependency_requirement_label,
    dependency_traits,
)


COMMON_CREATURE_CLASSES = {
    "advisor",
    "artificer",
    "assassin",
    "bard",
    "cleric",
    "druid",
    "knight",
    "monk",
    "ninja",
    "rogue",
    "shaman",
    "soldier",
    "warlock",
    "warrior",
    "wizard",
}


def build_deck_invariants(
    cards: List[Mapping],
    intent_profile: Optional[Mapping],
    commander_constraints: Optional[Mapping] = None,
    commander_synergies: Optional[List[str]] = None,
) -> Dict:
    constraints = set((intent_profile or {}).get("intentional_constraints", []))
    commander_constraints = commander_constraints or {}
    commander_synergies = commander_synergies or []
    result = {
        "active": [],
        "typal": None,
        "spell_density": None,
        "aura_ladder": None,
        "card_type_spread": None,
        "sacrifice_engine": None,
        "protected_packages": [],
        "dependencies": build_dependency_graph(cards),
    }
    if "typal_core" in constraints:
        typal = _detect_typal_invariant(cards)
        if typal:
            result["typal"] = typal
            result["active"].append(f"typal:{typal['creature_type'].casefold()}")
    if "spell_density" in constraints:
        spell = _detect_spell_invariant(cards)
        result["spell_density"] = spell
        result["active"].append("spell_density")
    if commander_constraints.get("aura_tutor_chain"):
        aura_ladder = _detect_aura_ladder(cards)
        result["aura_ladder"] = aura_ladder
        result["active"].append("aura_ladder")
    if (
        commander_constraints.get("card_type_diversity")
        or commander_constraints.get("graveyard_permanent_engine")
    ):
        permanent_only = bool(
            commander_constraints.get("graveyard_permanent_engine")
            and not commander_constraints.get("card_type_diversity")
        )
        card_type_spread = _detect_card_type_spread(
            cards,
            permanent_only=permanent_only,
            tracked_types=commander_constraints.get("card_types_mentioned"),
        )
        result["card_type_spread"] = card_type_spread
        result["active"].append(
            "permanent_type_spread" if permanent_only else "card_type_spread"
        )
    if "sacrifice" in commander_synergies:
        sacrifice_engine = _detect_sacrifice_engine(cards)
        result["sacrifice_engine"] = sacrifice_engine
        result["active"].append("sacrifice_engine")
    packages = _protected_package_coverage(cards, intent_profile or {})
    if packages:
        result["protected_packages"] = packages
        result["active"].extend(
            f"package:{package['key']}" for package in packages
        )
    if result["dependencies"]["active"]:
        result["active"].append("dependency_graph")
    return result


def card_invariant_traits(card: Mapping, invariants: Mapping) -> List[str]:
    traits = []
    type_line = str(card.get("type_line") or "").casefold()
    oracle_text = str(card.get("oracle_text") or "").casefold()
    typal = invariants.get("typal")
    if typal:
        creature_type = str(typal["creature_type"]).casefold()
        subtypes = {value.casefold() for value in _creature_subtypes(type_line)}
        token_pattern = re.compile(
            rf"\b{re.escape(creature_type)}\b[^.]*\bcreature token"
        )
        if creature_type in subtypes or token_pattern.search(oracle_text):
            traits.append(f"typal:{creature_type}")
    if invariants.get("spell_density") and _is_instant_or_sorcery(type_line):
        traits.append("spell_density")
    aura_ladder = invariants.get("aura_ladder")
    if aura_ladder and _is_aura(type_line):
        traits.append("aura_density")
        traits.append(f"aura_mv:{_mana_value_bucket(card.get('cmc', 0))}")
    card_type_spread = invariants.get("card_type_spread")
    if card_type_spread:
        card_types = _card_types(type_line)
        if card_type_spread.get("permanent_only") and card_types & {
            "artifact",
            "battle",
            "creature",
            "enchantment",
            "land",
            "planeswalker",
        }:
            traits.append("permanent_engine")
        traits.extend(f"card_type:{card_type}" for card_type in sorted(card_types))
    sacrifice_engine = invariants.get("sacrifice_engine")
    if sacrifice_engine:
        traits.extend(
            f"sacrifice:{component}"
            for component in _sacrifice_traits(oracle_text, type_line)
        )
    card_name = str(card.get("name") or "").strip().casefold()
    for package in invariants.get("protected_packages") or []:
        if card_name in set(package.get("card_keys") or []):
            traits.append(f"package:{package['key']}")
    traits.extend(dependency_traits(card, invariants.get("dependencies")))
    return list(dict.fromkeys(traits))


def apply_invariants_to_suggestion(
    suggestion: Mapping,
    card_data: Mapping,
    invariants: Mapping,
) -> Optional[Dict]:
    result = dict(suggestion)
    traits = card_invariant_traits(card_data, invariants)
    alignments = []
    warnings = []
    evidence_tags = set(result.get("evidence_tags") or [])
    penalty_tags = set(result.get("penalty_tags") or [])
    score_delta = 0
    role = str(result.get("role_tag") or "").casefold()
    type_line = str(card_data.get("type_line") or "").casefold()

    typal = invariants.get("typal")
    if typal:
        typal_trait = f"typal:{str(typal['creature_type']).casefold()}"
        if typal_trait in traits:
            alignments.append(
                f"Preserves {typal['creature_type']} density"
            )
            evidence_tags.add("archetype_invariant")
        elif role in {"tokens", "creature", "typal", "tribal"}:
            return None
        elif "creature" in type_line:
            score_delta -= 14
            warnings.append(
                f"Off-type creature for the declared {typal['creature_type']} core"
            )
            penalty_tags.add("off_typal_creature")

    if invariants.get("spell_density"):
        if "spell_density" in traits:
            alignments.append("Preserves instant/sorcery density")
            evidence_tags.add("archetype_invariant")
        elif role == "instant_sorcery":
            return None

    aura_ladder = invariants.get("aura_ladder")
    if aura_ladder:
        aura_traits = {trait for trait in traits if trait.startswith("aura_")}
        if "aura_density" in aura_traits:
            alignments.append("Preserves the Aura tutor ladder")
            evidence_tags.add("archetype_invariant")
            mana_value_trait = next(
                (trait for trait in aura_traits if trait.startswith("aura_mv:")),
                None,
            )
            if mana_value_trait and mana_value_trait.split(":", 1)[1] in set(
                aura_ladder.get("missing_core_mana_values") or []
            ):
                score_delta += 8
                alignments.append("Fills a missing Aura mana-value rung")
        elif role in {"voltron", "enchantment"}:
            return None

    card_type_spread = invariants.get("card_type_spread")
    if card_type_spread:
        type_traits = {
            trait.split(":", 1)[1]
            for trait in traits
            if trait.startswith("card_type:")
        }
        underrepresented = set(card_type_spread.get("underrepresented_types") or [])
        supplied = sorted(type_traits & underrepresented)
        if supplied:
            score_delta += min(10, len(supplied) * 5)
            alignments.append(
                "Strengthens underrepresented card types: "
                + ", ".join(value.title() for value in supplied)
            )
            evidence_tags.add("archetype_invariant")
        if (
            card_type_spread.get("permanent_only")
            and role in {
                "draw",
                "ramp",
                "removal",
                "sweeper",
                "protection",
            }
            and "permanent_engine" not in traits
        ):
            score_delta -= 12
            warnings.append(
                "Nonpermanent role card in a deck that reuses permanent types"
            )
            penalty_tags.add("permanent_engine_mismatch")

    sacrifice_engine = invariants.get("sacrifice_engine")
    if sacrifice_engine:
        sacrifice_traits = {
            trait.split(":", 1)[1]
            for trait in traits
            if trait.startswith("sacrifice:")
        }
        if role == "sacrifice" and not sacrifice_traits:
            return None
        deficient = set(sacrifice_engine.get("deficient_components") or [])
        supplied = sorted(sacrifice_traits & deficient)
        if supplied:
            score_delta += min(12, len(supplied) * 6)
            alignments.append(
                "Fills sacrifice-engine need: "
                + ", ".join(supplied)
            )
            evidence_tags.add("archetype_invariant")

    package_traits = [
        trait for trait in traits if trait.startswith("package:")
    ]
    if package_traits:
        package_names = {
            package["key"]: package["name"]
            for package in invariants.get("protected_packages") or []
        }
        names = [
            package_names.get(trait.split(":", 1)[1], trait.split(":", 1)[1])
            for trait in package_traits
        ]
        score_delta += 12
        alignments.append("Matches declared package: " + ", ".join(names))
        evidence_tags.add("declared_package_fit")

    dependencies = invariants.get("dependencies") or {}
    tutor_package_by_key = {
        package["key"]: package
        for package in dependencies.get("tutor_packages") or []
    }
    tutor_traits = [
        trait for trait in traits if trait.startswith("tutor_target:")
    ]
    dependency_delta = 0
    for trait in tutor_traits:
        package = tutor_package_by_key.get(trait.split(":", 1)[1])
        if not package or package.get("status") == "healthy":
            continue
        bonus = 10 if package.get("status") == "dead" else 6
        dependency_delta = max(dependency_delta, bonus)
        alignments.append(
            f"Adds a target for {', '.join(package['source_cards'])} "
            f"({package['label']})"
        )
        evidence_tags.add("dependency_target_fit")

    missing_named_links = {
        link["key"]: link
        for link in dependencies.get("named_links") or []
        if not link.get("present")
    }
    for trait in traits:
        if not trait.startswith("named_dependency:"):
            continue
        link = missing_named_links.get(trait.split(":", 1)[1])
        if not link:
            continue
        dependency_delta = max(dependency_delta, 14)
        alignments.append(
            f"Restores the exact card named by {link['source_card']}"
        )
        evidence_tags.add("named_dependency_fit")
    score_delta += dependency_delta

    result["score"] = max(0, int(result.get("score") or 0) + score_delta)
    if score_delta:
        result["confidence"] = round(
            min(float(result.get("confidence") or 0), 0.64),
            2,
        )
    result["invariant_traits"] = traits
    result["invariant_alignment"] = alignments
    result["invariant_warnings"] = warnings
    result["invariant_score_delta"] = score_delta
    result["evidence_tags"] = sorted(evidence_tags)
    result["penalty_tags"] = sorted(penalty_tags)
    note_parts = alignments + warnings
    if note_parts:
        result["reason"] = _append_reason(
            str(result.get("reason") or ""),
            "Deck-plan check: " + "; ".join(note_parts) + ".",
        )
    return result


def apply_invariants_to_cuts(
    cuts: List[Mapping],
    cards: List[Mapping],
    invariants: Mapping,
) -> List[Dict]:
    cards_by_name = {
        str(card.get("name") or "").casefold(): card
        for card in cards
        if card.get("name")
    }
    results = []
    for cut in cuts:
        row = dict(cut)
        card = cards_by_name.get(str(row.get("card_name") or "").casefold(), {})
        requirements = _cut_invariant_requirements(card, invariants)
        row["preservation_requirements"] = requirements
        row["invariant_alignment"] = []
        row["invariant_warnings"] = []
        if requirements:
            labels = [
                _requirement_label(value, invariants) for value in requirements
            ]
            warning = "Only replace this slot with " + " and ".join(labels)
            row["invariant_warnings"] = [warning]
            row["reason"] = _append_reason(
                str(row.get("reason") or ""),
                "Deck-plan check: " + warning + ".",
            )
            row["confidence"] = round(
                min(float(row.get("confidence") or 0), 0.62),
                2,
            )
        results.append(row)
    return results


def addition_satisfies_cut_invariants(
    addition: Mapping,
    cut: Mapping,
) -> bool:
    required = set(cut.get("preservation_requirements") or [])
    traits = set(addition.get("invariant_traits") or [])
    return required <= traits


def _cut_invariant_requirements(
    card: Mapping,
    invariants: Mapping,
) -> List[str]:
    traits = card_invariant_traits(card, invariants)
    requirements = []
    aura_ladder = invariants.get("aura_ladder") or {}
    card_type_spread = invariants.get("card_type_spread") or {}
    sacrifice_engine = invariants.get("sacrifice_engine") or {}
    protected_types = set(card_type_spread.get("protected_types") or [])
    component_counts = sacrifice_engine.get("component_counts") or {}
    component_floors = sacrifice_engine.get("component_floors") or {}

    for trait in traits:
        if trait.startswith("typal:") or trait == "spell_density":
            requirements.append(trait)
        elif trait == "aura_density":
            requirements.append(trait)
        elif trait.startswith("aura_mv:"):
            mana_value = trait.split(":", 1)[1]
            if int(aura_ladder.get("mana_value_counts", {}).get(mana_value, 0)) <= 1:
                requirements.append(trait)
        elif trait.startswith("card_type:"):
            card_type = trait.split(":", 1)[1]
            if card_type in protected_types:
                requirements.append(trait)
        elif trait.startswith("sacrifice:"):
            component = trait.split(":", 1)[1]
            if int(component_counts.get(component, 0)) <= int(
                component_floors.get(component, 0)
            ):
                requirements.append(trait)
        elif trait.startswith("package:"):
            requirements.append(trait)
    requirements.extend(
        dependency_cut_requirements(card, invariants.get("dependencies"))
    )
    return list(dict.fromkeys(requirements))


def _detect_typal_invariant(cards: List[Mapping]) -> Optional[Dict]:
    subtype_counts = Counter()
    creature_cards = 0
    for card in cards:
        quantity = _quantity(card)
        type_line = str(card.get("type_line") or "")
        if "creature" not in type_line.casefold():
            continue
        creature_cards += quantity
        for subtype in set(_creature_subtypes(type_line)):
            subtype_counts[subtype] += quantity
    if not subtype_counts or creature_cards == 0:
        return None

    ranked = sorted(
        subtype_counts.items(),
        key=lambda item: (
            -item[1],
            item[0].casefold() in COMMON_CREATURE_CLASSES,
            item[0].casefold(),
        ),
    )
    creature_type, count = ranked[0]
    if (
        creature_type.casefold() == "human"
        and len(ranked) > 1
        and ranked[1][1] >= count * 0.60
    ):
        creature_type, count = ranked[1]
    share = count / creature_cards
    if count < 6 or share < 0.20:
        return None
    return {
        "creature_type": creature_type,
        "on_type_cards": count,
        "creature_cards": creature_cards,
        "creature_share": round(share, 4),
        "minimum_on_type_cards": count,
    }


def _detect_aura_ladder(cards: List[Mapping]) -> Dict:
    mana_value_counts = Counter()
    aura_cards = 0
    unique_names = set()
    for card in cards:
        type_line = str(card.get("type_line") or "").casefold()
        if not _is_aura(type_line):
            continue
        quantity = _quantity(card)
        aura_cards += quantity
        mana_value_counts[_mana_value_bucket(card.get("cmc", 0))] += quantity
        if card.get("name"):
            unique_names.add(str(card["name"]).casefold())
    core_values = ["1", "2", "3", "4"]
    return {
        "aura_cards": aura_cards,
        "unique_aura_names": len(unique_names),
        "mana_value_counts": dict(sorted(mana_value_counts.items())),
        "covered_mana_values": sorted(mana_value_counts),
        "missing_core_mana_values": [
            value for value in core_values if mana_value_counts[value] == 0
        ],
        "minimum_aura_cards": aura_cards,
    }


def _detect_card_type_spread(
    cards: List[Mapping],
    permanent_only: bool,
    tracked_types: Optional[List[str]] = None,
) -> Dict:
    counts = Counter()
    allowed_types = {
        "artifact",
        "battle",
        "creature",
        "enchantment",
        "land",
        "planeswalker",
    }
    if not permanent_only:
        allowed_types.update({"instant", "kindred", "sorcery"})
    if tracked_types:
        allowed_types &= {value.casefold() for value in tracked_types}
    for card in cards:
        quantity = _quantity(card)
        for card_type in _card_types(str(card.get("type_line") or "")):
            if card_type in allowed_types:
                counts[card_type] += quantity
    protected_types = sorted(
        card_type for card_type, count in counts.items() if 0 < count <= 3
    )
    underrepresented = sorted(
        card_type for card_type in allowed_types if counts[card_type] < 3
    )
    return {
        "permanent_only": permanent_only,
        "type_counts": dict(sorted(counts.items())),
        "protected_types": protected_types,
        "underrepresented_types": underrepresented,
        "minimum_type_presence": 1,
    }


def _detect_sacrifice_engine(cards: List[Mapping]) -> Dict:
    counts = Counter()
    for card in cards:
        quantity = _quantity(card)
        oracle_text = str(card.get("oracle_text") or "").casefold()
        type_line = str(card.get("type_line") or "").casefold()
        for component in _sacrifice_traits(oracle_text, type_line):
            counts[component] += quantity
    desired = {"outlet": 2, "payoff": 3, "fodder": 6}
    floors = {
        component: min(counts[component], target)
        for component, target in desired.items()
    }
    return {
        "component_counts": {
            component: counts[component]
            for component in ("outlet", "payoff", "fodder")
        },
        "desired_components": desired,
        "component_floors": floors,
        "deficient_components": [
            component
            for component, target in desired.items()
            if counts[component] < target
        ],
    }


def _protected_package_coverage(
    cards: List[Mapping],
    intent_profile: Mapping,
) -> List[Dict]:
    present = {
        str(card.get("name") or "").strip().casefold()
        for card in cards
        if str(card.get("name") or "").strip()
    }
    results = []
    for package in intent_profile.get("protected_packages") or []:
        if not isinstance(package, Mapping):
            continue
        name = str(package.get("name") or "").strip()
        package_cards = [
            str(card).strip()
            for card in package.get("cards") or []
            if str(card).strip()
        ]
        if not name or not package_cards:
            continue
        card_keys = [card.casefold() for card in package_cards]
        present_cards = [
            card for card in package_cards if card.casefold() in present
        ]
        missing_cards = [
            card for card in package_cards if card.casefold() not in present
        ]
        results.append({
            "name": name,
            "key": _package_key(name),
            "declared_cards": package_cards,
            "card_keys": card_keys,
            "present_cards": present_cards,
            "missing_cards": missing_cards,
            "complete": not missing_cards,
        })
    return results


def _detect_spell_invariant(cards: List[Mapping]) -> Dict:
    spell_cards = 0
    nonland_cards = 0
    for card in cards:
        quantity = _quantity(card)
        type_line = str(card.get("type_line") or "").casefold()
        if "land" not in type_line:
            nonland_cards += quantity
        if _is_instant_or_sorcery(type_line):
            spell_cards += quantity
    share = spell_cards / nonland_cards if nonland_cards else 0.0
    return {
        "instant_sorcery_cards": spell_cards,
        "nonland_cards": nonland_cards,
        "nonland_share": round(share, 4),
        "minimum_instant_sorcery_cards": spell_cards,
    }


def _creature_subtypes(type_line: str) -> List[str]:
    parts = re.split(r"\s+[—–-]\s+", type_line, maxsplit=1)
    if len(parts) < 2 or "creature" not in parts[0].casefold():
        return []
    return [
        value.strip(" ,")
        for value in parts[1].split()
        if value.strip(" ,")
    ]


def _card_types(type_line: str) -> set[str]:
    normalized = type_line.casefold()
    return {
        card_type
        for card_type in {
            "artifact",
            "battle",
            "creature",
            "enchantment",
            "instant",
            "kindred",
            "land",
            "planeswalker",
            "sorcery",
        }
        if re.search(rf"\b{card_type}\b", normalized)
    }


def _is_aura(type_line: str) -> bool:
    return "enchantment" in type_line and re.search(r"\baura\b", type_line) is not None


def _mana_value_bucket(value) -> str:
    try:
        mana_value = max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        mana_value = 0
    return "6+" if mana_value >= 6 else str(mana_value)


def _sacrifice_traits(oracle_text: str, type_line: str) -> List[str]:
    traits = []
    outlet_patterns = [
        r"sacrifice (?:a|another|one|two|x) (?:artifact|creature|permanent|token)[^.:]*:",
        r"sacrifice (?:an|another) enchantment[^.:]*:",
    ]
    if any(re.search(pattern, oracle_text) for pattern in outlet_patterns):
        traits.append("outlet")
    if any(phrase in oracle_text for phrase in [
        "whenever you sacrifice",
        "whenever a creature you control dies",
        "whenever another creature dies",
        "whenever another creature you control dies",
        "whenever an artifact you control is put into a graveyard",
    ]):
        traits.append("payoff")
    creates_creature_tokens = (
        "create" in oracle_text
        and "creature token" in oracle_text
    )
    reusable_creature = (
        "creature" in type_line
        and any(phrase in oracle_text for phrase in [
            "return it to the battlefield",
            "return this card from your graveyard",
            "you may cast this card from your graveyard",
        ])
    )
    if creates_creature_tokens or reusable_creature:
        traits.append("fodder")
    return traits


def _package_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return key or "protected-package"


def _is_instant_or_sorcery(type_line: str) -> bool:
    return "instant" in type_line or "sorcery" in type_line


def _quantity(card: Mapping) -> int:
    try:
        return max(int(card.get("qty", 1)), 0)
    except (TypeError, ValueError):
        return 0


def _requirement_label(requirement: str, invariants: Mapping) -> str:
    if requirement == "spell_density":
        return "another instant or sorcery"
    if requirement.startswith("typal:"):
        return f"another {requirement.split(':', 1)[1].title()} card"
    if requirement == "aura_density":
        return "another Aura"
    if requirement.startswith("aura_mv:"):
        return f"an Aura at mana value {requirement.split(':', 1)[1]}"
    if requirement.startswith("card_type:"):
        return f"another {requirement.split(':', 1)[1].title()} card"
    if requirement.startswith("sacrifice:"):
        return f"another sacrifice {requirement.split(':', 1)[1]}"
    if requirement.startswith("package:"):
        return "the same declared package role"
    if requirement.startswith("tutor_target:"):
        return dependency_requirement_label(
            requirement,
            invariants.get("dependencies"),
        )
    return requirement.replace("_", " ")


def _append_reason(existing: str, note: str) -> str:
    if not existing:
        return note
    return f"{existing} {note}"
