"""Versioned, deterministic intent contract for Guided Build."""

from __future__ import annotations

from typing import Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from services.deck_intent import (
    BudgetMode,
    DeckIntentProfile,
    IntentionalConstraint,
    ProtectedPackage,
    StrategyPriority,
    normalize_intent_profile,
    protected_card_names,
)


StartingPoint = Literal[
    "blank",
    "imported_list",
    "existing_deck",
    "commander",
    "card",
    "concept",
]
BuildMode = Literal["manual", "guided_scaffold", "complete_draft"]
BuildPlaystyle = Literal[
    "balanced",
    "aggressive",
    "value",
    "control",
    "combo",
    "custom",
]
BuildShape = Literal["full_deck", "core_shell", "mana_base", "missing_slots"]
CollectionMode = Literal["all_cards", "prefer_owned", "owned_only"]
CollectionSource = Literal["manual", "saved_collection"]


POWER_BANDS = {
    1: (1, 2),
    2: (3, 4),
    3: (5, 6),
    4: (7, 8),
    5: (9, 10),
}

PLAYSTYLE_PRIORITIES: Dict[str, List[StrategyPriority]] = {
    "balanced": ["card_velocity", "protection"],
    "aggressive": ["go_wide", "combat_combo", "protection"],
    "value": ["card_velocity", "permanent_engine", "protection"],
    "control": ["stack_interaction", "card_velocity", "protection"],
    "combo": ["compact_wins", "card_velocity", "protection"],
}

PLAYSTYLE_LANE_WEIGHTS = {
    "balanced": {
        "engine": 1.0,
        "pressure": 1.0,
        "interaction": 1.0,
        "resilience": 1.0,
    },
    "aggressive": {
        "engine": 0.9,
        "pressure": 1.35,
        "interaction": 0.85,
        "resilience": 1.0,
    },
    "value": {
        "engine": 1.3,
        "pressure": 0.85,
        "interaction": 1.0,
        "resilience": 1.15,
    },
    "control": {
        "engine": 1.0,
        "pressure": 0.7,
        "interaction": 1.4,
        "resilience": 1.15,
    },
    "combo": {
        "engine": 1.25,
        "pressure": 0.7,
        "interaction": 1.15,
        "resilience": 1.0,
    },
    "custom": {
        "engine": 1.0,
        "pressure": 1.0,
        "interaction": 1.0,
        "resilience": 1.0,
    },
}


def _clean_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _clean_unique_strings(values: List[str], limit: int) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for value in values:
        item = " ".join(str(value or "").split())
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


