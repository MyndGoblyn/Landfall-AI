"""Versioned competitive Commander evidence labels.

This registry is intentionally curated and conservative.  Low mana value alone
never creates competitive evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional


DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "competitive_card_labels.json"
)


class CompetitiveCardRegistry:
    def __init__(self, payload: Mapping):
        if int(payload.get("schema_version") or 0) != 1:
            raise ValueError("Unsupported competitive card registry schema")
        self.version = str(payload.get("version") or "unknown")
        self._cards = {
            str(row["name"]).strip().casefold(): dict(row)
            for row in payload.get("cards") or []
            if isinstance(row, Mapping) and row.get("name")
        }
        self._power_outliers = {
            str(name).strip().casefold()
            for name in payload.get("power_outliers") or []
            if str(name).strip()
        }

    @classmethod
    def load_default(cls) -> "CompetitiveCardRegistry":
        with DEFAULT_REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    def row(self, card_name: str) -> Optional[Dict]:
        value = self._cards.get(str(card_name or "").strip().casefold())
        return dict(value) if value else None

    def is_power_outlier(self, card_name: str) -> bool:
        return str(card_name or "").strip().casefold() in self._power_outliers

    def candidate_names(self) -> Iterable[str]:
        return tuple(row["name"] for row in self._cards.values())

    def count(self) -> int:
        return len(self._cards)

    def evidence(
        self,
        card_name: str,
        current_card_names: set[str],
        strategy_priorities: set[str],
    ) -> Optional[Dict]:
        row = self.row(card_name)
        if not row:
            return None
        required_any = {
            str(name).strip().casefold()
            for name in row.get("requires_any") or []
        }
        if required_any and not required_any.intersection(current_card_names):
            return None
        supported = set(row.get("strategies") or [])
        if supported and strategy_priorities and not supported.intersection(
            strategy_priorities
        ):
            return None
        return row

    def exact_name_query(self, color_filter: str) -> str:
        names = sorted(self.candidate_names(), key=str.casefold)
        exact = " OR ".join(f'!"{name}"' for name in names)
        return f"({exact}) {color_filter} f:commander"
