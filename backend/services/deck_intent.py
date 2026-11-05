"""Validated deck intent and deterministic recommendation constraints."""

from __future__ import annotations

from typing import Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


BudgetMode = Literal["unknown", "strict", "target", "flexible", "unrestricted"]
OptimizationMode = Literal["preserve", "tune", "competitive", "repair"]
StrategyPriority = Literal[
    "typal",
    "go_wide",
    "spell_chain",
    "donation",
    "politics",
    "graveyard_recursion",
    "permanent_engine",
    "blink",
    "voltron",
    "compact_wins",
    "stack_interaction",
    "mana_fixing",
    "combat_combo",
    "card_velocity",
    "protection",
    "competitive",
]
ExperienceTag = Literal[
    "budget",
    "casual",
    "political",
    "chaotic",
    "jank",
    "flavor_first",
    "high_power",
    "cedh",
    "tournament",
]
ProtectedRole = Literal[
    "closer",
    "engine",
    "mana_fixing",
    "card_advantage",
    "interaction",
    "tutor",
    "combo_piece",
    "typal_payoff",
]
IntentionalConstraint = Literal[
    "typal_core",
    "spell_density",
    "intentional_jank",
    "flavor_first",
    "low_land_count",
    "no_fast_mana",
    "no_tutors",
    "no_infinite_combos",
]


