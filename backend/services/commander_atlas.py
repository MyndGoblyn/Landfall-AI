"""Deterministic local-catalog browse and profile retrieval for commanders."""

from __future__ import annotations

import asyncio
import re
from typing import Dict, List, Optional


ARCHETYPE_FILTERS = (
    "artifact",
    "combat",
    "combo",
    "control",
    "enchantment",
    "graveyard",
    "lands",
    "spells",
    "stax",
    "tokens",
    "typal",
    "value",
    "voltron",
)
PLAYSTYLE_FILTERS = ("aggressive", "value", "control", "combo")


class CommanderAtlas:
    """Build a cacheable commander index from the verified local card catalog."""

    def __init__(self, candidate_provider, suggestion_engine):
        self.candidate_provider = candidate_provider
        self.engine = suggestion_engine
        self._lock = asyncio.Lock()
        self._identity = None
        self._entries: List[Dict] = []
        self._cards_by_oracle_id: Dict[str, Dict] = {}

    def _provider_identity(self):
        resolver = getattr(self.candidate_provider, "cache_identity", None)
        return resolver() if callable(resolver) else (type(self.candidate_provider).__name__,)

    def _catalog_status(self) -> Dict:
        resolver = getattr(self.candidate_provider, "get_status", None)
        status = resolver() if callable(resolver) else {}
        if status.get("type") == "fallback" and isinstance(status.get("primary"), dict):
            return status["primary"]
        return status

    def get_status(self) -> Dict:
        catalog = self._catalog_status()
        return {
            "index_state": "ready" if self._entries else "lazy",
            "commander_count": len(self._entries) if self._entries else None,
            "catalog_version": catalog.get("catalog_version"),
            "source_updated_at": catalog.get("source_updated_at"),
        }

    @staticmethod
    def _browse_synergies(card: Dict) -> List[str]:
        """Cheap catalog tags; full semantic detection runs only on opened profiles."""
        oracle_text = " ".join(
            str(value or "")
            for value in (
                card.get("oracle_text"),
                *(face.get("oracle_text") for face in card.get("card_faces") or []),
            )
        ).casefold()
        type_line = " ".join(
            str(value or "")
            for value in (
                card.get("type_line"),
                *(face.get("type_line") for face in card.get("card_faces") or []),
            )
        ).casefold()
        checks = (
            ("artifact", ("artifact", "equipment")),
            ("enchantment", ("enchantment", "aura", "enchanted")),
            ("graveyard", ("graveyard", "mill ", " dies", "reanimate")),
            ("sacrifice", ("sacrifice", " dies")),
            ("tokens", ("create a ", "create two ", "create that many", "populate")),
            ("counters", ("+1/+1 counter", "proliferate", "counter on")),
            ("lifegain", ("gain life", "gains life", "you gained life")),
            ("landfall", ("landfall", "land enters", "additional land")),
            ("instant_sorcery", ("instant or sorcery", "noncreature spell", "magecraft")),
            ("blink", ("exile it, then return", "return it to the battlefield")),
            ("voltron", ("equipped creature", "enchanted creature", "attach")),
            ("combat_damage", ("combat damage to a player", "combat damage to one or more")),
            ("attack_triggers", ("whenever you attack", "whenever this creature attacks", "whenever one or more creatures attack")),
            ("extra_combat", ("additional combat phase", "extra combat phase")),
            ("donation", ("gains control of target permanent", "exchange control")),
            ("target_spells", ("instant or sorcery spell that targets", "whenever you cast a spell that targets")),
        )
        synergies = [
            synergy for synergy, markers in checks
            if any(marker in oracle_text for marker in markers)
        ]
        if (
            "choose a creature type" in oracle_text
            or "kindred" in type_line
            or re.search(r"\b(other|each|all) [a-z]+s? you control\b", oracle_text)
        ):
            synergies.append("typal")
        if "creature" in type_line and any(marker in oracle_text for marker in (
            "creatures you control",
            "another creature",
            "creature card",
        )):
            synergies.append("creature")
        return list(dict.fromkeys(synergies))

    @staticmethod
    def _archetype_families(card: Dict, synergies: set) -> set:
        mapping = {
            "artifact": "artifact",
            "artifact_tokens": "artifact",
            "combat_damage": "combat",
            "attack_triggers": "combat",
            "extra_combat": "combat",
            "goad": "combat",
            "target_spells": "combo",
            "temporary_drawback": "combo",
            "donation": "control",
            "flash_control": "control",
            "hand_size_pressure": "control",
            "control_finisher": "control",
            "enchantment": "enchantment",
            "graveyard": "graveyard",
            "sacrifice": "graveyard",
            "landfall": "lands",
            "instant_sorcery": "spells",
            "tokens": "tokens",
            "typal": "typal",
            "counters": "value",
            "lifegain": "value",
            "blink": "value",
            "creature": "value",
            "topdeck_value": "value",
            "voltron": "voltron",
        }
        families = {
            mapping[synergy] for synergy in synergies if synergy in mapping
        }
        oracle_text = " ".join(
            str(value or "")
            for value in (
                card.get("oracle_text"),
                *(face.get("oracle_text") for face in card.get("card_faces") or []),
            )
        ).casefold()
        if any(marker in oracle_text for marker in (
            "players can't",
            "player can't",
            "spells cost ",
            "don't untap",
            "doesn't untap",
        )):
            families.add("stax")
        return families

    @staticmethod
    def _playstyles(archetype_families: set, synergies: set) -> List[str]:
        playstyles = set()
        if archetype_families & {"combat", "tokens", "typal", "voltron"} or synergies & {
            "attack_triggers", "combat_damage", "extra_combat", "tokens", "typal", "voltron",
        }:
            playstyles.add("aggressive")
        if archetype_families & {"value", "artifact", "enchantment", "graveyard", "lands"} or synergies & {
            "artifact", "enchantment", "graveyard", "landfall", "lifegain", "counters", "blink",
        }:
            playstyles.add("value")
        if archetype_families & {"control", "stax"} or synergies & {
            "flash_control", "hand_size_pressure", "donation", "goad",
        }:
            playstyles.add("control")
        if archetype_families & {"combo"} or synergies & {
            "target_spells", "extra_combat", "temporary_drawback",
        }:
            playstyles.add("combo")
        return sorted(playstyles)

    async def _ensure_index(self) -> None:
        identity = self._provider_identity()
        if self._entries and identity == self._identity:
            return
        async with self._lock:
            identity = self._provider_identity()
            if self._entries and identity == self._identity:
                return
            cards = await self.candidate_provider.search_cards(
                "is:commander f:commander",
                6000,
            )
            entries = []
            cards_by_oracle_id = {}
            for card in cards:
                if not self.engine._is_commander_eligible(card):
                    continue
                oracle_id = str(card.get("oracle_id") or "").strip()
                name = str(card.get("name") or "").strip()
                if not oracle_id or not name:
                    continue
                synergies = self._browse_synergies(card)
                reviewed_profile = self.engine.commander_profile_registry.match(card)
                if reviewed_profile:
                    synergies = list(dict.fromkeys([
                        *synergies,
                        *reviewed_profile.get("supported_synergies", []),
                    ]))
                archetype_families = self._archetype_families(
                    card,
                    set(synergies),
                )
                archetype_ids = set()
                if reviewed_profile:
                    archetype_ids.update(reviewed_profile.get("archetype_ids", []))
                    for archetype_id in reviewed_profile.get("archetype_ids", []):
                        definition = self.engine.archetype_registry.get(archetype_id) or {}
                        family = definition.get("archetype_family")
                        if family:
                            archetype_families.add(family)
                playstyles = (
                    set(reviewed_profile.get("playstyles", []))
                    if reviewed_profile
                    else set(self._playstyles(archetype_families, set(synergies)))
                )
                images = self.engine._get_card_images(card)
                entry = {
                    "oracle_id": oracle_id,
                    "name": name,
                    "type_line": card.get("type_line"),
                    "cmc": card.get("cmc", 0),
                    "color_identity": card.get("color_identity") or [],
                    "image_url": images["front"],
                    "image_url_back": images["back"],
                    "synergies": synergies[:6],
                    "archetype_ids": sorted(archetype_ids),
                    "archetype_families": sorted(archetype_families),
                    "playstyles": sorted(playstyles),
                    "profile_status": "reviewed" if reviewed_profile else (
                        "supported" if synergies else "exploratory"
                    ),
                }
                entries.append(entry)
                cards_by_oracle_id[oracle_id.casefold()] = card
            entries.sort(key=lambda item: item["name"].casefold())
            self._entries = entries
            self._cards_by_oracle_id = cards_by_oracle_id
            self._identity = identity

    @staticmethod
    def _query_rank(name: str, query: str) -> tuple:
        normalized_name = name.casefold()
        normalized_query = " ".join(query.casefold().split())
        if not normalized_query:
            return (0, normalized_name)
        if normalized_name == normalized_query:
            return (0, normalized_name)
        if normalized_name.startswith(normalized_query):
            return (1, normalized_name)
        name_words = re.findall(r"[a-z0-9]+", normalized_name)
        query_tokens = re.findall(r"[a-z0-9]+", normalized_query)
        if query_tokens and all(
            any(word.startswith(token) for word in name_words)
            for token in query_tokens
        ):
            return (2, normalized_name)
        return (3, normalized_name)

    async def search(
        self,
        *,
        query: str = "",
        colors: str = "",
        color_mode: str = "exact",
        max_cmc: Optional[int] = None,
        archetype: str = "",
        playstyle: str = "",
        page: int = 1,
        page_size: int = 24,
    ) -> Dict:
        await self._ensure_index()
        normalized_query = " ".join(query.casefold().split())
        colorless = "C" in colors.upper()
        selected_colors = {char for char in colors.upper() if char in "WUBRG"}
        archetype = archetype.casefold().strip()
        playstyle = playstyle.casefold().strip()
        rows = []
        for entry in self._entries:
            if normalized_query and normalized_query not in entry["name"].casefold():
                query_tokens = re.findall(r"[a-z0-9]+", normalized_query)
                name_words = re.findall(r"[a-z0-9]+", entry["name"].casefold())
                if not query_tokens or not all(
                    any(word.startswith(token) for word in name_words)
                    for token in query_tokens
                ):
                    continue
            identity = {str(color).upper() for color in entry["color_identity"]}
            if colorless:
                if identity:
                    continue
            elif selected_colors:
                if color_mode == "exact" and identity != selected_colors:
                    continue
                if color_mode == "inclusive" and not selected_colors.issubset(identity):
                    continue
            if max_cmc is not None and float(entry.get("cmc") or 0) > max_cmc:
                continue
            if archetype and archetype not in {
                *entry["archetype_ids"],
                *entry["archetype_families"],
                *entry["synergies"],
            }:
                continue
            if playstyle and playstyle not in entry["playstyles"]:
                continue
            rows.append(entry)
        rows.sort(key=lambda item: self._query_rank(item["name"], normalized_query))
        total = len(rows)
        start = (page - 1) * page_size
        status = self._catalog_status()
        return {
            "commanders": rows[start:start + page_size],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "catalog": {
                "catalog_version": status.get("catalog_version"),
                "source_updated_at": status.get("source_updated_at"),
                "commander_count": len(self._entries),
            },
            "filters": {
                "archetypes": list(ARCHETYPE_FILTERS),
                "playstyles": list(PLAYSTYLE_FILTERS),
            },
        }

    async def get(self, oracle_id: str) -> Optional[Dict]:
        await self._ensure_index()
        card = self._cards_by_oracle_id.get(str(oracle_id or "").casefold())
        if card is None:
            return None
        entry = next(
            (
                row for row in self._entries
                if row["oracle_id"].casefold() == str(oracle_id).casefold()
            ),
            None,
        )
        return {"card": card, "catalog_entry": entry}

