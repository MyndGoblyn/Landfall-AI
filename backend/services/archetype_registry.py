import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


@dataclass(frozen=True)
class ArchetypeMatch:
    """A scored composite strategy match from reusable semantic signals."""

    id: str
    name: str
    summary: str
    archetype_family: str
    confidence_floor: str
    confidence: str
    score: int
    matched_required: List[str]
    matched_supporting: List[str]
    matched_rejects: List[str]
    primary_needs: List[str]
    secondary_needs: List[str]
    recommendation_focus: List[str]
    avoid_recommendations: List[str]
    pilot_note_guidance: List[str]
    reason_builder_guidance: List[str]
    false_positive_notes: str

    def as_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "archetype_family": self.archetype_family,
            "confidence_floor": self.confidence_floor,
            "confidence": self.confidence,
            "score": self.score,
            "matched_required": self.matched_required,
            "matched_supporting": self.matched_supporting,
            "matched_rejects": self.matched_rejects,
            "primary_needs": self.primary_needs,
            "secondary_needs": self.secondary_needs,
            "recommendation_focus": self.recommendation_focus,
            "avoid_recommendations": self.avoid_recommendations,
            "pilot_note_guidance": self.pilot_note_guidance,
            "reason_builder_guidance": self.reason_builder_guidance,
            "false_positive_notes": self.false_positive_notes,
        }


class ArchetypeRegistry:
    """In-memory semantic layer for composite Commander archetypes."""

    DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "archetype_signal_registry.json"

    MIN_SCORE_BY_FLOOR = {
        "low": 5,
        "medium": 8,
        "high": 10,
    }

    FLOOR_BONUS = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }

    def __init__(self, entries: List[Dict]):
        self.entries = entries
        self._by_id = {
            entry.get("id"): entry
            for entry in entries
            if isinstance(entry.get("id"), str) and entry.get("id")
        }

    @classmethod
    def load_default(cls) -> "ArchetypeRegistry":
        if not cls.DEFAULT_PATH.exists():
            return cls([])
        return cls.from_path(cls.DEFAULT_PATH)

    @classmethod
    def from_path(cls, path: Path) -> "ArchetypeRegistry":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("Archetype registry must be a JSON array.")
        return cls([entry for entry in data if isinstance(entry, dict)])

    def count(self) -> int:
        return len(self.entries)

    def get(self, archetype_id: str) -> Optional[Dict]:
        return self._by_id.get(archetype_id)

    @staticmethod
    def _list(entry: Dict, field: str) -> List[str]:
        value = entry.get(field) or []
        return [item for item in value if isinstance(item, str) and item]

    def _confidence_for_score(self, score: int, floor: str, supporting_count: int) -> str:
        if score >= 18 and supporting_count >= 2:
            return "core"
        if score >= 14:
            return "high"
        if score >= self.MIN_SCORE_BY_FLOOR.get(floor, 8):
            return floor if floor in {"low", "medium", "high"} else "medium"
        return "low"

    def detect_archetypes(self, signals: Iterable[str], limit: int = 5) -> List[ArchetypeMatch]:
        """Score archetypes from generic signal names and reject false-positive patterns."""
        signal_set: Set[str] = {signal for signal in signals if signal}
        matches: List[ArchetypeMatch] = []

        for entry in self.entries:
            required = self._list(entry, "required_signals")
            if not required:
                continue

            matched_required = [signal for signal in required if signal in signal_set]
            missing_required = [signal for signal in required if signal not in signal_set]
            if missing_required:
                continue

            supporting = self._list(entry, "supporting_signals")
            rejects = self._list(entry, "reject_signals")
            matched_supporting = [signal for signal in supporting if signal in signal_set]
            matched_rejects = [signal for signal in rejects if signal in signal_set]
            confidence_floor = entry.get("confidence_floor", "medium")

            if matched_rejects:
                continue

            score = (
                len(matched_required) * 6 +
                len(matched_supporting) * 2 +
                self.FLOOR_BONUS.get(confidence_floor, 1) -
                len(matched_rejects) * 5
            )

            if score < self.MIN_SCORE_BY_FLOOR.get(confidence_floor, 8):
                continue

            matches.append(ArchetypeMatch(
                id=entry.get("id", ""),
                name=entry.get("name", ""),
                summary=entry.get("summary", ""),
                archetype_family=entry.get("archetype_family", ""),
                confidence_floor=confidence_floor,
                confidence=self._confidence_for_score(score, confidence_floor, len(matched_supporting)),
                score=score,
                matched_required=matched_required,
                matched_supporting=matched_supporting,
                matched_rejects=matched_rejects,
                primary_needs=self._list(entry, "primary_needs"),
                secondary_needs=self._list(entry, "secondary_needs"),
                recommendation_focus=self._list(entry, "recommendation_focus"),
                avoid_recommendations=self._list(entry, "avoid_recommendations"),
                pilot_note_guidance=self._list(entry, "pilot_note_guidance"),
                reason_builder_guidance=self._list(entry, "reason_builder_guidance"),
                false_positive_notes=entry.get("false_positive_notes", ""),
            ))

        matches.sort(key=lambda match: (
            -match.score,
            match.confidence != "core",
            match.confidence_floor != "high",
            match.name,
        ))
        return matches[:limit]
