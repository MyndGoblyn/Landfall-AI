import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class HeuristicSignal:
    """A text-pattern signal used only when registry coverage is thin."""

    id: str
    label: str
    category: str
    evidence: str
    reason_language: str
    mapped_synergies: List[str]
    matched_patterns: List[str]
    evidence_strength: str = "heuristic"

    def as_dict(self) -> Dict:
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "evidence": self.evidence,
            "reason_language": self.reason_language,
            "mapped_synergies": self.mapped_synergies,
            "matched_patterns": self.matched_patterns,
            "evidence_strength": self.evidence_strength,
        }


class HeuristicSignalExtractor:
    """Generic Commander text-pattern extraction without commander-name branches."""

    ARTIFACT_TOKEN_TERMS = (
        "treasure", "clue", "food", "blood", "map", "gold", "powerstone",
        "incubator", "junk",
    )

    CARD_TYPE_SYNERGIES = {
        "aura": ["enchantment", "voltron"],
        "equipment": ["artifact", "voltron"],
        "vehicle": ["artifact"],
        "saga": ["enchantment"],
        "class": ["enchantment"],
        "room": ["enchantment"],
        "background": ["enchantment"],
    }

    def extract(self, oracle_text: str, type_line: str = "") -> List[Dict]:
        text = (oracle_text or "").lower()
        type_text = (type_line or "").lower()
        signals: List[HeuristicSignal] = []
        seen = set()

        def add_signal(
            signal_id: str,
            label: str,
            category: str,
            evidence: str,
            reason_language: str,
            mapped_synergies: List[str],
            matched_patterns: List[str],
        ):
            if signal_id in seen:
                return
            seen.add(signal_id)
            signals.append(HeuristicSignal(
                id=signal_id,
                label=label,
                category=category,
                evidence=evidence,
                reason_language=reason_language,
                mapped_synergies=mapped_synergies,
                matched_patterns=matched_patterns,
            ))

        if re.search(r"\bwhenever (?:you attack|one or more creatures attack|[^.]+ attacks)\b", text):
            add_signal(
                "attack_trigger",
                "Attack Trigger",
                "trigger",
                "an attack trigger in the commander text",
                "the commander rewards declaring attackers before combat damage",
                ["attack_triggers"],
                ["whenever ... attacks"],
            )

        if "combat damage to a player" in text or "combat damage to one or more players" in text:
            add_signal(
                "combat_damage_trigger",
                "Combat Damage Trigger",
                "trigger",
                "a combat-damage-to-player trigger",
                "the commander needs creatures to connect with players",
                ["combat_damage"],
                ["combat damage to a player"],
            )

        if re.search(r"\b(when|whenever) [^.]+ enters\b", text) or "enters the battlefield" in text:
            add_signal(
                "enters_battlefield_trigger",
                "ETB Trigger",
                "trigger",
                "an enters-the-battlefield trigger",
                "the commander can care about repeatable permanent entry value",
                ["creature", "blink"],
                ["enters the battlefield"],
            )

        if re.search(r"\b(when|whenever) [^.]+ dies\b", text) or "put into a graveyard from the battlefield" in text:
            add_signal(
                "death_trigger",
                "Death Trigger",
                "trigger",
                "a death or graveyard-from-battlefield trigger",
                "the commander rewards creatures or permanents dying",
                ["sacrifice", "graveyard"],
                ["dies", "graveyard from the battlefield"],
            )

        if re.search(r"\bwhenever you cast (?:an? )?(?:instant|sorcery|noncreature|artifact|enchantment|creature)? ?spell\b", text):
            mapped = ["instant_sorcery"] if any(term in text for term in ["instant", "sorcery", "noncreature spell"]) else ["creature"]
            add_signal(
                "cast_trigger",
                "Cast Trigger",
                "trigger",
                "a spell-cast trigger",
                "the commander rewards repeated spell casting",
                mapped,
                ["whenever you cast"],
            )

        if "sacrifice" in text:
            add_signal(
                "sacrifice_action",
                "Sacrifice Text",
                "action",
                "sacrifice text",
                "the commander uses sacrifice as a resource-conversion action",
                ["sacrifice"],
                ["sacrifice"],
            )

        if any(term in text for term in ["mill", "surveil", "discard a card", "from your graveyard", "in your graveyard"]):
            add_signal(
                "graveyard_resource",
                "Graveyard Resource",
                "zone",
                "self-mill, discard, or graveyard-resource text",
                "the commander treats the graveyard as a resource zone",
                ["graveyard"],
                ["mill", "discard", "graveyard"],
            )

        if "exile" in text and any(term in text for term in ["return", "battlefield", "under its owner's control"]):
            add_signal(
                "blink_pattern",
                "Blink Pattern",
                "action",
                "exile-and-return text",
                "the commander can reuse or reset permanents",
                ["blink"],
                ["exile", "return"],
            )

        if "exile the top" in text or "play that card" in text or "cast that card" in text or "from exile" in text:
            add_signal(
                "exile_access",
                "Exile Access",
                "zone",
                "cast-from-exile or impulse-draw text",
                "the commander uses exile as a playable resource zone",
                ["exile"],
                ["exile the top", "play that card", "from exile"],
            )

        if "create" in text and "token" in text:
            artifact_tokens = [term for term in self.ARTIFACT_TOKEN_TERMS if f"{term} token" in text]
            if artifact_tokens:
                add_signal(
                    "artifact_token_creation",
                    "Artifact Token Creation",
                    "token",
                    f"{artifact_tokens[0]} token creation",
                    "the commander creates artifact tokens that can become mana, material, or value",
                    ["artifact_tokens"],
                    [f"{artifact_tokens[0]} token"],
                )
            if "creature token" in text or re.search(r"\b\d+/\d+ [a-z ]+ creature token\b", text):
                add_signal(
                    "creature_token_creation",
                    "Creature Token Creation",
                    "token",
                    "creature token creation",
                    "the commander creates bodies that can attack, block, scale, or be sacrificed",
                    ["tokens", "creature"],
                    ["creature token"],
                )

        if "+1/+1 counter" in text or "-1/-1 counter" in text or "proliferate" in text or re.search(r"\b[a-z]+ counters?\b", text):
            add_signal(
                "counter_pattern",
                "Counter Pattern",
                "counter",
                "counter placement, counter scaling, or proliferate text",
                "the commander references counters as tracked game objects",
                ["counters"],
                ["counter", "proliferate"],
            )

        if "becomes the target" in text or "target creature you control" in text or "any number of target" in text:
            add_signal(
                "targeting_pattern",
                "Targeting Pattern",
                "target",
                "targeting payoff text",
                "the commander rewards spells or abilities choosing targets",
                ["target_spells"],
                ["target"],
            )

        if "landfall" in text or "land you control enters" in text or "additional land" in text:
            add_signal(
                "land_pattern",
                "Land Pattern",
                "resource",
                "landfall, land-entry, or additional-land text",
                "the commander rewards land drops or land access",
                ["landfall"],
                ["landfall", "land enters", "additional land"],
            )

        if "gain life" in text or "gained life" in text or "life total" in text:
            add_signal(
                "lifegain_pattern",
                "Life-Gain Pattern",
                "resource",
                "life-gain or life-total payoff text",
                "the commander converts life changes into value or pressure",
                ["lifegain"],
                ["gain life", "life total"],
            )

        if "additional combat phase" in text or "extra combat phase" in text:
            add_signal(
                "extra_combat_pattern",
                "Extra Combat Pattern",
                "combat",
                "extra-combat text",
                "the commander can multiply attack steps and attack triggers",
                ["extra_combat", "attack_triggers"],
                ["additional combat", "extra combat"],
            )

        if "goad" in text or "attacks a player other than you" in text:
            add_signal(
                "goad_pattern",
                "Goad Pattern",
                "combat",
                "goad or forced-attack text",
                "the commander pushes opposing creatures into combat elsewhere",
                ["goad"],
                ["goad", "attack a player other than you"],
            )

        if "choose a creature type" in text or "creatures of the chosen type" in text or re.search(r"\b(other )?[a-z]+s you control\b", text):
            add_signal(
                "typal_pattern",
                "Typal Pattern",
                "type-line",
                "creature-type reward text",
                "the commander rewards a specific or chosen creature type",
                ["typal"],
                ["creature type", "you control"],
            )

        if "colorless mana" in text or "add {c}" in text or "mana value 7" in text or "mana value 8" in text:
            add_signal(
                "colorless_mana_pattern",
                "Colorless Mana Pattern",
                "resource",
                "colorless-mana or high-mana-value text",
                "the commander points toward colorless mana development or expensive payoffs",
                ["colorless_big_mana"],
                ["colorless mana", "add {C}", "mana value 7"],
            )

        for card_type, mapped_synergies in self.CARD_TYPE_SYNERGIES.items():
            if card_type in type_text or card_type in text:
                add_signal(
                    f"{card_type}_type_clue",
                    f"{card_type.title()} Type Clue",
                    "type-line",
                    f"{card_type} text or type-line clue",
                    f"the card points toward a {card_type}-aware package",
                    mapped_synergies,
                    [card_type],
                )

        return [signal.as_dict() for signal in signals]
