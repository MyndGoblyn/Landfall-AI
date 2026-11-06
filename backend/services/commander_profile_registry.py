"""Reviewed commander-specific evidence with exact identity matching."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Dict, List, Optional


class CommanderProfileRegistry:
    """Versioned human-reviewed commander strategy profiles."""

    DEFAULT_PATH = (
        Path(__file__).resolve().parents[1] / "data" / "commander_profiles.json"
    )
    ALLOWED_PLAYSTYLES = {"aggressive", "value", "control", "combo"}
    LIST_FIELDS = (
        "archetype_ids",
        "supported_synergies",
        "playstyles",
        "win_paths",
        "support_needs",
        "common_failure_modes",
        "anti_synergies",
        "evidence_sources",
    )

    def __init__(self, entries: List[Dict]):
        validated = [self._validate(entry) for entry in entries]
        oracle_ids = [entry["oracle_id"] for entry in validated]
        if len(oracle_ids) != len(set(oracle_ids)):
            raise ValueError("Commander profile oracle IDs must be unique")
        self.entries = validated
        self._by_oracle_id = {
            entry["oracle_id"].casefold(): entry for entry in validated
        }
        self._by_name = {entry["name"].casefold(): entry for entry in validated}

    @classmethod
    def load_default(cls) -> "CommanderProfileRegistry":
        if not cls.DEFAULT_PATH.exists():
            return cls([])
        return cls.from_path(cls.DEFAULT_PATH)

    @classmethod
    def from_path(cls, path: Path) -> "CommanderProfileRegistry":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("Commander profile registry must be a JSON array")
        return cls([entry for entry in data if isinstance(entry, dict)])

    @classmethod
    def _validate(cls, entry: Dict) -> Dict:
        normalized = copy.deepcopy(entry)
        for field in ("oracle_id", "name", "game_plan", "reviewed_at"):
            value = normalized.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Commander profile {field} is required")
            normalized[field] = value.strip()
        if normalized.get("review_status") != "reviewed":
            raise ValueError("Commander profiles must be explicitly reviewed")
        if normalized.get("confidence") not in {"high", "core"}:
            raise ValueError("Commander profile confidence must be high or core")
        for field in cls.LIST_FIELDS:
            values = normalized.get(field) or []
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ValueError(f"Commander profile {field} must contain strings")
            normalized[field] = list(dict.fromkeys(value.strip() for value in values))
        invalid_playstyles = (
            set(normalized["playstyles"]) - cls.ALLOWED_PLAYSTYLES
        )
        if invalid_playstyles:
            raise ValueError(
                "Unsupported commander playstyles: "
                + ", ".join(sorted(invalid_playstyles))
            )
        packages = normalized.get("packages") or []
        if not isinstance(packages, list):
            raise ValueError("Commander profile packages must be an array")
        for package in packages:
            if not isinstance(package, dict):
                raise ValueError("Commander profile packages must be objects")
            if not package.get("name") or not package.get("purpose"):
                raise ValueError("Commander profile packages require name and purpose")
        normalized["packages"] = packages
        similar_commanders = normalized.get("similar_commanders") or []
        if not isinstance(similar_commanders, list):
            raise ValueError("Commander profile similar commanders must be an array")
        for similar in similar_commanders:
            if not isinstance(similar, dict):
                raise ValueError("Commander profile similar commanders must be objects")
            if not isinstance(similar.get("name"), str) or not similar["name"].strip():
                raise ValueError("Similar commanders require a name")
            if not isinstance(similar.get("reason"), str) or not similar["reason"].strip():
                raise ValueError("Similar commanders require a reason")
        normalized["similar_commanders"] = similar_commanders
        return normalized

    def count(self) -> int:
        return len(self.entries)

    def get(self, oracle_id: str) -> Optional[Dict]:
        profile = self._by_oracle_id.get(str(oracle_id or "").casefold())
        return copy.deepcopy(profile) if profile else None

    def get_by_name(self, name: str) -> Optional[Dict]:
        profile = self._by_name.get(str(name or "").casefold())
        return copy.deepcopy(profile) if profile else None

    def match(self, card: Dict) -> Optional[Dict]:
        """Match only stable oracle identity; a similar name is not evidence."""
        return self.get(card.get("oracle_id"))

