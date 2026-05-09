import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.enhanced_suggestion_engine import EnhancedSuggestionEngine


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
MATRIX_PATH = FIXTURE_DIR / "golden_commander_qa_matrix.md"
CARDS_PATH = FIXTURE_DIR / "golden_commander_cards.json"


@dataclass
class GoldenCommanderCase:
    name: str
    expected_themes: List[str]
    should_recommend: List[str]
    should_avoid: List[str]
    reason_notes: List[str]


def _parse_bullet_section(lines: List[str], start: int) -> tuple[List[str], int]:
    values = []
    index = start
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.endswith(":") and not line.startswith("-"):
            break
        if line.startswith("## "):
            break
        if line.startswith("- "):
            values.append(line[2:].strip())
        index += 1
    return values, index


def load_golden_matrix() -> List[GoldenCommanderCase]:
    lines = MATRIX_PATH.read_text(encoding="utf-8").splitlines()
    cases = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line.startswith("## "):
            index += 1
            continue

        case = GoldenCommanderCase(
            name=line[3:].strip(),
            expected_themes=[],
            should_recommend=[],
            should_avoid=[],
            reason_notes=[],
        )
        index += 1
        while index < len(lines) and not lines[index].startswith("## "):
            header = lines[index].strip().lower()
            if header == "expected primary themes:":
                case.expected_themes, index = _parse_bullet_section(lines, index + 1)
                continue
            if header == "should recommend:":
                case.should_recommend, index = _parse_bullet_section(lines, index + 1)
                continue
            if header == "should avoid:":
                case.should_avoid, index = _parse_bullet_section(lines, index + 1)
                continue
            if header == "reason quality notes:":
                case.reason_notes, index = _parse_bullet_section(lines, index + 1)
                continue
            index += 1
        cases.append(case)
    return cases


def load_commander_cards() -> Dict[str, Dict]:
    return json.loads(CARDS_PATH.read_text(encoding="utf-8"))


def expected_synergies_for_text(text: str) -> Set[str]:
    normalized = text.lower()
    expected = set()

    rules = [
        (r"shrine|enchant|aura", {"enchantment"}),
        (r"aura voltron|voltron|commander-damage|single-attacker", {"voltron"}),
        (r"equipment", {"artifact", "voltron"}),
        (r"artifact recursion-like", {"artifact"}),
        (r"artifact recursion(?!-like)|graveyard artifact|historic artifact", {"artifact", "graveyard"}),
        (r"artifact token copies|temporary artifact token copies", {"artifact", "tokens"}),
        (r"artifact tokens?(?! copies)|treasure|clue|investigate", {"artifact_tokens"}),
        (r"artifact-count|artifact mana|artifact-based|artifact value|colorless artifacts", {"artifact"}),
        (r"token multiplication|token aristocrats|token sacrifice|aggro tokens|token copying|zombie token", {"tokens"}),
        (r"proliferate|counter", {"counters"}),
        (r"sacrifice|aristocrats|death-trigger|lifedrain", {"sacrifice"}),
        (r"blink|flicker", {"blink"}),
        (r"etb", {"creature"}),
        (r"spellslinger|magecraft|spell-copy|spell recursion|cost reduction", {"instant_sorcery"}),
        (r"target-based|target count", {"target_spells"}),
        (r"landfall|lands matter|land recursion|land sacrifice", {"landfall"}),
        (r"graveyard|reanimator|recursion|self-mill|discard", {"graveyard"}),
        (r"vampire|dragon|zombie|insect|typal", {"typal"}),
        (r"combat damage|evasive creature|shared commander aggression", {"combat_damage"}),
        (r"attack trigger|extra combat|combat aggression", {"attack_triggers"}),
        (r"extra combat", {"extra_combat"}),
        (r"goad|forced combat", {"goad"}),
        (r"colorless|eldrazi|high-mana-value", {"colorless_big_mana"}),
        (r"donate|control exchange|political value|permanent exchange|control rotation", {"donation"}),
        (r"forced reanimation|graveyard politics", {"forced_reanimation"}),
        (r"end-the-turn|temporary-effect|temporary effect", {"temporary_drawback"}),
        (r"background", {"enchantment"}),
    ]
    for pattern, synergies in rules:
        if re.search(pattern, normalized):
            expected.update(synergies)
    if "recursion-like" in normalized:
        expected.discard("graveyard")
    return expected


