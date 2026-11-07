import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


from services.competitive_registry import (
    DEFAULT_REGISTRY_PATH,
    CompetitiveCardRegistry,
)


def test_competitive_registry_is_versioned_unique_and_function_labeled():
    payload = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry = CompetitiveCardRegistry(payload)
    names = [row["name"].casefold() for row in payload["cards"]]

    assert registry.version == "2026-11-06.1"
    assert registry.count() >= 100
    assert registry.public_count() == 48
    assert len(names) == len(set(names))
    assert all(row.get("labels") for row in payload["cards"])
    assert all(row.get("strategies") for row in payload["cards"])


def test_commander_specific_competitive_evidence_requires_exact_package_context():
    registry = CompetitiveCardRegistry.load_default()

    assert registry.evidence(
        "Storm-Kiln Artist",
        {"vadrik, astral archmage"},
        {"compact_wins"},
        construction_context=True,
    )
    assert registry.evidence(
        "Storm-Kiln Artist",
        set(),
        {"compact_wins"},
        construction_context=True,
    ) is None
    assert registry.evidence(
        "Ingenious Infiltrator",
        {"yuriko, the tiger's shadow"},
        {"card_velocity"},
        construction_context=True,
    )
    assert registry.evidence(
        "Ingenious Infiltrator",
        {"najeela, the blade-blossom"},
        {"card_velocity"},
        construction_context=True,
    ) is None


def test_general_competitive_card_velocity_remains_strategy_scoped():
    registry = CompetitiveCardRegistry.load_default()

    assert registry.evidence(
        "Brainstorm",
        set(),
        {"card_velocity"},
        construction_context=True,
    )
    assert registry.evidence(
        "Brainstorm",
        set(),
        {"combat_combo"},
        construction_context=True,
    ) is None
    assert registry.evidence(
        "Brainstorm",
        set(),
        {"card_velocity"},
    ) is None
    assert "Brainstorm" not in registry.candidate_names()
    assert "Brainstorm" in registry.candidate_names(construction_context=True)
