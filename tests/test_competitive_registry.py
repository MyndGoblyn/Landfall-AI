import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import compile_catalog_query
from services.competitive_registry import CompetitiveCardRegistry


def test_default_competitive_registry_is_versioned_and_queryable():
    registry = CompetitiveCardRegistry.load_default()

    assert registry.version == "2026-08-04.1"
    assert registry.row("Force of Will")["labels"] == ["free_interaction"]
    compile_catalog_query(registry.exact_name_query("id<=ub"))


def test_compact_components_require_existing_package_evidence():
    registry = CompetitiveCardRegistry.load_default()

    assert registry.evidence(
        "Lion's Eye Diamond",
        {"najeela, the blade-blossom"},
        {"competitive", "combat_combo"},
    ) is None
    assert registry.evidence(
        "Lion's Eye Diamond",
        {"underworld breach"},
        {"competitive", "compact_wins"},
    ) is not None


def test_low_power_outliers_are_explicit_not_inferred_from_price_alone():
    registry = CompetitiveCardRegistry.load_default()

    assert registry.is_power_outlier("Gilded Drake")
    assert not registry.is_power_outlier("Volatile Stormdrake")