def avoid_synergies_for_text(text: str) -> Set[str]:
    normalized = text.lower()
    avoid = set()
    rules = [
        (r"equipment voltron|aura voltron|voltron-only|normal go-wide aggro", {"voltron"}),
        (r"creature-token|token swarm|go-wide|boros tokens", {"tokens"}),
        (r"spellslinger|cantrip-only|burn", {"instant_sorcery"}),
        (r"reanimator package that ignores|creature reanimator packages", set()),
        (r"generic artifact recursion", set()),
        (r"treasure-only|artifact token", {"artifact_tokens"}),
        (r"lifegain", {"lifegain"}),
        (r"counters|poison", {"counters"}),
        (r"landfall|lands matter", {"landfall"}),
        (r"blink", {"blink"}),
        (r"typal|tribal|squirrel|dragon|non-dragon|non-vampire|zombie", {"typal"}),
        (r"color identity|colored", {"colorless_big_mana"}),
    ]
    for pattern, synergies in rules:
        if re.search(pattern, normalized):
            avoid.update(synergies)
    return avoid


def test_golden_matrix_has_expected_shape_and_fixture_coverage():
    cases = load_golden_matrix()
    cards = load_commander_cards()

    assert len(cases) == 60
    assert set(case.name for case in cases) == set(cards)
    assert all(case.expected_themes for case in cases)
    assert all(case.reason_notes for case in cases)


def test_golden_matrix_expected_theme_detection_is_broad_not_commander_specific():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    cards = load_commander_cards()
    failures = []

    for case in load_golden_matrix():
        card = cards[case.name]
        synergies = set(engine._detect_commander_synergies(card))
        expected = set()
        for theme in case.expected_themes:
            expected.update(expected_synergies_for_text(theme))
        if not expected.issubset(synergies):
            failures.append((case.name, sorted(expected - synergies), sorted(synergies)))

    assert not failures


def test_golden_matrix_avoid_rules_do_not_trigger_unless_expected_elsewhere():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    cards = load_commander_cards()
    failures = []

    for case in load_golden_matrix():
        card = cards[case.name]
        synergies = set(engine._detect_commander_synergies(card))
        expected = set()
        for theme in case.expected_themes:
            expected.update(expected_synergies_for_text(theme))
        avoid = set()
        for item in case.should_avoid:
            avoid.update(avoid_synergies_for_text(item))
        forbidden = avoid - expected
        bad_hits = forbidden & synergies
        if bad_hits:
            failures.append((case.name, sorted(bad_hits), sorted(synergies), case.should_avoid))

    assert not failures


def test_golden_matrix_reason_notes_are_reflected_in_pilot_notes_for_key_constraints():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    cards = load_commander_cards()
    cases = {case.name: case for case in load_golden_matrix()}
    commanders_to_check = [
        "Zur the Enchanter",
        "Light-Paws, Emperor's Voice",
        "The Beamtown Bullies",
        "Obeka, Brute Chronologist",
        "Zedruu the Greathearted",
        "Hinata, Dawn-Crowned",
        "Kozilek, the Great Distortion",
        "Edric, Spymaster of Trest",
        "Isshin, Two Heavens as One",
        "Edgar Markov",
    ]

    expected_fragments = {
        "Zur the Enchanter": ["mana value 3", "enchantment"],
        "Light-Paws, Emperor's Voice": ["aura", "mana value"],
        "The Beamtown Bullies": ["bad gifts", "opponents"],
        "Obeka, Brute Chronologist": ["timing", "delayed"],
        "Zedruu the Greathearted": ["ownership", "control"],
        "Hinata, Dawn-Crowned": ["targeted", "target"],
        "Kozilek, the Great Distortion": ["colorless", "utility lands"],
        "Edric, Spymaster of Trest": ["connect", "players"],
        "Isshin, Two Heavens as One": ["attack triggers", "declaring attackers"],
        "Edgar Markov": ["typal", "density"],
    }

    for name in commanders_to_check:
        card = cards[name]
        synergies = engine._detect_commander_synergies(card)
        tips = engine._generate_commander_strategy_tips(
            card,
            synergies,
            engine._get_commander_constraints(card),
        )
        joined = " ".join(tips).lower()
        for fragment in expected_fragments[name]:
            assert fragment in joined, (name, cases[name].reason_notes, tips)


