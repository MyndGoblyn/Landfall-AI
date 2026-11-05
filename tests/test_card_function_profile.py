import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_function_profile import (
    classify_card_functions,
    counter_resources_compatible,
    has_extra_combat,
    strategic_cut_block_reason,
)


def test_alternate_cost_interaction_uses_practical_casting_mode():
    card = {
        "name": "Pyrokinesis",
        "cmc": 6,
        "type_line": "Instant",
        "oracle_text": (
            "You may exile a red card from your hand rather than pay this "
            "spell's mana cost. Pyrokinesis deals 4 damage divided as you "
            "choose among any number of target creatures."
        ),
    }

    profile = classify_card_functions(card)

    assert profile.alternate_cast
    assert profile.practical_mana_value == 2
    assert "interaction" in profile.functions
    assert strategic_cut_block_reason(card, strategy_priorities={"typal"})


def test_named_counter_resources_do_not_cross_match():
    vadrik = {
        "oracle_text": (
            "Whenever day becomes night or night becomes day, put a +1/+1 "
            "counter on Vadrik."
        )
    }
    generatorium = {
        "oracle_text": "Whenever you cast an instant, you get an energy counter."
    }
    proliferate = {"oracle_text": "Proliferate."}

    assert not counter_resources_compatible(vadrik, generatorium)
    assert counter_resources_compatible(vadrik, proliferate)


def test_untap_is_not_extra_combat():
    assert not has_extra_combat("Untap all creatures you control.")
    assert has_extra_combat(
        "After this main phase, there is an additional combat phase."
    )


def test_declared_closer_and_multicolor_fixing_are_cut_blocked():
    stampede = {
        "oracle_text": (
            "Until end of turn, creatures you control get +X/+X and gain "
            "trample, where X is the greatest power among creatures you control."
        ),
        "cmc": 5,
    }
    lantern = {
        "oracle_text": (
            "Lands you control have '{T}: Add one mana of any color.' "
            "{T}: Add one mana of any color."
        ),
        "cmc": 3,
    }

    assert strategic_cut_block_reason(
        stampede,
        strategy_priorities={"go_wide"},
    )
    assert strategic_cut_block_reason(
        lantern,
        color_count=4,
        strategy_priorities={"blink"},
    )


def test_compact_board_copy_and_combat_copy_enablers_are_cut_blocked():
    board_copy = {
        "oracle_text": (
            "Choose target creature you control. Each other creature becomes "
            "a copy of that creature until end of turn, except it isn't legendary."
        ),
        "cmc": 4,
    }
    combat_copy = {
        "oracle_text": (
            "At the beginning of combat on your turn, you may have this creature "
            "become a copy of another target creature you control. It gains haste."
        ),
        "cmc": 4,
    }

    assert strategic_cut_block_reason(
        board_copy,
        strategy_priorities={"compact_wins"},
    )
    assert strategic_cut_block_reason(
        combat_copy,
        strategy_priorities={"combat_combo"},
    )


def test_conditional_graveyard_mana_is_not_reliable_fixing():
    deathrite = {
        "type_line": "Creature — Elf Shaman",
        "oracle_text": (
            "{T}: Exile target land card from a graveyard. "
            "Add one mana of any color."
        ),
        "cmc": 1,
    }

    profile = classify_card_functions(deathrite)
    assert profile.has("conditional_mana_fixing")
    assert not profile.has("mana_fixing")

    token_engine = classify_card_functions({
        "type_line": "Enchantment",
        "oracle_text": (
            'Creature tokens you control have "{T}: Add one mana of any color."'
        ),
        "cmc": 2,
    })
    assert token_engine.has("conditional_mana_fixing")
    assert not token_engine.has("mana_fixing")
