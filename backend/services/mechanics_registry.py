import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


@dataclass(frozen=True)
class MechanicSignal:
    """A normalized, scored mechanics-registry match."""

    name: str
    theme_family: str
    subthemes: List[str]
    evidence_strength: str
    risk_level: str
    can_define_deck: bool
    support_only: bool
    deck_roles: List[str]
    reason_language: str
    strategy_language: str
    scryfall_query_terms: List[str]
    matched_patterns: List[str]
    requirements_met: bool
    score: int

    def as_dict(self) -> Dict:
        return {
            "name": self.name,
            "theme_family": self.theme_family,
            "subthemes": self.subthemes,
            "evidence_strength": self.evidence_strength,
            "risk_level": self.risk_level,
            "can_define_deck": self.can_define_deck,
            "support_only": self.support_only,
            "deck_roles": self.deck_roles,
            "reason_language": self.reason_language,
            "strategy_language": self.strategy_language,
            "scryfall_query_terms": self.scryfall_query_terms,
            "matched_patterns": self.matched_patterns,
            "requirements_met": self.requirements_met,
            "score": self.score,
        }


class MechanicsRegistry:
    """Small in-memory evidence layer for deterministic MTG mechanic detection."""

    DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "mechanics_registry.json"

    EVIDENCE_WEIGHTS = {
        "core": 5,
        "support": 3,
        "texture": 1,
        "reject": -6,
    }

    RISK_PENALTIES = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }

    REQUIREMENT_PATTERNS = {
        "combat damage payoff": [
            "combat damage to a player",
            "combat damage to one or more players",
            "deals damage to a player",
            "deals combat damage",
        ],
        "attack trigger": [
            "whenever this creature attacks",
            "whenever it attacks",
            "whenever you attack",
            "whenever one or more creatures attack",
            "attacks,",
        ],
        "evasive creature payoff": [
            "creature with flying",
            "creatures with flying",
            "can't be blocked",
            "unblocked",
        ],
        "counter placement": [
            "+1/+1 counter",
            "-1/-1 counter",
            "counter on",
            "put a counter",
            "gets a counter",
        ],
        "counter payoff": [
            "for each counter",
            "with counters",
            "proliferate",
            "remove a counter",
        ],
        "artifact payoff": [
            "artifact you control",
            "whenever an artifact",
            "sacrifice an artifact",
            "artifacts you control",
        ],
        "sacrifice payoff": [
            "whenever you sacrifice",
            "whenever a creature dies",
            "whenever another creature dies",
            "dies",
        ],
        "mana sink": [
            "pay ",
            "activated ability",
            "{x}",
            "x spell",
        ],
        "self-mill or discard outlets": [
            "mill",
            "discard",
            "surveil",
            "put into your graveyard",
        ],
        "big creature targets": [
            "creature card from your graveyard",
            "return target creature",
            "put target creature",
        ],
        "high instant/sorcery density": [
            "instant or sorcery",
            "instant and sorcery",
            "noncreature spell",
        ],
        "cheap targeting spells": [
            "target creature you control",
            "target this creature",
            "becomes the target",
        ],
        "auras": [
            "aura",
            "enchant creature",
            "enchanted creature",
        ],
        "single creature focus": [
            "equipped creature",
            "enchanted creature",
            "commander damage",
        ],
        "extra land drops": [
            "additional land",
            "play lands",
            "land enters",
            "landfall",
        ],
        "fetch land density": [
            "search your library for a land",
            "land card",
            "sacrifice",
        ],
        "ETB creatures with strong triggers": [
            "enters the battlefield",
            "when this creature enters",
            "when it enters",
        ],
        "repeatable blink": [
            "exile",
            "return it to the battlefield",
            "return that card to the battlefield",
        ],
        "protection for the creature being enchanted": [
            "hexproof",
            "ward",
            "indestructible",
            "totem armor",
            "umbra armor",
        ],
        "voltron-friendly commander": [
            "combat damage",
            "commander damage",
            "attacks",
            "equipped",
            "enchanted",
        ],
        "auras/equipment density": [
            "aura",
            "equipment",
            "equip",
            "attach",
        ],
        "protection (hexproof, totem armor)": [
            "hexproof",
            "ward",
            "totem armor",
            "umbra armor",
            "indestructible",
        ],
        "evasion": [
            "flying",
            "trample",
            "menace",
            "can't be blocked",
        ],
    }

    FAMILY_SYNERGY_MAP = {
        "artifact_tokens": {"artifact_tokens"},
        "artifacts": {"artifact"},
        "blink": {"blink"},
        "counters": {"counters"},
        "creatures": {"creature"},
        "enchantments": {"enchantment"},
        "exile": {"exile"},
        "graveyard": {"graveyard"},
        "lands": {"landfall"},
        "lifegain": {"lifegain"},
        "sacrifice": {"sacrifice"},
        "spells": {"instant_sorcery"},
        "tokens": {"tokens"},
        "typal": {"creature"},
        "voltron": {"voltron"},
    }

    NAME_SYNERGY_MAP = {
        "Auras": {"enchantment", "voltron"},
        "Equipment": {"artifact", "voltron"},
        "Vehicles": {"artifact"},
        "Sagas": {"enchantment"},
        "Backgrounds": {"enchantment"},
        "Rooms": {"enchantment"},
        "Classes": {"enchantment"},
        "Constellation": {"enchantment"},
        "Eerie": {"enchantment"},
        "Cases": {"enchantment"},
        "Reanimator": {"graveyard"},
        "Aristocrats": {"sacrifice"},
        "Spellslinger": {"instant_sorcery"},
        "Voltron": {"voltron"},
        "Goad": {"goad", "combat_damage"},
        "Extra Combats": {"extra_combat", "attack_triggers"},
        "Spell Copy": {"instant_sorcery"},
        "Lifegain": {"lifegain"},
        "Landfall": {"landfall"},
        "Blink": {"blink"},
        "Treasure": {"artifact_tokens"},
        "Food": {"artifact_tokens"},
        "Clue": {"artifact_tokens"},
        "Blood": {"artifact_tokens"},
        "Powerstone": {"artifact_tokens"},
        "Map": {"artifact_tokens"},
        "Gold": {"artifact_tokens"},
        "Servo": {"artifact_tokens", "tokens"},
        "Thopter": {"artifact_tokens", "tokens"},
        "Investigate": {"artifact_tokens"},
        "Fabricate": {"artifact_tokens", "tokens"},
        "Incubate": {"artifact_tokens"},
        "Populate": {"tokens"},
        "Myriad": {"tokens"},
        "Offspring": {"tokens"},
        "Squad": {"tokens"},
        "Typal": {"creature"},
    }

    VOLTRON_SUBTHEMES = {
        "voltron",
        "voltron_engine",
        "commander_damage",
        "single_threat",
        "auras_equipment",
        "evasion",
        "damage_through",
    }

    def __init__(self, entries: List[Dict]):
        self.entries = entries
        self._by_term = self._build_term_index(entries)

    @classmethod
    def load_default(cls) -> "MechanicsRegistry":
        if not cls.DEFAULT_PATH.exists():
            return cls([])
        return cls.from_path(cls.DEFAULT_PATH)

    @classmethod
    def from_path(cls, path: Path) -> "MechanicsRegistry":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("Mechanics registry must be a JSON array.")
        return cls([entry for entry in data if isinstance(entry, dict)])

    @staticmethod
    def normalize_text(value: Optional[str]) -> str:
        value = value or ""
        value = value.replace("\u2019", "'").replace("\u2014", " ")
        value = re.sub(r"\s+", " ", value)
        return value.strip().lower()

    @classmethod
    def _build_term_index(cls, entries: List[Dict]) -> Dict[str, Dict]:
        index = {}
        for entry in entries:
            terms = [entry.get("name", ""), *(entry.get("aliases") or [])]
            for term in terms:
                normalized = cls.normalize_text(term)
                if normalized:
                    index[normalized] = entry
        return index

    def count(self) -> int:
        return len(self.entries)

    def _pattern_matches(self, pattern: str, haystack: str, type_line: str) -> bool:
        normalized = self.normalize_text(pattern)
        if not normalized:
            return False

        if normalized in {"tap", "add", "draw", "search", "exile"}:
            return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None

        if re.fullmatch(r"[a-z][a-z'-]*", normalized):
            return re.search(rf"\b{re.escape(normalized)}\b", haystack) is not None

        if normalized in type_line:
            return True

        if re.search(r"[a-z0-9][\w' +/-]*[a-z0-9]", normalized):
            return normalized in haystack

        return False

    def _requirements_met(self, requires: Iterable[str], context: str) -> bool:
        requirements = [self.normalize_text(requirement) for requirement in requires if requirement]
        if not requirements:
            return True

        for requirement in requirements:
            if requirement in context:
                return True
            for pattern in self.REQUIREMENT_PATTERNS.get(requirement, []):
                if self.normalize_text(pattern) in context:
                    return True
        return False

    def _score_entry(self, entry: Dict, matched_patterns: List[str], requirements_met: bool) -> int:
        evidence = entry.get("evidence_strength", "texture")
        risk = entry.get("risk_level", "medium")
        score = self.EVIDENCE_WEIGHTS.get(evidence, 1)
        if entry.get("can_define_deck"):
            score += 1
        if entry.get("support_only"):
            score -= 1
        if not requirements_met:
            score -= self.RISK_PENALTIES.get(risk, 1)
        if len(matched_patterns) > 1:
            score += 1
        return score

    def detect_signals(
        self,
        oracle_text: str,
        type_line: str = "",
        context_text: Optional[str] = None,
        include_texture: bool = True,
        include_rejects: bool = False,
    ) -> List[MechanicSignal]:
        """Return scored mechanics that match card text and survive basic risk gates."""
        text = self.normalize_text(oracle_text)
        type_text = self.normalize_text(type_line)
        haystack = f"{type_text} {text}".strip()
        context = self.normalize_text(context_text) if context_text is not None else haystack
        signals: List[MechanicSignal] = []

        for entry in self.entries:
            evidence = entry.get("evidence_strength", "texture")
            if evidence == "texture" and not include_texture:
                continue
            if evidence == "reject" and not include_rejects:
                continue

            patterns = [
                *(entry.get("oracle_patterns") or []),
                *(entry.get("rules_text_patterns") or []),
            ]
            matched = [
                pattern for pattern in patterns
                if self._pattern_matches(pattern, haystack, type_text)
            ]
            if not matched:
                continue

            requirements_met = self._requirements_met(entry.get("requires") or [], context)
            score = self._score_entry(entry, matched, requirements_met)

            if score <= 0 and evidence != "reject":
                continue

            signals.append(MechanicSignal(
                name=entry.get("name", ""),
                theme_family=entry.get("theme_family", ""),
                subthemes=list(entry.get("subthemes") or []),
                evidence_strength=evidence,
                risk_level=entry.get("risk_level", "medium"),
                can_define_deck=bool(entry.get("can_define_deck")),
                support_only=bool(entry.get("support_only")),
                deck_roles=list(entry.get("deck_roles") or []),
                reason_language=entry.get("reason_language", ""),
                strategy_language=entry.get("strategy_language", ""),
                scryfall_query_terms=list(entry.get("scryfall_query_terms") or []),
                matched_patterns=matched,
                requirements_met=requirements_met,
                score=score,
            ))

        signals.sort(key=lambda signal: (
            -signal.score,
            signal.support_only,
            signal.risk_level == "high",
            signal.name,
        ))
        return signals

    def synergies_for_signal(self, signal: MechanicSignal) -> Set[str]:
        synergies = set(self.FAMILY_SYNERGY_MAP.get(signal.theme_family, set()))
        synergies.update(self.NAME_SYNERGY_MAP.get(signal.name, set()))

        if signal.theme_family == "combat":
            subthemes = set(signal.subthemes)
            if signal.requirements_met and (subthemes & self.VOLTRON_SUBTHEMES):
                synergies.add("voltron")

        if signal.theme_family == "artifacts" and set(signal.subthemes) & self.VOLTRON_SUBTHEMES:
            synergies.add("voltron")

        if signal.theme_family == "enchantments" and set(signal.subthemes) & self.VOLTRON_SUBTHEMES:
            synergies.add("voltron")

        if signal.support_only and not signal.requirements_met:
            synergies = {
                synergy for synergy in synergies
                if synergy not in {"voltron", "counters", "artifact_tokens", "tokens"}
            }

        return synergies

    def synergy_scores(self, signals: Iterable[MechanicSignal]) -> Dict[str, int]:
        scores: Dict[str, int] = {}
        for signal in signals:
            if signal.evidence_strength == "reject":
                continue
            for synergy in self.synergies_for_signal(signal):
                scores[synergy] = scores.get(synergy, 0) + signal.score
        return scores

    def best_signal_for_synergy(
        self,
        signals: Iterable[MechanicSignal],
        synergy: str,
    ) -> Optional[MechanicSignal]:
        candidates = [
            signal for signal in signals
            if synergy in self.synergies_for_signal(signal)
            and signal.reason_language
            and signal.evidence_strength != "reject"
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda signal: (
            -signal.score,
            signal.evidence_strength != "core",
            signal.support_only,
            signal.name,
        ))[0]

    def query_for_term(self, term: str) -> Optional[str]:
        entry = self._by_term.get(self.normalize_text(term))
        if not entry:
            return None

        query_terms = [
            query.strip()
            for query in entry.get("scryfall_query_terms", [])
            if isinstance(query, str) and query.strip()
        ]
        if not query_terms:
            return None
        if len(query_terms) == 1:
            return query_terms[0]
        return "(" + " OR ".join(query_terms[:4]) + ")"