def test_aura_tutor_commanders_do_not_accept_generic_equipment_recommendations():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    cards = load_commander_cards()
    constraints = engine._get_commander_constraints(cards["Light-Paws, Emperor's Voice"])

    equipment_card = {
        "name": "Generic Equipment",
        "type_line": "Artifact - Equipment",
        "oracle_text": "Equipped creature gets +1/+1.",
    }
    aura_card = {
        "name": "Generic Aura",
        "type_line": "Enchantment - Aura",
        "oracle_text": "Enchant creature. Enchanted creature gets +1/+1.",
    }

    assert not engine._passes_commander_recommendation_constraints(equipment_card, 1, constraints)
    assert engine._passes_commander_recommendation_constraints(aura_card, 1, constraints)


def test_aura_tutor_reasoning_labels_aura_support_instead_of_equipment_pressure():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    commander = load_commander_cards()["Light-Paws, Emperor's Voice"]
    support_card = {
        "name": "Aura Support Creature",
        "type_line": "Creature - Dwarf Advisor",
        "oracle_text": "Whenever you cast an Aura, Equipment, or Vehicle spell, draw a card.",
        "cmc": 2,
    }

    quality = engine._recommendation_quality_metadata(support_card, "voltron", commander)
    reason = engine._generate_validated_recommendation_reason(
        support_card,
        commander["name"],
        "voltron",
        quality,
        commander,
    )

    assert "Aura" in reason
    assert "equipment pressure" not in reason


def test_target_cost_commanders_rate_scalable_targeted_spells_as_core_fits():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    commander = load_commander_cards()["Hinata, Dawn-Crowned"]
    scalable_spell = {
        "name": "Scalable Target Spell",
        "type_line": "Instant",
        "oracle_text": "Scalable Target Spell deals X damage divided as you choose among any number of target creatures.",
        "cmc": 3,
    }

    quality = engine._recommendation_quality_metadata(scalable_spell, "target_spells", commander)

    assert quality["score"] >= 84
    assert "direct_synergy" in quality["evidence_tags"]


def test_forced_reanimation_prefers_bad_gifts_and_ignores_blink_protection_drawbacks():
    engine = EnhancedSuggestionEngine(scryfall_service=None)
    commander = load_commander_cards()["The Beamtown Bullies"]
    bad_gift = {
        "name": "Bad Gift Creature",
        "type_line": "Creature - Horror",
        "oracle_text": "When Bad Gift Creature enters the battlefield, you skip your next turn.",
        "cmc": 4,
    }
    blink_protection = {
        "name": "Blink Protection Creature",
        "type_line": "Creature - Elder Dinosaur",
        "oracle_text": "Discard three cards: Exile it. Return it to the battlefield tapped under its owner's control at the beginning of the next end step.",
        "cmc": 7,
    }

    quality = engine._recommendation_quality_metadata(bad_gift, "forced_reanimation", commander)
    reason = engine._generate_validated_recommendation_reason(
        bad_gift,
        commander["name"],
        "forced_reanimation",
        quality,
        commander,
    )

    assert quality["score"] >= 84
    assert "direct_synergy" in quality["evidence_tags"]
    assert "bad gift creature" in reason
    assert not engine._has_temporary_drawback_text(blink_protection["oracle_text"].lower())
