# Phase 5 Builder Validation Report — 2026-11-06

## Decision

**Complete-draft construction is not promoted.** Production remains on the
validated bounded scaffold. The new Phase 5 gate correctly refuses to turn a
partial high-confidence portfolio into a complete deck by inserting weakly
supported filler.

The first full calibration passed 7 of 26 cases. After adding staged candidate
depth, iterative re-analysis, plan-specific expansion, mana reservation, and
independent quality checks, the final run passes 13 of 26 cases. This is useful
progress, but the promotion contract requires every reviewed case and every
counterfactual check to pass.

## Reproducible run

- Suite: `tests/fixtures/golden_builder_validation.json`
- Frozen catalog: 39,287 cards
- Catalog version: `oracle_cards:2026-11-05T10:02:05.865+00:00`
- Constructor: `deterministic-constructor-v2`
- Raw artifact: `test_reports/phase5-builder-report.json` (intentionally ignored)

```powershell
.\.venv\Scripts\python.exe backend\scripts\run_builder_validation.py `
  --output test_reports\phase5-builder-report.json
```

## Coverage and result

The reviewed matrix contains 26 cases, four counterfactual pairs, five negative
controls, and every required archetype or edge tag. Thirteen cases pass and
thirteen fail. All five negative controls and all seven explicit
counterfactual checks pass.

Passing cases:

- B01 — strict-budget Meren graveyard value
- B02 — high-power Meren combo
- B03 — target-budget Yuriko tempo
- B06 — intentional-jank Zedruu correctly abstains
- B12 — Lathril Elf typal
- B14 — Wilhelt Zombie aristocrats
- B17 — Wilson and Noble Heritage partner/background
- B21 — impossible strict budget correctly abstains
- B22 — flexible-budget Meren
- B23 — insufficient owned pool correctly abstains
- B24 — impossible protected color identity correctly blocks
- B25 — illegal commander correctly blocks
- B26 — protected package over strict budget correctly blocks

Counterfactual results:

| Baseline | Variant | Requirement | Result |
| --- | --- | --- | --- |
| B02 | B01 | Lower-budget variant costs less | Pass |
| B01 | B02 | Power intent changes the portfolio | Pass |
| B01 | B02 | The shared core remains stable | Pass |
| B03 | B04 | cEDH intent changes the portfolio | Pass |
| B03 | B04 | The shared Yuriko core remains stable | Pass |
| B05 | B06 | Intentional jank changes the portfolio | Pass |
| B22 | B21 | Impossible strict budget costs less and abstains | Pass |

## Remaining promotion blockers

| Case | Result | Primary blocker |
| --- | ---: | --- |
| B04 cEDH Yuriko | 78/99 | Curated competitive pool lacks card-flow and ramp depth |
| B05 political Zedruu | 84/99 | Average Planner confidence is 0.69, below 0.72 |
| B07 Vadrik storm | 75/99 | Competitive spell-chain pool lacks card-flow depth |
| B08 cEDH Najeela | 78/99 | Competitive pool lacks card-flow and ramp depth |
| B09 optimized Muldrotha | 83/99 | Graveyard plan pool is not deep enough |
| B10 Light-Paws | 52/99 | Aura-specific support, card flow, and ramp are under-covered |
| B11 Talrand | 74/99 | Spell-density-compatible ramp is under-covered |
| B13 Krenko | 88/99 | Goblin package depth is incomplete |
| B15 Atraxa blink | 50/99 | Blink semantic coverage and interaction evidence are inadequate |
| B16 Kozilek | 95/99 | Colorless big-mana package is four qualified cards short |
| B18 Sythis | 87/99 | Average Planner confidence is 0.71, below 0.72 |
| B19 Tatyova | 71/99 | Landfall/value package depth is incomplete |
| B20 Breya | 71/99 | Artifact-combo package depth is incomplete |

These are semantic and curated-evidence gaps. Increasing loop counts or
lowering confidence thresholds would hide the problem and is not an acceptable
promotion strategy.

## Implemented Phase 5 controls

- A separate evaluator now owns promotion, so constructor success cannot
  self-certify release readiness.
- Every complete card requires a reason, evidence ledger, and Planner V3
  confidence; individual complete-draft cards must clear 0.68 and the complete
  portfolio must average at least 0.72.
- Complete construction re-analyzes after accepted portfolios and reserves the
  measured mana floor before accepting more nonlands.
- Candidate depth is staged: the calibrated suggestion depth builds the first
  shell, and only incomplete complete drafts may inspect a deeper frozen pool.
  The normal suggestion endpoint keeps its existing search and result limits.
- Legality, singleton, exact deck count, mana, strict budget, protected and
  excluded cards, and owned-only collection constraints are hard gates.
- Intentional jank, impossible requests, and incomplete owned pools are allowed
  to abstain instead of being blindly optimized.
- Counterfactual release checks now measure requested direction and unrelated
  portfolio instability.

## Non-regression verification

- Full backend suite: **266 passed**.
- Existing frozen real-deck validation: input expectations and fixture
  integrity pass for all 18 cases.
- Planner V3 addition portfolios are an exact card-for-card, order-for-order
  match with the previously promoted release-candidate artifact in all 18
  cases.

This confirms that deeper retrieval is isolated to the unpromoted complete
constructor and does not alter the served suggestion path.

## Next implementation target

The next Phase 5 increment should expand the evidence sources rather than the
number of construction passes:

1. Add reviewed competitive-function coverage for card flow, fast mana,
   protection, and commander-specific compact packages.
2. Add package graphs for aura Voltron, blink, colorless big mana, lands,
   artifacts, typal aggro, and spell-chain decks.
3. Teach role scoring to recognize commander-compatible support cards in those
   packages without relaxing the global confidence floor.
4. Re-run the same frozen suite and require 26/26 individual cases plus all
   counterfactual checks before changing `BUILD_CONSTRUCTOR_MODE`.