class ProtectedPackage(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    cards: List[str] = Field(default_factory=list, max_length=30)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("cards")
    @classmethod
    def clean_cards(cls, value: List[str]) -> List[str]:
        return _clean_unique_strings(value, limit=30)


class DeckIntentProfile(BaseModel):
    """User-owned constraints that inference must not silently replace."""

    schema_version: int = 1
    confirmed: bool = False
    power_level_min: Optional[int] = Field(default=None, ge=1, le=10)
    power_level_max: Optional[int] = Field(default=None, ge=1, le=10)
    budget_mode: BudgetMode = "unknown"
    budget_limit_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    max_card_price_usd: Optional[float] = Field(default=None, ge=0, le=100000)
    optimization_mode: OptimizationMode = "preserve"
    primary_strategy: Optional[str] = Field(default=None, max_length=160)
    desired_experience: Optional[str] = Field(default=None, max_length=320)
    strategy_priorities: List[StrategyPriority] = Field(
        default_factory=list,
        max_length=16,
    )
    experience_tags: List[ExperienceTag] = Field(
        default_factory=list,
        max_length=12,
    )
    protected_roles: List[ProtectedRole] = Field(
        default_factory=list,
        max_length=12,
    )
    power_outlier_policy: Literal["auto", "preserve", "allow"] = "auto"
    generic_staple_tolerance: Literal["auto", "low", "normal", "high"] = "auto"
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

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Unsupported deck intent schema version")
        return value

    @field_validator("primary_strategy", "desired_experience")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("protected_cards", "excluded_cards")
    @classmethod
    def clean_card_lists(cls, value: List[str]) -> List[str]:
        return _clean_unique_strings(value, limit=100)

    @field_validator("intentional_constraints")
    @classmethod
    def unique_constraints(
        cls,
        value: List[IntentionalConstraint],
    ) -> List[IntentionalConstraint]:
        return list(dict.fromkeys(value))

    @field_validator("strategy_priorities", "experience_tags", "protected_roles")
    @classmethod
    def unique_structured_intent(cls, value: List[str]) -> List[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_ranges(self) -> "DeckIntentProfile":
        if (
            self.power_level_min is not None
            and self.power_level_max is not None
            and self.power_level_min > self.power_level_max
        ):
            raise ValueError("power_level_min cannot exceed power_level_max")
        if self.budget_mode == "strict" and self.max_card_price_usd is None:
            raise ValueError(
                "strict budget mode requires max_card_price_usd so candidates "
                "can be verified"
            )
        protected = protected_card_names(self.model_dump())
        excluded = {name.casefold() for name in self.excluded_cards}
        overlap = sorted(protected & excluded)
        if overlap:
            raise ValueError(
                "Cards cannot be both protected and excluded: " + ", ".join(overlap)
            )
        return self


def normalize_intent_profile(value: Optional[Mapping] = None) -> Dict:
    """Return the canonical serializable intent profile."""
    if isinstance(value, DeckIntentProfile):
        profile = value
    else:
        profile = DeckIntentProfile.model_validate(dict(value or {}))
    return _resolve_structured_intent(profile.model_dump())


def _resolve_structured_intent(profile: Dict) -> Dict:
    """Map confirmed prose into a small, inspectable vocabulary when fields are absent."""
    result = dict(profile)
    text = " ".join(
        str(result.get(field) or "")
        for field in ("primary_strategy", "desired_experience")
    ).casefold()
    constraints = set(result.get("intentional_constraints") or [])
    priorities = list(result.get("strategy_priorities") or [])
    experiences = list(result.get("experience_tags") or [])
    protected_roles = list(result.get("protected_roles") or [])

    def affirmative(term: str) -> bool:
        position = text.find(term)
        while position >= 0:
            prefix = text[max(0, position - 48):position]
            if not any(
                marker in prefix
                for marker in (
                    "avoid ", "avoiding ", "do not ", "don't ", "not ",
                    "rather than ", "without ",
                )
            ):
                return True
            position = text.find(term, position + len(term))
        return False

    priority_terms = {
        "typal": ("typal", "tribal", "ninja", "elf", "goblin", "zombie"),
        "go_wide": ("go-wide", "go wide", "token pressure", "wide board"),
        "spell_chain": ("storm", "spellslinger", "spell-chain", "spell chain"),
        "donation": ("donation", "donates", "bad-gift", "bad gift"),
        "politics": ("political", "group hug", "table-facing"),
        "graveyard_recursion": ("graveyard", "recursion", "reanimate"),
        "permanent_engine": ("permanent-based", "permanent recursion", "permanent engine"),
        "blink": ("blink", "flicker"),
        "voltron": ("voltron", "aura toolbox", "commander damage"),
        "compact_wins": ("compact win", "compact combo", "tempo-combo"),
        "stack_interaction": ("stack interaction", "free interaction", "tournament-speed interaction"),
        "mana_fixing": ("four-color", "five-color", "fixing"),
        "combat_combo": ("combat combo", "combat win"),
        "card_velocity": ("card velocity", "card advantage", "card flow"),
        "protection": ("protection", "resilience"),
        "competitive": ("cedh", "tournament", "competitive"),
    }
    for priority, terms in priority_terms.items():
        if any(affirmative(term) for term in terms) and priority not in priorities:
            priorities.append(priority)

    if "budget" in text or result.get("budget_mode") in {"strict", "target"}:
        experiences.append("budget") if "budget" not in experiences else None
    for tag, terms in {
        "political": ("political", "group hug"),
        "chaotic": ("chaotic",),
        "jank": ("jank", "joke"),
        "flavor_first": ("flavor", "bad santa"),
        "cedh": ("cedh",),
        "tournament": ("tournament",),
        "high_power": ("high-power", "high power"),
        "casual": ("casual",),
    }.items():
        if any(affirmative(term) for term in terms) and tag not in experiences:
            experiences.append(tag)

    if "typal_core" in constraints and "typal" not in priorities:
        priorities.append("typal")
    if "spell_density" in constraints and "spell_chain" not in priorities:
        priorities.append("spell_chain")
    if "intentional_jank" in constraints and "jank" not in experiences:
        experiences.append("jank")
    if "flavor_first" in constraints and "flavor_first" not in experiences:
        experiences.append("flavor_first")
    if result.get("optimization_mode") == "competitive":
        if "competitive" not in priorities:
            priorities.append("competitive")
        if "high_power" not in experiences:
            experiences.append("high_power")

    if "go_wide" in priorities and "closer" not in protected_roles:
        protected_roles.append("closer")
    if "mana_fixing" in priorities and "mana_fixing" not in protected_roles:
        protected_roles.append("mana_fixing")
    if "permanent_engine" in priorities and "engine" not in protected_roles:
        protected_roles.append("engine")

    if result.get("power_outlier_policy") == "auto":
        result["power_outlier_policy"] = (
            "preserve"
            if (result.get("power_level_max") or 10) <= 4
            or bool({"intentional_jank", "flavor_first"} & constraints)
            or (
                result.get("optimization_mode") == "preserve"
                and bool({"politics", "donation"} & set(priorities))
            )
            else "allow"
        )
    if result.get("generic_staple_tolerance") == "auto":
        result["generic_staple_tolerance"] = (
            "low"
            if bool({"politics", "donation"} & set(priorities))
            or bool({"intentional_jank", "flavor_first"} & constraints)
            else "high"
            if result.get("optimization_mode") == "competitive"
            else "normal"
        )

    result["strategy_priorities"] = priorities
    result["experience_tags"] = list(dict.fromkeys(experiences))
    result["protected_roles"] = protected_roles
    return result


def build_budget_context(
    cards: List[Mapping],
    profile: Optional[Mapping],
) -> Dict:
    """Build a soft total-deck budget model without pretending prices are exact."""
    normalized = normalize_intent_profile(profile)
    limit = _optional_float(normalized.get("budget_limit_usd"))
    known_prices = []
    for card in cards:
        price = _optional_float(card.get("price"))
        if price is None and isinstance(card.get("prices"), Mapping):
            price = _optional_float(card["prices"].get("usd"))
        if price is not None:
            known_prices.extend([price] * max(1, int(card.get("qty", 1) or 1)))
    estimated_current = round(sum(known_prices), 2) if known_prices else None
    experience_tags = set(normalized.get("experience_tags") or [])
    proxy_card_target = None
    if (
        limit is None
        and "budget" in experience_tags
        and normalized.get("budget_mode") in {"strict", "target"}
    ):
        # A deck described only as "budget" still needs a bounded ranking
        # signal. This is deliberately a soft, disclosed proxy rather than a
        # claim about the deck's total price.
        proxy_card_target = 10.0
    return {
        "mode": normalized.get("budget_mode"),
        "limit_usd": limit,
        "estimated_current_usd": estimated_current,
        "known_price_count": len(known_prices),
        "soft_card_share": 0.04,
        "portfolio_share": 0.25,
        "proxy_card_target_usd": proxy_card_target,
    }


def protected_card_names(profile: Mapping) -> set[str]:
    names = {
        str(name).strip().casefold()
        for name in profile.get("protected_cards", [])
        if str(name).strip()
    }
    for package in profile.get("protected_packages", []):
        package_value = (
            package.model_dump()
            if isinstance(package, ProtectedPackage)
            else package
        )
        if not isinstance(package_value, Mapping):
            continue
        names.update(
            str(name).strip().casefold()
            for name in package_value.get("cards", [])
            if str(name).strip()
        )
    return names


def is_cut_protected(card_name: str, profile: Optional[Mapping]) -> bool:
    if not profile:
        return False
    return card_name.strip().casefold() in protected_card_names(profile)


def apply_intent_to_suggestion(
    suggestion: Mapping,
    card_data: Mapping,
    profile: Optional[Mapping],
    budget_context: Optional[Mapping] = None,
    power_outlier: bool = False,
) -> Optional[Dict]:
    """Filter or annotate one addition using only declared deterministic rules."""
    result = dict(suggestion)
    if profile is None:
        return result
    normalized = normalize_intent_profile(profile)
    name = str(result.get("card_name") or card_data.get("name") or "").strip()
    name_key = name.casefold()
    oracle_text = str(card_data.get("oracle_text") or "").casefold()
    cmc = float(result.get("cmc") or card_data.get("cmc") or 0)
    constraints = set(normalized["intentional_constraints"])
    excluded = {
        str(card).strip().casefold()
        for card in normalized["excluded_cards"]
    }
    if name_key in excluded:
        return None
    if power_outlier and normalized.get("power_outlier_policy") == "preserve":
        return None
    if "no_fast_mana" in constraints and _is_fast_mana(
        name_key,
        oracle_text,
        cmc,
    ):
        return None
    if "no_tutors" in constraints and _is_nonland_tutor(oracle_text):
        return None

    alignments: List[str] = []
    warnings: List[str] = []
    evidence_tags = set(result.get("evidence_tags") or [])
    penalty_tags = set(result.get("penalty_tags") or [])
    score_delta = 0
    confidence_cap = 1.0
    price = _optional_float(result.get("price"))
    max_price = normalized.get("max_card_price_usd")
    budget_mode = normalized["budget_mode"]

    if max_price is not None:
        max_price = float(max_price)
        if price is None:
            if budget_mode == "strict":
                return None
            warnings.append("Current price was unavailable for the declared card cap")
            confidence_cap = min(confidence_cap, 0.64)
        elif price > max_price:
            if budget_mode == "strict":
                return None
            penalty = 18 if budget_mode == "target" else 8
            score_delta -= penalty
            penalty_tags.add(
                "over_budget_target"
                if budget_mode == "target"
                else "over_budget_flexible"
            )
            confidence_cap = min(confidence_cap, 0.62)
            warnings.append(
                f"Current price exceeds the declared ${max_price:.2f} card target"
            )
        else:
            alignments.append(f"Within the declared ${max_price:.2f} card cap")
            evidence_tags.add("declared_budget_fit")

    total_budget = _optional_float((budget_context or {}).get("limit_usd"))
    if total_budget is not None and price is not None and total_budget > 0:
        budget_ratio = price / total_budget
        result["budget_limit_usd"] = total_budget
        result["budget_ratio"] = round(budget_ratio, 4)
        result["budget_portfolio_share"] = float(
            (budget_context or {}).get("portfolio_share") or 0.25
        )
        if budget_ratio <= float((budget_context or {}).get("soft_card_share") or 0.04):
            score_delta += 5
            evidence_tags.add("total_budget_fit")
            alignments.append(
                f"Uses about {budget_ratio:.0%} of the declared deck budget"
            )
        elif budget_ratio <= 0.08:
            score_delta -= 5
            penalty_tags.add("total_budget_pressure")
        elif budget_ratio <= 0.15:
            score_delta -= 14
            penalty_tags.add("total_budget_outlier")
            confidence_cap = min(confidence_cap, 0.64)
            warnings.append(
                f"Current price uses about {budget_ratio:.0%} of the declared deck budget"
            )
        else:
            score_delta -= 28
            penalty_tags.add("total_budget_outlier")
            confidence_cap = min(confidence_cap, 0.52)
            warnings.append(
                f"Current price uses about {budget_ratio:.0%} of the declared deck budget"
            )

    proxy_target = _optional_float(
        (budget_context or {}).get("proxy_card_target_usd")
    )
    if (
        total_budget is None
        and proxy_target is not None
        and proxy_target > 0
    ):
        result["budget_proxy_card_target_usd"] = proxy_target
        if price is None:
            if budget_mode == "strict":
                return None
            score_delta -= 22
            penalty_tags.add("implicit_budget_unpriced")
            confidence_cap = min(confidence_cap, 0.56)
            warnings.append(
                "Current price is unavailable for a budget profile without a numeric cap"
            )
        elif price <= proxy_target:
            score_delta += 3
            evidence_tags.add("implicit_budget_fit")
            alignments.append(
                f"Within the ${proxy_target:.0f} soft card-price proxy used because no numeric budget was supplied"
            )
        elif price <= proxy_target * 2:
            score_delta -= 14
            penalty_tags.add("implicit_budget_pressure")
            confidence_cap = min(confidence_cap, 0.66)
            warnings.append(
                f"Current price exceeds the ${proxy_target:.0f} soft proxy for a budget profile without a numeric cap"
            )
        else:
            score_delta -= 30
            penalty_tags.add("implicit_budget_outlier")
            confidence_cap = min(confidence_cap, 0.54)
            warnings.append(
                f"Current price is a major outlier against the ${proxy_target:.0f} soft proxy for this budget profile"
            )
    confirmed = bool(normalized["confirmed"])
    optimization_mode = normalized["optimization_mode"]
    if confirmed:
        alignments.append(f"Evaluated for {optimization_mode} mode")
        evidence_tags.add("declared_intent_fit")
    else:
        score_delta -= 4
        confidence_cap = min(confidence_cap, 0.68)
        warnings.append(
            "Deck intent is unconfirmed; budget, power, and protected packages "
            "may still change this choice"
        )
        penalty_tags.add("intent_unconfirmed")

    priority_roles = {
        "typal": {"typal"},
        "go_wide": {"tokens", "attack_triggers", "combat_damage"},
        "spell_chain": {"instant_sorcery", "target_spells"},
        "donation": {"donation", "temporary_drawback", "forced_reanimation"},
        "politics": {"donation", "goad"},
        "graveyard_recursion": {"graveyard", "recursion", "sacrifice"},
        "permanent_engine": {"artifact", "enchantment", "graveyard"},
        "blink": {"blink"},
        "voltron": {"voltron", "enchantment"},
        "compact_wins": {"compact_win", "tutor"},
        "stack_interaction": {"interaction", "counter", "protection"},
        "mana_fixing": {"ramp", "mana_base_optimization"},
        "combat_combo": {"extra_combat", "attack_triggers", "compact_win"},
        "card_velocity": {"draw"},
        "protection": {"protection"},
    }
    role_tag = str(result.get("role_tag") or "")
    matched_priorities = [
        priority
        for priority in normalized.get("strategy_priorities") or []
        if role_tag in priority_roles.get(priority, set())
    ]
    if matched_priorities:
        score_delta += 8
        evidence_tags.add("declared_strategy_priority")
        alignments.append(
            "Advances declared "
            + ", ".join(priority.replace("_", " ") for priority in matched_priorities)
            + " priority"
        )

    high_power_target = (
        (normalized.get("power_level_min") or 0) >= 7
        or "high_power" in set(normalized.get("experience_tags") or [])
    )
    if (
        high_power_target
        and role_tag == "ramp"
        and "basic land card" in oracle_text
        and "sacrifice" in oracle_text
        and "tapped" in oracle_text
    ):
        score_delta -= 18
        confidence_cap = min(confidence_cap, 0.66)
        penalty_tags.add("high_power_tempo_mismatch")
        warnings.append(
            "The multi-step tapped-land ramp is slow for the declared high-power target"
        )

    direct_plan_evidence = bool(evidence_tags & {
        "direct_synergy",
        "commander_theme_match",
        "archetype_need_match",
        "existing_deck_theme",
        "declared_package_fit",
        "competitive_evidence",
        "declared_strategy_priority",
    })
    if (
        confirmed
        and normalized.get("generic_staple_tolerance") == "low"
        and _is_generic_role_suggestion(result)
        and not direct_plan_evidence
    ):
        return None

    competitive = (
        optimization_mode == "competitive"
        or (normalized.get("power_level_min") or 0) >= 9
    )
    if competitive:
        alternate_cost = _has_alternate_cost(oracle_text)
        evidence = set(result.get("evidence_tags") or [])
        direct_plan = bool(evidence & {
            "direct_synergy",
            "commander_theme_match",
            "archetype_need_match",
        })
        if alternate_cost or (
            cmc <= 2
            and (_is_generic_role_suggestion(result) or direct_plan)
        ):
            score_delta += 8
            alignments.append("Clears the declared competitive efficiency bar")
            evidence_tags.add("competitive_efficiency_fit")
        elif (
            cmc > 3
            and _is_generic_role_suggestion(result)
            and not alternate_cost
        ):
            penalty = 14 if cmc > 4 else 8
            score_delta -= penalty
            confidence_cap = min(confidence_cap, 0.66 if cmc > 4 else 0.72)
            warnings.append(
                "High mana value for the declared competitive target without "
                "an identified alternate cost"
            )
            penalty_tags.add("competitive_curve_mismatch")
        deterministic_competitive = alternate_cost or (
            cmc <= 1
            and any(
                phrase in oracle_text
                for phrase in (
                    "counter target spell",
                    "exile target spell",
                    "destroy target",
                    "exile target permanent",
                    "protection from",
                )
            )
        )
        if not deterministic_competitive and not evidence_tags & {
            "competitive_evidence",
            "free_interaction",
            "compact_win_component",
            "competitive_enabler",
            "competitive_card_advantage",
        }:
            confidence_cap = min(confidence_cap, 0.62)
            penalty_tags.add("missing_competitive_evidence")
            warnings.append(
                "No curated competitive function or compatible compact-package evidence was identified"
            )

    low_power_preservation = (
        (normalized.get("power_level_max") or 10) <= 4
        or bool({"intentional_jank", "flavor_first"} & constraints)
    )
    if low_power_preservation:
        if confirmed and optimization_mode == "preserve" and not evidence_tags & {
            "direct_synergy",
            "commander_theme_match",
            "archetype_need_match",
            "existing_deck_theme",
        }:
            return None
        confidence_cap = min(confidence_cap, 0.70)
        alignments.append("Preserves a deliberately lower-power experience")

    result["score"] = min(100, max(0, int(result.get("score") or 0) + score_delta))
    result["confidence"] = round(
        min(float(result.get("confidence") or 0), confidence_cap),
        2,
    )
    result["intent_alignment"] = alignments
    result["intent_warnings"] = warnings
    result["intent_score_delta"] = score_delta
    result["strategy_priorities"] = list(normalized.get("strategy_priorities") or [])
    result["experience_tags"] = list(normalized.get("experience_tags") or [])
    result["generic_staple_tolerance"] = normalized.get("generic_staple_tolerance")
    result["optimization_mode"] = normalized.get("optimization_mode")
    result["evidence_tags"] = sorted(evidence_tags)
    result["penalty_tags"] = sorted(penalty_tags)
    result["reason"] = _append_reason(
        str(result.get("reason") or ""),
        _intent_reason(normalized, alignments, warnings),
    )
    return result


def apply_intent_to_cuts(
    cuts: List[Mapping],
    profile: Optional[Mapping],
) -> List[Dict]:
    """Apply abstention and confidence policy after protected cuts are removed."""
    if profile is None:
        return [dict(cut) for cut in cuts]
    normalized = normalize_intent_profile(profile)
    constraints = set(normalized["intentional_constraints"])
    confirmed = bool(normalized["confirmed"])
    mode = normalized["optimization_mode"]

    if confirmed and mode == "preserve" and {
        "intentional_jank",
        "flavor_first",
    } & constraints:
        return []

    limit = {
        "preserve": 3,
        "tune": 10,
        "competitive": 10,
        "repair": 6,
    }[mode]
    confidence_cap = {
        "preserve": 0.64,
        "tune": 0.78,
        "competitive": 0.80,
        "repair": 0.72,
    }[mode]
    warning = None
    if not confirmed:
        limit = min(limit, 2)
        confidence_cap = min(confidence_cap, 0.48)
        warning = "Cut confidence is reduced until deck intent is confirmed"

    results = []
    for cut in cuts[:limit]:
        row = dict(cut)
        row["confidence"] = round(
            min(float(row.get("confidence") or 0), confidence_cap),
            2,
        )
        row["intent_alignment"] = [f"Evaluated for {mode} mode"] if confirmed else []
        row["intent_warnings"] = [warning] if warning else []
        if warning:
            row["reason"] = _append_reason(str(row.get("reason") or ""), warning + ".")
        results.append(row)
    return results


def intent_summary(profile: Optional[Mapping]) -> Dict:
    normalized = normalize_intent_profile(profile)
    constraints = list(normalized["intentional_constraints"])
    enforcement_notes = []
    if (
        normalized.get("budget_limit_usd") is not None
        and normalized.get("max_card_price_usd") is None
    ):
        enforcement_notes.append(
            "The total budget applies a soft per-card and recommendation-portfolio "
            "pressure model; only a declared per-card cap is a hard filter."
        )
    if "no_infinite_combos" in constraints:
        enforcement_notes.append(
            "Generated combo lines are suppressed; deterministic dependency "
            "checks do not claim to detect emergent infinite interactions."
        )
    power_min = normalized.get("power_level_min")
    power_max = normalized.get("power_level_max")
    if power_min is None and power_max is None:
        power = "unknown"
    elif power_min == power_max:
        power = str(power_min)
    else:
        power = f"{power_min or '?'}-{power_max or '?'}"
    return {
        "confirmed": normalized["confirmed"],
        "optimization_mode": normalized["optimization_mode"],
        "power_target": power,
        "budget_mode": normalized["budget_mode"],
        "budget_limit_usd": normalized.get("budget_limit_usd"),
        "max_card_price_usd": normalized.get("max_card_price_usd"),
        "primary_strategy": normalized.get("primary_strategy"),
        "desired_experience": normalized.get("desired_experience"),
        "strategy_priorities": list(normalized.get("strategy_priorities") or []),
        "experience_tags": list(normalized.get("experience_tags") or []),
        "protected_roles": list(normalized.get("protected_roles") or []),
        "power_outlier_policy": normalized.get("power_outlier_policy"),
        "generic_staple_tolerance": normalized.get("generic_staple_tolerance"),
        "protected_card_count": len(protected_card_names(normalized)),
        "excluded_card_count": len(normalized["excluded_cards"]),
        "intentional_constraints": constraints,
        "enforcement_notes": enforcement_notes,
        "recommendation_posture": (
            normalized["optimization_mode"] if normalized["confirmed"]
            else "conservative-unconfirmed"
        ),
    }


def _clean_unique_strings(values: List[str], limit: int) -> List[str]:
    results = []
    seen = set()
    for value in values:
        cleaned = " ".join(str(value).split())
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        results.append(cleaned)
        if len(results) >= limit:
            break
    return results


def _optional_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_fast_mana(name: str, oracle_text: str, cmc: float) -> bool:
    known = {
        "chrome mox",
        "cryptolith fragment",
        "jeweled lotus",
        "lion's eye diamond",
        "lotus petal",
        "mana crypt",
        "mana vault",
        "mox amber",
        "mox diamond",
        "mox opal",
    }
    if name in known:
        return True
    if cmc > 1 or "add" not in oracle_text:
        return False
    return any(phrase in oracle_text for phrase in [
        "add {c}{c}",
        "add three mana",
        "add two mana",
        "sacrifice this artifact: add",
    ])


def _is_nonland_tutor(oracle_text: str) -> bool:
    if "search your library" not in oracle_text:
        return False
    return not any(phrase in oracle_text for phrase in [
        "basic land card",
        "land card",
        "plains card",
        "island card",
        "swamp card",
        "mountain card",
        "forest card",
    ])


def _is_generic_role_suggestion(suggestion: Mapping) -> bool:
    return str(suggestion.get("role_tag") or "") in {
        "draw",
        "ramp",
        "removal",
        "sweeper",
        "interaction",
        "protection",
    }


def _has_alternate_cost(oracle_text: str) -> bool:
    return any(phrase in oracle_text for phrase in [
        "rather than pay this spell's mana cost",
        "rather than pay its mana cost",
        "without paying its mana cost",
        "you may pay 0 rather than",
    ])


def _intent_reason(
    profile: Mapping,
    alignments: List[str],
    warnings: List[str],
) -> str:
    if warnings:
        return "Intent check: " + "; ".join(warnings) + "."
    if alignments:
        return "Intent check: " + "; ".join(alignments) + "."
    return f"Intent check: evaluated for {profile['optimization_mode']} mode."


def _append_reason(existing: str, note: str) -> str:
    if not existing:
        return note
    return f"{existing} {note}"
