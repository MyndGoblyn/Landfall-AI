"""Versioned strategy evidence and balanced candidate-query planning.

The V3 planner deliberately keeps recommendation intent separate from card
ranking.  It converts commander, archetype, deck-gap, and user-intent evidence
into an inspectable profile, then allocates a bounded retrieval budget across
the strongest plan lanes and the most important measured deficiencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


STRATEGY_PROFILE_VERSION = "strategy-profile-v3"
QUERY_PLANNER_VERSION = "balanced-query-planner-v3"


ARCHETYPE_NEED_ROLE_MAP = {
    "backup_engine": "draw",
    "card_advantage": "draw",
    "card_flow": "draw",
    "card_selection": "draw",
    "cheap_protection": "protection",
    "countermagic": "interaction",
    "interaction": "interaction",
    "mana_acceleration": "ramp",
    "mana_efficiency": "ramp",
    "mana_rocks": "ramp",
    "protection": "protection",
    "recursion": "recursion",
    "removal": "removal",
    "sweepers": "sweeper",
}


INTENT_PRIORITY_LANES = {
    "aristocrats": "sacrifice",
    "auras": "voltron",
    "blink": "blink",
    "combat_combo": "attack_triggers",
    "counters": "counters",
    "donation": "donation",
    "go_wide": "tokens",
    "graveyard": "graveyard",
    "landfall": "landfall",
    "politics": "goad",
    "spell_chain": "instant_sorcery",
    "spellslinger": "instant_sorcery",
    "typal": "typal",
    "voltron": "voltron",
}


# Functional gaps are not equally urgent.  Reliable cards and mana determine
# whether the deck can execute any strategy, while sweepers are intentionally
# lower-frequency tools.  This bonus only breaks otherwise comparable measured
# gaps; it does not create a role that the analysis did not identify.
ROLE_IMPORTANCE_BONUS = {
    "draw": 8,
    "ramp": 7,
    "protection": 5,
    "interaction": 4,
    "removal": 3,
    "recursion": 2,
    "sweeper": 0,
}


@dataclass(frozen=True)
class PlanLane:
    id: str
    kind: str
    priority: float
    confidence: float
    sources: Tuple[str, ...]
    evidence: Tuple[str, ...]
    current_count: float = 0.0
    target_count: float = 0.0
    status: str = "active"

    def as_dict(self) -> Dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "priority": round(self.priority, 2),
            "confidence": round(self.confidence, 3),
            "sources": list(self.sources),
            "evidence": list(self.evidence),
            "current_count": round(self.current_count, 2),
            "target_count": round(self.target_count, 2),
            "status": self.status,
        }


@dataclass(frozen=True)
class StrategyProfile:
    version: str
    commander_names: Tuple[str, ...]
    coverage_level: str
    lanes: Tuple[PlanLane, ...]
    intentional_constraints: Tuple[str, ...]
    strategy_priorities: Tuple[str, ...]

    def lane(self, lane_id: str) -> Optional[PlanLane]:
        return next((lane for lane in self.lanes if lane.id == lane_id), None)

    def as_dict(self) -> Dict:
        return {
            "version": self.version,
            "commander_names": list(self.commander_names),
            "coverage_level": self.coverage_level,
            "lanes": [lane.as_dict() for lane in self.lanes],
            "intentional_constraints": list(self.intentional_constraints),
            "strategy_priorities": list(self.strategy_priorities),
        }


@dataclass(frozen=True)
class QuerySpec:
    key: str
    kind: str
    lane: str
    query: str
    ordinal: int

    def as_dict(self) -> Dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "lane": self.lane,
            "ordinal": self.ordinal,
        }


def _number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _confidence_for_coverage(coverage_level: str) -> float:
    return {
        "deep": 0.94,
        "partial": 0.82,
        "exploratory": 0.58,
    }.get(str(coverage_level or "partial").lower(), 0.72)


def build_strategy_profile(
    *,
    commander_names: Sequence[str],
    commander_synergies: Sequence[str],
    commander_archetypes: Sequence[Mapping],
    gaps: Mapping,
    deck_context: Optional[Mapping] = None,
    intent_profile: Optional[Mapping] = None,
    coverage_level: str = "partial",
) -> StrategyProfile:
    """Build an inspectable strategy profile without changing recommendation output."""
    deck_context = deck_context or {}
    intent_profile = intent_profile or {}
    role_quality = deck_context.get("role_quality") or {}
    synergy_counts = deck_context.get("synergy_counts") or {}
    coverage_confidence = _confidence_for_coverage(coverage_level)
    strategy_priorities = tuple(sorted({
        str(value)
        for value in intent_profile.get("strategy_priorities") or []
        if str(value)
    }))
    constraints = tuple(sorted({
        str(value)
        for value in intent_profile.get("intentional_constraints") or []
        if str(value)
    }))

    archetype_rows = [
        archetype for archetype in commander_archetypes or []
        if isinstance(archetype, Mapping)
    ]
    archetype_ids = {
        str(archetype.get("id"))
        for archetype in archetype_rows
        if archetype.get("id")
    }
    archetype_needs = {
        str(need)
        for archetype in archetype_rows
        for need in archetype.get("primary_needs") or []
        if str(need)
    }
    intent_lanes = {
        lane
        for priority in strategy_priorities
        for lane in [INTENT_PRIORITY_LANES.get(priority)]
        if lane
    }

    lanes: Dict[str, PlanLane] = {}
    for index, synergy in enumerate(dict.fromkeys(commander_synergies or [])):
        count = _number(synergy_counts.get(synergy, 0))
        sources = ["commander"]
        evidence = [f"commander plan lane: {synergy.replace('_', ' ')}"]
        priority = 72 - min(index, 8) * 2
        confidence = coverage_confidence
        if archetype_ids:
            sources.append("archetype")
            priority += 4
        if synergy in intent_lanes:
            sources.append("declared_intent")
            evidence.append("matches a declared strategy priority")
            priority += 12
            confidence = max(confidence, 0.9)
        if count >= 3:
            sources.append("deck_evidence")
            evidence.append(f"{int(count)} existing cards match this lane")
            priority += min(8, count)
        status = "established" if count >= 3 else "developing"
        lanes[synergy] = PlanLane(
            id=synergy,
            kind="synergy",
            priority=priority,
            confidence=confidence,
            sources=tuple(dict.fromkeys(sources)),
            evidence=tuple(evidence),
            current_count=count,
            status=status,
        )

    gap_roles = gaps.get("roles") or {}
    for role, requested in gap_roles.items():
        quality = role_quality.get(role) or {}
        target = _number(quality.get("target_min"), 0)
        current = _number(
            quality.get("effective_count"),
            max(0, target - _number(requested)),
        )
        gap = _number(quality.get("effective_gap"), requested)
        pressure = gap / max(target, 1.0) if target else min(1.0, gap / 3.0)
        sources = ["measured_role_gap"]
        evidence = [f"effective {role} gap: {gap:.1f}"]
        priority = (
            78
            + min(18, pressure * 18)
            + ROLE_IMPORTANCE_BONUS.get(role, 1)
            + min(8, gap * 1.5)
        )
        if role in {ARCHETYPE_NEED_ROLE_MAP.get(need) for need in archetype_needs}:
            sources.append("archetype_primary_need")
            evidence.append("matches an archetype primary need")
            priority += 8
        lanes[role] = PlanLane(
            id=role,
            kind="role",
            priority=priority,
            confidence=0.95 if quality else 0.84,
            sources=tuple(sources),
            evidence=tuple(evidence),
            current_count=current,
            target_count=target,
            status="deficient",
        )

    for need in sorted(archetype_needs):
        role = ARCHETYPE_NEED_ROLE_MAP.get(need)
        if not role or role in lanes:
            continue
        lanes[role] = PlanLane(
            id=role,
            kind="role",
            priority=70,
            confidence=0.82,
            sources=("archetype_primary_need",),
            evidence=(f"archetype need: {need.replace('_', ' ')}",),
            status="archetype_need",
        )

    ordered_lanes = tuple(sorted(
        lanes.values(),
        key=lambda lane: (-lane.priority, lane.kind != "role", lane.id),
    ))
    return StrategyProfile(
        version=STRATEGY_PROFILE_VERSION,
        commander_names=tuple(dict.fromkeys(
            str(name).strip() for name in commander_names if str(name).strip()
        )),
        coverage_level=coverage_level,
        lanes=ordered_lanes,
        intentional_constraints=constraints,
        strategy_priorities=strategy_priorities,
    )


class BalancedQueryPlanner:
    """Allocate a fixed search budget across plan and deficiency evidence."""

    VERSION = QUERY_PLANNER_VERSION

    def plan(
        self,
        specs: Sequence[QuerySpec],
        profile: StrategyProfile,
        budget: int,
        *,
        explicit_categories: bool = False,
    ) -> Tuple[List[QuerySpec], Dict]:
        budget = max(0, int(budget))
        deduped: List[QuerySpec] = []
        seen_queries = set()
        for spec in specs:
            normalized_query = " ".join(spec.query.split()).casefold()
            if not normalized_query or normalized_query in seen_queries:
                continue
            seen_queries.add(normalized_query)
            deduped.append(spec)

        legacy = deduped[:budget]
        if budget == 0 or not deduped:
            return [], self._diagnostics(profile, legacy, [], budget)
        if explicit_categories:
            selected = deduped[:budget]
            return selected, self._diagnostics(profile, legacy, selected, budget)

        lane_priorities = {lane.id: lane.priority for lane in profile.lanes}

        def score(spec: QuerySpec) -> tuple:
            base = lane_priorities.get(spec.lane, 50.0)
            if spec.kind == "special":
                base += 40
            elif spec.kind == "role":
                base += 8
            return (-base, spec.ordinal, spec.key)

        special = sorted(
            (spec for spec in deduped if spec.kind == "special"),
            key=score,
        )
        role = sorted(
            (spec for spec in deduped if spec.kind == "role"),
            key=score,
        )
        synergy = sorted(
            (spec for spec in deduped if spec.kind == "synergy"),
            key=score,
        )
        other = sorted(
            (
                spec for spec in deduped
                if spec.kind not in {"special", "role", "synergy"}
            ),
            key=score,
        )

        selected: List[QuerySpec] = []

        def add(spec: QuerySpec):
            if len(selected) < budget and spec not in selected:
                selected.append(spec)

        for spec in special:
            add(spec)

        remaining = budget - len(selected)
        if remaining > 0 and role and synergy:
            role_quota = min(len(role), 2 if remaining >= 4 else 1)
            synergy_quota = min(len(synergy), 2 if remaining >= 3 else 1)
            for spec in role[:role_quota]:
                add(spec)
            for spec in synergy[:synergy_quota]:
                add(spec)

        ranked_all = sorted(
            [*role, *synergy, *other],
            key=score,
        )
        for spec in ranked_all:
            add(spec)

        selected.sort(key=lambda spec: (
            score(spec),
            spec.ordinal,
        ))
        return selected[:budget], self._diagnostics(
            profile,
            legacy,
            selected[:budget],
            budget,
        )

    def _diagnostics(
        self,
        profile: StrategyProfile,
        legacy: Sequence[QuerySpec],
        selected: Sequence[QuerySpec],
        budget: int,
    ) -> Dict:
        legacy_keys = [spec.key for spec in legacy]
        selected_keys = [spec.key for spec in selected]
        return {
            "version": self.VERSION,
            "profile_version": profile.version,
            "budget": budget,
            "legacy_plan": legacy_keys,
            "v3_plan": selected_keys,
            "changed": legacy_keys != selected_keys,
            "added": [key for key in selected_keys if key not in legacy_keys],
            "removed": [key for key in legacy_keys if key not in selected_keys],
            "role_queries": sum(spec.kind == "role" for spec in selected),
            "synergy_queries": sum(spec.kind == "synergy" for spec in selected),
            "special_queries": sum(spec.kind == "special" for spec in selected),
        }


def query_specs_from_pairs(pairs: Iterable[tuple[str, str]]) -> List[QuerySpec]:
    """Convert the legacy `(role, query)` representation without losing order."""
    specs = []
    for ordinal, (role, query) in enumerate(pairs):
        if role.startswith("synergy:"):
            kind = "synergy"
            lane = role.split(":", 1)[1]
        elif role.startswith("competitive:") or role == "mana_fixing":
            kind = "special"
            lane = role.split(":", 1)[-1]
        else:
            kind = "role"
            lane = role
        specs.append(QuerySpec(
            key=role,
            kind=kind,
            lane=lane,
            query=query,
            ordinal=ordinal,
        ))
    return specs
