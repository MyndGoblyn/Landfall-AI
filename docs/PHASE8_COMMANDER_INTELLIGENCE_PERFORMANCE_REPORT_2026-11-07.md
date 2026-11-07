# Phase 8 Commander Intelligence and Performance Report — 2026-11-07

## Decision

Phase 8 satisfies its local release-candidate gates for commander-profile speed,
theme precision, recommendation quality, and non-regression. The implementation
is ready for production deployment and live latency verification.

Engineering confidence that this release improves the covered commander
experience without weakening the established deck-analysis path is **0.92**.
The remaining uncertainty is production network and database latency, not a
known deterministic-quality failure.

## What changed

### Retrieval and execution speed

- The local 39,287-card catalog is sorted once and can resolve all planned
  queries in one pass. It no longer scans and sorts the entire catalog once per
  recommendation lane.
- Candidate providers expose a batch path. The live fallback is used only for
  individual queries that the local catalog cannot satisfy.
- Mechanics-registry patterns and requirement variants are compiled once when
  the registry loads rather than normalized and compiled for every card.
- Commander profiles expose `Server-Timing` stages and an
  `X-Landfall-Profile-Cache` layer header.
- A versioned Mongo profile cache survives API restarts. Its identity includes
  Oracle text, catalog version, semantic version, ranker, planner, analysis
  depth, and the Phase 8 cache schema. Process memory remains the first layer.
  Cache failures fall back to computation and never block analysis.

### Theme precision

- Commander themes now carry structured `primary`, `supporting`, or
  `incidental` evidence, with a reason and evidence source.
- Only primary and supporting themes drive recommendation searches. Incidental
  text remains inspectable but cannot become the displayed game plan.
- Reviewed profiles supplement evidence but do not promote an otherwise
  incidental keyword by themselves.
- Primary-theme candidates are selected before supporting-theme candidates.
  Four of five visible slots are reserved for the commander's plan when four
  qualified plan cards exist; at most one generic support card then fills the
  remaining slot.
- Per-theme shortlists preserve distinct card jobs before adding repeated jobs.
  This prevents a spellslinger profile from returning only the first three
  popular cantrips.

### Recommendation accuracy and explanations

- Sacrifice cards are classified as repeatable outlets, mana-free outlets,
  one-shot sacrifice costs, death payoffs, or fodder. One-shot draw spells are
  no longer described as reusable outlets in commander profiles.
- Recommendation output includes a structured reason ledger: card job,
  commander theme, theme tier, rules-text evidence, lane, and limitations.
- Public explanations no longer contain `V2 selection`, rank positions,
  component scores, `Portfolio fit`, or measured-optimizer language.
- Commander-plan and general-support cards are visibly separated. Internal
  numeric scores, raw mechanic labels, and raw evidence tokens are no longer
  presented as user-facing reasons.

### Coverage and interface behavior

- The large “unreviewed profile” warning was removed. Oracle-text profiles are
  normal product output, not an error state.
- Partial coverage no longer creates a blanket warning. A compact limitation is
  shown only when no reliable build-around theme clears the evidence floor.
- The synergy panel presents primary plans and supporting themes with the
  reason each classification was earned.

## Measured evidence

### Local commander-profile benchmark

Ten cold, uncached profiles were measured against the November 5 catalog:

| Metric | Result |
| --- | ---: |
| Median | 383 ms |
| Observed p95 | 592 ms |
| Maximum | 592 ms |
| Profiles over 750 ms | 0 / 10 |
| Internal ranker jargon detected | 0 / 10 |

The set covered Meren, Vadrik, Najeela, Muldrotha, Light-Paws, Talrand,
Zedruu, Lathril, Yuriko, and Urza. Later primary-theme quota checks remained
under the 750 ms local target. A process-cold Meren profile measured 422 ms;
after clearing process memory, the same result loaded from the persistent
cache in under 1 ms in the in-memory database harness. Production Mongo timing
must be verified after deployment.

Earlier cold spot checks were approximately 0.83–1.57 seconds, so the current
local results are materially faster without reducing query breadth, legality,
evidence, or confidence checks.

### Full commander-catalog audit

The eligible catalog contains 3,470 commanders.

| Profile classification | Before | Phase 8 |
| --- | ---: | ---: |
| Deep/direct plan | 38 | 2,728 |
| Partial/supporting | 2,207 | 367 |
| Exploratory/no reliable plan | 1,225 | 375 |

All 15 reviewed profiles that match an eligible catalog commander now classify
as direct-plan profiles. The audit also found 1,154 incidental theme signals;
those remain available as evidence but are prevented from driving the plan.
There are 465 honest no-actionable-theme cases. This increase from the old
zero-theme count is intentional precision: weak keyword matches are now
abstentions instead of false plans.

The previous UI showed a warning for every partial or exploratory result—3,432
of 3,470 commanders. Phase 8 limits that warning to the 375 exploratory cases.

## Non-regression evidence

- Backend suite: **287/287 passed**.
- Phase 8 focused commander-quality gates: sacrifice taxonomy, theme
  centrality, explanation language, lane quotas, and exact batch retrieval all
  pass.
- Frontend production build: **compiled successfully**.
- Frontend source smoke suite: **17/17 groups passed**.
- Complete constructor: **26/26 cases passed**, including all negative controls
  and counterfactual contracts.
- Fresh 18-deck run: snapshot integrity and all input expectations passed.
- Compared with the Phase 7 release artifact, legacy, V2, and V3 additions,
  cuts, and swaps are exact in all **18/18** cases.

The real-deck comparison caught an early scope leak during implementation:
commander-only semantics briefly affected five imported-deck portfolios. Those
classifiers are now explicitly scoped to commander profiles, and the final
matrix is exact. This is why the release confidence is evidence-based rather
than inferred from unit tests alone.

## Rollback boundaries

- `COMMANDER_PROFILE_CACHE_ENABLED=false` disables persistent profile caching;
  computation and the process-memory cache remain available.
- Candidate-provider batch failure automatically reverts to the existing
  bounded per-query path.
- Imported-deck analysis retains the Phase 7 coverage, selection, and role
  contracts. Phase 8 theme centrality and precise sacrifice roles are opt-in
  only on commander profiles.
- The new UI consumes additive fields and keeps fallbacks for older profile
  responses.

## Production acceptance checks

After deployment:

1. Measure cold and warm `Server-Timing` for the ten-commanders set.
2. Confirm memory and persistent cache headers and automatic invalidation after
   a semantic or catalog version change.
3. Visually inspect Meren, Vadrik, Najeela, Talrand, Zedruu, and one deliberately
   ambiguous commander on desktop and mobile.
4. Confirm no recommendation card shows internal ranker or portfolio jargon.
5. Confirm the 18-deck and 26-build matrices remain green from the deployed
   release revision.