class BuildIntent(BaseModel):
    """Facts a user confirms before deterministic construction may begin."""

    schema_version: int = 1
    confirmed: bool = False
    format: Literal["commander"] = "commander"
    deck_name: str = Field(min_length=1, max_length=120)
    starting_point: StartingPoint = "blank"
    existing_deck_id: Optional[str] = Field(default=None, max_length=80)
    commander_name: Optional[str] = Field(default=None, max_length=200)
    commander_oracle_id: Optional[str] = Field(default=None, max_length=80)
    partner_name: Optional[str] = Field(default=None, max_length=200)
    partner_oracle_id: Optional[str] = Field(default=None, max_length=80)
    starting_card_name: Optional[str] = Field(default=None, max_length=200)
    concept: Optional[str] = Field(default=None, max_length=320)
    build_mode: BuildMode = "manual"
    playstyle: BuildPlaystyle = "balanced"
    custom_strategy_priorities: List[StrategyPriority] = Field(
        default_factory=list,
        max_length=16,
    )
    target_bracket: int = Field(default=3, ge=1, le=5)
    power_level_min: Optional[int] = Field(default=None, ge=1, le=10)
    power_level_max: Optional[int] = Field(default=None, ge=1, le=10)
    budget_mode: BudgetMode = "unknown"
    budget_limit_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    max_card_price_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    build_shape: BuildShape = "full_deck"
    collection_mode: CollectionMode = "all_cards"
    collection_source: CollectionSource = "manual"
    owned_card_names: List[str] = Field(default_factory=list, max_length=500)
    owned_card_quantities: Dict[str, int] = Field(default_factory=dict)
    protected_cards: List[str] = Field(default_factory=list, max_length=100)
    protected_packages: List[ProtectedPackage] = Field(
        default_factory=list,
        max_length=20,
    )
    excluded_cards: List[str] = Field(default_factory=list, max_length=100)
    intentional_constraints: List[IntentionalConstraint] = Field(
        default_factory=list,
        max_length=8,
    )
    notes: Optional[str] = Field(default=None, max_length=600)

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Unsupported build intent schema version")
        return value

    @field_validator("deck_name")
    @classmethod
    def clean_deck_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Deck name cannot be blank")
        return cleaned

    @field_validator(
        "existing_deck_id",
        "commander_name",
        "commander_oracle_id",
        "partner_name",
        "partner_oracle_id",
        "starting_card_name",
        "concept",
        "notes",
    )
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        return _clean_optional_text(value)

    @field_validator("owned_card_names")
    @classmethod
    def clean_owned_cards(cls, value: List[str]) -> List[str]:
        return _clean_unique_strings(value, 500)

    @field_validator("owned_card_quantities")
    @classmethod
    def clean_owned_quantities(cls, value: Dict[str, int]) -> Dict[str, int]:
        cleaned: Dict[str, int] = {}
        for raw_name, raw_quantity in value.items():
            name = " ".join(str(raw_name or "").split())
            if not name:
                continue
            quantity = int(raw_quantity)
            if quantity < 1 or quantity > 999:
                raise ValueError("Owned-card quantities must be between 1 and 999")
            cleaned[name] = quantity
            if len(cleaned) >= 5000:
                break
        return cleaned

    @field_validator("protected_cards", "excluded_cards")
    @classmethod
    def clean_card_lists(cls, value: List[str]) -> List[str]:
        return _clean_unique_strings(value, 100)

    @field_validator("custom_strategy_priorities", "intentional_constraints")
    @classmethod
    def unique_structured_fields(cls, value: List[str]) -> List[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_contract(self) -> "BuildIntent":
        if self.starting_point == "commander" and not self.commander_name:
            raise ValueError("Commander starting point requires a commander")
        if self.starting_point == "card" and not self.starting_card_name:
            raise ValueError("Card starting point requires a card name")
        if self.starting_point == "concept" and not (self.concept or self.notes):
            raise ValueError("Concept starting point requires a concept")
        if self.starting_point == "existing_deck" and not self.existing_deck_id:
            raise ValueError("Existing deck starting point requires a deck ID")
        if self.partner_name and not self.commander_name:
            raise ValueError("A partner or background requires a primary commander")
        if (
            self.partner_name
            and self.commander_name
            and self.partner_name.casefold() == self.commander_name.casefold()
        ):
            raise ValueError("Primary and partner commanders must be different")
        if self.playstyle == "custom" and not self.custom_strategy_priorities:
            raise ValueError("Custom playstyle requires at least one strategy priority")
        if (
            self.power_level_min is not None
            and self.power_level_max is not None
            and self.power_level_min > self.power_level_max
        ):
            raise ValueError("power_level_min cannot exceed power_level_max")
        band_min, band_max = POWER_BANDS[self.target_bracket]
        if self.power_level_min is not None and not band_min <= self.power_level_min <= band_max:
            raise ValueError("power_level_min conflicts with the selected power band")
        if self.power_level_max is not None and not band_min <= self.power_level_max <= band_max:
            raise ValueError("power_level_max conflicts with the selected power band")
        if self.budget_mode == "strict" and self.max_card_price_usd is None:
            raise ValueError("Strict budget requires a per-card limit")
        if self.budget_mode == "target" and (
            self.budget_limit_usd is None and self.max_card_price_usd is None
        ):
            raise ValueError("Target budget requires a total or per-card target")
        if self.budget_mode == "unrestricted" and (
            self.budget_limit_usd is not None or self.max_card_price_usd is not None
        ):
            raise ValueError("Unrestricted budget cannot include price limits")
        if self.build_shape == "missing_slots" and self.starting_point not in {
            "existing_deck",
            "imported_list",
        }:
            raise ValueError("Missing-slots mode requires an existing or imported list")
        if (
            self.collection_mode == "owned_only"
            and self.collection_source == "manual"
            and not self.owned_card_names
            and not self.owned_card_quantities
        ):
            raise ValueError("Owned-only mode requires at least one owned card")

        protected = protected_card_names({
            "protected_cards": self.protected_cards,
            "protected_packages": [package.model_dump() for package in self.protected_packages],
        })
        excluded = {name.casefold() for name in self.excluded_cards}
        overlap = sorted(protected & excluded)
        if overlap:
            raise ValueError(
                "Cards cannot be both protected and excluded: " + ", ".join(overlap)
            )
        return self


def _resolved_power_range(intent: BuildIntent) -> tuple[int, int]:
    band_min, band_max = POWER_BANDS[intent.target_bracket]
    return (
        intent.power_level_min if intent.power_level_min is not None else band_min,
        intent.power_level_max if intent.power_level_max is not None else band_max,
    )


def _power_policy(target_bracket: int) -> Dict:
    return {
        1: {
            "fast_mana": "exclude",
            "tutors": "exclude",
            "compact_combos": "exclude",
            "interaction": "light",
        },
        2: {
            "fast_mana": "exclude",
            "tutors": "limited",
            "compact_combos": "exclude",
            "interaction": "standard",
        },
        3: {
            "fast_mana": "limited",
            "tutors": "limited",
            "compact_combos": "disclosed",
            "interaction": "standard",
        },
        4: {
            "fast_mana": "allowed",
            "tutors": "allowed",
            "compact_combos": "allowed",
            "interaction": "high",
        },
        5: {
            "fast_mana": "expected",
            "tutors": "expected",
            "compact_combos": "expected",
            "interaction": "competitive",
        },
    }[target_bracket]


def _shape_policy(shape: BuildShape) -> Dict:
    return {
        "full_deck": {
            "scope": "all_noncommander_slots",
            "maximum_requested_slots": 99,
        },
        "core_shell": {
            "scope": "engine_and_support_core",
            "maximum_requested_slots": 40,
        },
        "mana_base": {
            "scope": "lands_and_mana_sources",
            "maximum_requested_slots": 40,
        },
        "missing_slots": {
            "scope": "unfilled_slots_only",
            "maximum_requested_slots": 99,
        },
    }[shape]


def _deck_intent_from_build(intent: BuildIntent) -> Dict:
    power_min, power_max = _resolved_power_range(intent)
    priorities = (
        intent.custom_strategy_priorities
        if intent.playstyle == "custom"
        else PLAYSTYLE_PRIORITIES[intent.playstyle]
    )
    constraints = list(intent.intentional_constraints)
    power_policy = _power_policy(intent.target_bracket)
    for policy, constraint in (
        ("fast_mana", "no_fast_mana"),
        ("tutors", "no_tutors"),
        ("compact_combos", "no_infinite_combos"),
    ):
        if power_policy[policy] == "exclude" and constraint not in constraints:
            constraints.append(constraint)

    experience_tags = []
    if intent.target_bracket <= 3:
        experience_tags.append("casual")
    if intent.target_bracket == 4:
        experience_tags.append("high_power")
    if intent.target_bracket == 5:
        experience_tags.extend(["high_power", "cedh", "tournament"])
    if intent.budget_mode in {"strict", "target"}:
        experience_tags.append("budget")

    strategy_parts = [intent.playstyle.replace("_", " ")]
    if intent.commander_name:
        strategy_parts.append(f"led by {intent.commander_name}")
    if intent.concept:
        strategy_parts.append(intent.concept)

    profile = DeckIntentProfile(
        confirmed=intent.confirmed,
        power_level_min=power_min,
        power_level_max=power_max,
        budget_mode=intent.budget_mode,
        budget_limit_usd=intent.budget_limit_usd,
        max_card_price_usd=intent.max_card_price_usd,
        optimization_mode=(
            "competitive"
            if intent.target_bracket == 5
            else "preserve"
            if intent.target_bracket <= 2
            else "tune"
        ),
        primary_strategy="; ".join(strategy_parts),
        desired_experience=intent.notes,
        strategy_priorities=priorities,
        experience_tags=experience_tags,
        protected_cards=intent.protected_cards,
        protected_packages=intent.protected_packages,
        excluded_cards=intent.excluded_cards,
        intentional_constraints=constraints,
        power_outlier_policy="preserve" if intent.target_bracket <= 2 else "allow",
        generic_staple_tolerance=(
            "low"
            if intent.target_bracket <= 2
            or bool({"intentional_jank", "flavor_first"} & set(constraints))
            else "high"
            if intent.target_bracket == 5
            else "normal"
        ),
    )
    return normalize_intent_profile(profile)


def normalize_build_intent(value: Mapping | BuildIntent) -> Dict:
    """Return stable canonical intent, engine mapping, and disclosed policies."""
    intent = value if isinstance(value, BuildIntent) else BuildIntent.model_validate(dict(value))
    power_min, power_max = _resolved_power_range(intent)
    priorities = (
        list(intent.custom_strategy_priorities)
        if intent.playstyle == "custom"
        else list(PLAYSTYLE_PRIORITIES[intent.playstyle])
    )
    canonical = intent.model_dump(mode="json")
    canonical["power_level_min"] = power_min
    canonical["power_level_max"] = power_max
    construction = {
        "manual": {
            "enabled": False,
            "availability": "manual_only",
            "next_action": "save_intent_and_open_manual_deck",
        },
        "guided_scaffold": {
            "enabled": True,
            "availability": "phase_4_scaffold",
            "next_action": "save_intent_and_build_scaffold",
        },
        "complete_draft": {
            "enabled": True,
            "availability": "phase_5_promoted",
            "next_action": "save_intent_and_build_complete_draft",
        },
    }[intent.build_mode]
    return {
        "schema_version": 1,
        "intent": canonical,
        "deck_intent_profile": _deck_intent_from_build(intent),
        "mapping": {
            "format": {
                "id": intent.format,
                "deck_size": 100,
                "singleton": True,
                "commander_slots": 2 if intent.partner_name else 1,
            },
            "playstyle": {
                "id": intent.playstyle,
                "strategy_priorities": priorities,
                "lane_weights": PLAYSTYLE_LANE_WEIGHTS[intent.playstyle],
            },
            "power": {
                "target_bracket": intent.target_bracket,
                "range": [power_min, power_max],
                "policies": _power_policy(intent.target_bracket),
            },
            "budget": {
                "mode": intent.budget_mode,
                "total_limit_usd": intent.budget_limit_usd,
                "per_card_limit_usd": intent.max_card_price_usd,
                "hard_gate": intent.budget_mode == "strict",
            },
            "build_shape": _shape_policy(intent.build_shape),
            "collection": {
                "mode": intent.collection_mode,
                "source": intent.collection_source,
                "owned_card_count": len({
                    name.casefold()
                    for name in [
                        *intent.owned_card_names,
                        *intent.owned_card_quantities.keys(),
                    ]
                }),
                "hard_gate": intent.collection_mode == "owned_only",
            },
            "construction": {
                "requested_mode": intent.build_mode,
                **construction,
            },
        },
    }


def migrate_legacy_deck_intent(
    value: Optional[Mapping],
    *,
    deck_name: str,
    commander_name: Optional[str] = None,
    existing_deck_id: Optional[str] = None,
) -> Dict:
    """Create a stable BuildIntent view over a saved DeckIntentProfile v1."""
    legacy = normalize_intent_profile(value)
    power_max = legacy.get("power_level_max")
    power_min = legacy.get("power_level_min")
    power_reference = power_max or power_min or 6
    target_bracket = next(
        bracket
        for bracket, (_minimum, maximum) in POWER_BANDS.items()
        if power_reference <= maximum
    )
    band_min, band_max = POWER_BANDS[target_bracket]
    priorities = list(legacy.get("strategy_priorities") or [])
    intent = BuildIntent(
        confirmed=bool(legacy.get("confirmed")),
        deck_name=deck_name,
        starting_point="existing_deck" if existing_deck_id else (
            "commander" if commander_name else "blank"
        ),
        existing_deck_id=existing_deck_id,
        commander_name=commander_name,
        build_mode="manual",
        playstyle="custom" if priorities else "balanced",
        custom_strategy_priorities=priorities,
        target_bracket=target_bracket,
        power_level_min=(
            power_min if power_min is not None and band_min <= power_min <= band_max else None
        ),
        power_level_max=(
            power_max if power_max is not None and band_min <= power_max <= band_max else None
        ),
        budget_mode=legacy.get("budget_mode", "unknown"),
        budget_limit_usd=legacy.get("budget_limit_usd"),
        max_card_price_usd=legacy.get("max_card_price_usd"),
        build_shape="missing_slots" if existing_deck_id else "full_deck",
        collection_mode="all_cards",
        protected_cards=legacy.get("protected_cards") or [],
        protected_packages=legacy.get("protected_packages") or [],
        excluded_cards=legacy.get("excluded_cards") or [],
        intentional_constraints=legacy.get("intentional_constraints") or [],
        notes=legacy.get("desired_experience"),
    )
    return normalize_build_intent(intent)
