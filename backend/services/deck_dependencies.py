"""Deterministic card-dependency discovery from explicit oracle text.

This module intentionally does not infer combo lines.  It recognizes only
typed library searches and exact named-card references that can be verified
against card data already available to the analysis engine.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Mapping, Optional, Sequence


SUPPORTED_CARD_TYPES = {
    "artifact",
    "battle",
    "creature",
    "enchantment",
    "instant",
    "kindred",
    "planeswalker",
    "sorcery",
}
COLOR_QUALIFIERS = {
    "white",
    "blue",
    "black",
    "red",
    "green",
    "colorless",
    "multicolored",
    "monocolored",
}
PERMANENT_TYPES = {
    "artifact",
    "battle",
    "creature",
    "enchantment",
    "planeswalker",
}
GENERIC_DESCRIPTOR_WORDS = {
    "a",
    "an",
    "any",
    "card",
    "cards",
    "colorless",
    "converted",
    "different",
    "each",
    "exactly",
    "historic",
    "legendary",
    "less",
    "mana",
    "nonland",
    "number",
    "one",
    "or",
    "permanent",
    "snow",
    "three",
    "two",
    "up",
    "value",
    "with",
}


def build_dependency_graph(cards: Sequence[Mapping]) -> Dict:
    """Build typed-tutor packages and exact named-card links for a deck."""
    normalized_cards = [card for card in cards if str(card.get("name") or "").strip()]
    present_names = {
        _name_key(card.get("name")): str(card.get("name") or "").strip()
        for card in normalized_cards
    }
    deck_subtypes = _known_creature_subtypes(normalized_cards)
    grouped_specs = defaultdict(list)

    for card in normalized_cards:
        source_name = str(card.get("name") or "").strip()
        for specification in _typed_tutor_specifications(card, deck_subtypes):
            grouped_specs[specification["key"]].append((source_name, specification))

    tutor_packages = []
    for key in sorted(grouped_specs):
        sources_and_specs = grouped_specs[key]
        source_names = list(dict.fromkeys(source for source, _ in sources_and_specs))
        specification = sources_and_specs[0][1]
        source_keys = {_name_key(source) for source in source_names}
        targets = [
            str(card.get("name") or "").strip()
            for card in normalized_cards
            if (
                _name_key(card.get("name")) not in source_keys
                or len(source_keys) > 1
            )
            and card_matches_tutor_specification(card, specification)
        ]
        target_names = list(dict.fromkeys(targets))
        target_count = len(target_names)
        status = "dead" if target_count == 0 else "fragile" if target_count <= 2 else "healthy"
        tutor_packages.append({
            "key": key,
            "label": specification["label"],
            "source_cards": source_names,
            "target_types": specification["target_types"],
            "required_subtype": specification.get("required_subtype"),
            "required_supertypes": specification.get("required_supertypes", []),
            "max_mana_value": specification.get("max_mana_value"),
            "target_cards": target_names,
            "target_count": target_count,
            "status": status,
        })

    named_links = []
    seen_links = set()
    for card in normalized_cards:
        source_name = str(card.get("name") or "").strip()
        for relation, target_name in _named_references(card):
            if _name_key(target_name) == _name_key(source_name):
                continue
            link_key = (relation, _name_key(source_name), _name_key(target_name))
            if link_key in seen_links:
                continue
            seen_links.add(link_key)
            canonical_target = present_names.get(_name_key(target_name), target_name)
            named_links.append({
                "key": _stable_key(
                    f"{relation}-{source_name}-{canonical_target}"
                ),
                "relation": relation,
                "source_card": source_name,
                "target_card": canonical_target,
                "present": _name_key(target_name) in present_names,
                "status": (
                    "complete" if _name_key(target_name) in present_names else "missing"
                ),
            })

    protected_card_keys = set()
    for link in named_links:
        protected_card_keys.add(_name_key(link["source_card"]))
        if link["present"]:
            protected_card_keys.add(_name_key(link["target_card"]))

    warnings = []
    for package in tutor_packages:
        if package["status"] == "dead":
            warnings.append(
                f"{', '.join(package['source_cards'])} has no in-deck target for "
                f"{package['label']}."
            )
        elif package["status"] == "fragile":
            warnings.append(
                f"{', '.join(package['source_cards'])} has only "
                f"{package['target_count']} in-deck target(s) for {package['label']}."
            )
    for link in named_links:
        if not link["present"]:
            warnings.append(
                f"{link['source_card']} explicitly references missing card "
                f"{link['target_card']}."
            )

    active = bool(tutor_packages or named_links)
    return {
        "active": active,
        "tutor_packages": tutor_packages,
        "named_links": named_links,
        "protected_card_keys": sorted(protected_card_keys),
        "warnings": warnings,
        "limitations": (
            "Deterministic only: recognizes explicit typed library searches and "
            "exact named-card text; it does not infer combos or strategic dependencies."
        ),
    }


def dependency_traits(card: Mapping, graph: Optional[Mapping]) -> List[str]:
    """Return graph traits supplied by a candidate or existing deck card."""
    if not graph or not graph.get("active"):
        return []
    traits = []
    for package in graph.get("tutor_packages") or []:
        if card_matches_tutor_specification(card, package):
            traits.append(f"tutor_target:{package['key']}")
    card_name = _name_key(card.get("name"))
    for link in graph.get("named_links") or []:
        if card_name == _name_key(link.get("target_card")):
            traits.append(f"named_dependency:{link['key']}")
    return list(dict.fromkeys(traits))


def dependency_cut_requirements(card: Mapping, graph: Optional[Mapping]) -> List[str]:
    """Require like-for-like targets when a cut would leave a tutor fragile/dead."""
    if not graph or not graph.get("active"):
        return []
    card_name = _name_key(card.get("name"))
    requirements = []
    for package in graph.get("tutor_packages") or []:
        target_keys = {_name_key(name) for name in package.get("target_cards") or []}
        if card_name in target_keys and int(package.get("target_count") or 0) <= 2:
            requirements.append(f"tutor_target:{package['key']}")
    return list(dict.fromkeys(requirements))


def is_dependency_cut_forbidden(card_name: str, graph: Optional[Mapping]) -> bool:
    """Protect cards participating in an explicit, non-substitutable named link."""
    protected = set((graph or {}).get("protected_card_keys") or [])
    return _name_key(card_name) in protected


def dependency_requirement_label(requirement: str, graph: Optional[Mapping]) -> str:
    if requirement.startswith("tutor_target:"):
        key = requirement.split(":", 1)[1]
        package = next(
            (
                item
                for item in (graph or {}).get("tutor_packages") or []
                if item.get("key") == key
            ),
            None,
        )
        if package:
            return f"another target for {package['label']}"
        return "another valid tutor target"
    return requirement.replace("_", " ")


def card_matches_tutor_specification(card: Mapping, specification: Mapping) -> bool:
    type_line = str(card.get("type_line") or "").casefold()
    target_types = set(specification.get("target_types") or [])
    if target_types and not any(
        re.search(rf"\b{re.escape(card_type)}\b", type_line)
        for card_type in target_types
    ):
        return False

    required_subtype = str(specification.get("required_subtype") or "").casefold()
    if required_subtype and not re.search(
        rf"\b{re.escape(required_subtype)}\b", type_line
    ):
        return False

    required_supertypes = specification.get("required_supertypes") or []
    if any(
        not re.search(rf"\b{re.escape(supertype)}\b", type_line)
        for supertype in required_supertypes
    ):
        return False

    max_mana_value = specification.get("max_mana_value")
    if max_mana_value is not None:
        try:
            if float(card.get("cmc", 0) or 0) > float(max_mana_value):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _typed_tutor_specifications(
    card: Mapping,
    deck_subtypes: set[str],
) -> List[Dict]:
    oracle_text = str(card.get("oracle_text") or "")
    clauses = re.findall(
        r"search your library\b[^.]*\.",
        oracle_text,
        flags=re.IGNORECASE,
    )
    results = []
    for clause in clauses:
        clause_normalized = clause.casefold()
        if "card named" in clause_normalized or "cards named" in clause_normalized:
            continue
        if re.search(r"\bcards?\b.*\bor\b.*\bcards?\b", clause_normalized):
            continue
        descriptor_match = re.search(
            r"\bfor\s+(?:up to\s+)?(?:any number of\s+|one\s+|two\s+|three\s+)?"
            r"(?:an?\s+)?(.{1,140}?)\s+cards?\b",
            clause,
            flags=re.IGNORECASE,
        )
        if not descriptor_match:
            continue
        descriptor = descriptor_match.group(1).strip()
        normalized = descriptor.casefold()
        if re.search(r"\bland\b", normalized):
            continue
        if any(
            re.search(rf"\b{qualifier}\b", normalized)
            for qualifier in COLOR_QUALIFIERS
        ):
            continue
        if "historic" in normalized:
            continue

        target_types = sorted(
            card_type
            for card_type in SUPPORTED_CARD_TYPES
            if re.search(rf"\b{card_type}\b", normalized)
        )
        required_subtype = None
        if re.search(r"\baura\b", normalized):
            target_types = ["enchantment"]
            required_subtype = "aura"
        elif re.search(r"\bequipment\b", normalized):
            target_types = ["artifact"]
            required_subtype = "equipment"
        elif "nonland permanent" in normalized and not target_types:
            target_types = sorted(PERMANENT_TYPES)

        if not target_types:
            descriptor_words = {
                word.casefold()
                for word in re.findall(r"[A-Za-z][A-Za-z'-]+", descriptor)
            }
            subtype_matches = sorted(
                word for word in descriptor_words
                if word in deck_subtypes and word not in GENERIC_DESCRIPTOR_WORDS
            )
            if len(subtype_matches) == 1:
                target_types = ["creature"]
                required_subtype = subtype_matches[0]
        if not target_types:
            continue

        mana_value_match = re.search(
            r"(?:mana value|converted mana cost)\s+(\d+)\s+or less",
            clause,
            flags=re.IGNORECASE,
        )
        max_mana_value = (
            int(mana_value_match.group(1)) if mana_value_match else None
        )
        has_mana_value_restriction = bool(re.search(
            r"(?:mana value|converted mana cost)",
            clause,
            flags=re.IGNORECASE,
        ))
        if has_mana_value_restriction and max_mana_value is None:
            continue
        if re.search(
            r"\bcards?\s+(?:with|whose|that has)\b",
            clause,
            flags=re.IGNORECASE,
        ) and not mana_value_match:
            continue
        required_supertypes = [
            supertype
            for supertype in ("legendary", "snow")
            if re.search(rf"\b{supertype}\b", normalized)
        ]
        key_parts = ["-or-".join(target_types)]
        if required_subtype:
            key_parts.append(required_subtype)
        key_parts.extend(required_supertypes)
        if max_mana_value is not None:
            key_parts.append(f"mv-le-{max_mana_value}")
        key = _stable_key("-".join(key_parts))
        results.append({
            "key": key,
            "label": _tutor_label(
                target_types,
                required_subtype,
                required_supertypes,
                max_mana_value,
            ),
            "target_types": target_types,
            "required_subtype": required_subtype,
            "required_supertypes": required_supertypes,
            "max_mana_value": max_mana_value,
        })
    return results


def _named_references(card: Mapping) -> List[tuple[str, str]]:
    oracle_text = str(card.get("oracle_text") or "")
    references = []
    patterns = [
        ("partner_with", r"\bpartner with\s+([^\n.(]+)"),
        ("melds_with", r"\bmelds with\s+([^\n.(]+)"),
        (
            "named_card",
            r"\bcards? named\s+([^\n.]+?)"
            r"(?=,\s+(?:reveal|put|create|exile|return|then|shuffle|you\b)"
            r"|\s+and\s+(?:reveal|put|create|exile|return)\b"
            r"|\s+(?:from|in|onto|to)\b|[.;]|$)",
        ),
    ]
    for relation, pattern in patterns:
        for match in re.finditer(pattern, oracle_text, flags=re.IGNORECASE):
            target_name = match.group(1).strip(" \"'.,")
            if target_name:
                references.append((relation, target_name))
    return references


def _known_creature_subtypes(cards: Sequence[Mapping]) -> set[str]:
    subtypes = set()
    for card in cards:
        type_line = str(card.get("type_line") or "")
        parts = re.split(r"\s+[—–-]\s+", type_line, maxsplit=1)
        if len(parts) < 2 or "creature" not in parts[0].casefold():
            continue
        subtypes.update(
            token.casefold()
            for token in re.findall(r"[A-Za-z][A-Za-z'-]+", parts[1])
        )
    return subtypes


def _tutor_label(
    target_types: List[str],
    required_subtype: Optional[str],
    required_supertypes: List[str],
    max_mana_value: Optional[int],
) -> str:
    if required_subtype:
        label = f"{required_subtype.title()} card"
    else:
        label = " or ".join(card_type.title() for card_type in target_types) + " card"
    if required_supertypes:
        label = " ".join(value.title() for value in required_supertypes) + " " + label
    if max_mana_value is not None:
        label += f" with mana value {max_mana_value} or less"
    return label


def _name_key(value) -> str:
    return str(value or "").strip().casefold()


def _stable_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "dependency"
