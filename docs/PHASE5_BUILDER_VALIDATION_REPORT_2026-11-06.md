# Phase 5 Builder Validation Report — 2026-11-06

## Decision

**Complete-draft construction satisfies the Phase 5 controlled-promotion
gate.** The release-candidate run passes all 26 reviewed cases, all five
negative controls, and all seven counterfactual expectations without lowering
the per-card or portfolio confidence floors.

The constructor may now be promoted through its independent runtime flag. The
existing public analysis and suggestion path remains unchanged: all 18 frozen
real-deck fixtures exactly match the previously promoted V3 additions, cuts,
and swap ordering.

Engineering confidence that the complete constructor meets the covered
quality, versatility, and abstention goals is **0.93**. This is an engineering
assessment over the frozen validation matrix, not a statistical guarantee for
every Commander, card release, or intent combination.

## Reproducible run

- Suite: `tests/fixtures/golden_builder_validation.json`
- Frozen catalog: 39,287 cards
- Catalog version: `oracle_cards:2026-11-05T10:02:05.865+00:00`
- Constructor: `deterministic-constructor-v2`
- Release-candidate artifact:
  `test_reports/phase5-builder-release-candidate.json` (intentionally ignored)

```powershell
.\.venv\Scripts\python.exe backend\scripts\run_builder_validation.py `
  --output test_reports\phase5-builder-release-candidate.json
```

## Coverage and result

The matrix covers aggro, artifacts, budget, cEDH, colorless, combo, control,
enchantments, expensive commanders, five-color decks, graveyard decks,
high-power decks, intentional jank, lands, partner/background pairs, politics,
spellslinger, typal, unusual mana bases, value, and Voltron.

- 20 expected complete drafts: **20 passed at exactly 99 main-deck cards**.
- Five impossible or insufficient-input negative controls: **five passed with
  the required abstain or blocked state**.
- Intentional-jank Zedruu: **passed by preserving the premise and abstaining
  from blind optimization**.
- Seven explicit counterfactual expectations: **seven passed**.
- Reason-ledger coverage: **100% in every evaluated result**.
- Evidence-ledger coverage: **100% in every evaluated result**.

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

## Changes that closed the calibration gaps

- Construction can use exact-oracle-ID reviewed commander profiles as
  corroborating evidence. A card still has to match the same semantic plan
  lane independently; the profile cannot manufacture card fit.
- Reviewed coverage now includes 16 commanders, including Tatyova, Kozilek,
  and Sythis for the remaining lands, colorless-big-mana, and enchantress
  construction gaps.
- The curated competitive-function registry contains 120 verified entries for
  complete construction, including exact commander-gated Yuriko, Vadrik, and
  Najeela packages. The public suggestion path remains frozen to its promoted
  48-card registry view.
- Positive construction invariant alignment and measured role-gap repair are
  explicit evidence classes. Negative invariant mismatches keep the existing
  conservative cap.
- Construction-only ramp retrieval recognizes explicit mana production in
  addition to land search and Treasure text. Public query behavior is
  unchanged.
- Complete construction reserves its final candidate capacity for unresolved
  draw, ramp, and interaction floors, preventing theme cards from crowding out
  structural deck needs.
- Intentional-jank and flavor-first builds do not receive the construction
  evidence expansion, preserving the established abstention behavior.

## Unchanged quality boundaries

- Every complete-draft card must clear the **0.68** evidence floor.
- The complete Planner portfolio must average at least **0.72** confidence.
- Legality, commander eligibility, partner/background pairing, color identity,
  singleton, exact deck count, mana, strict budget, protected and excluded
  cards, and owned-only collection constraints remain hard gates.
- Unresolved slots remain visible when no candidate clears every gate.
- The constructor cannot self-certify; the independent evaluator owns the
  promotion decision.

## Non-regression verification

- Full backend suite: **275 passed**.
- Frozen public real-deck validation: **18/18 fixture integrity checks and
  input expectations passed**.
- Public Planner V3 additions, cuts, and swap ordering: **exact match in all
  18 cases** against
  `test_reports/real_deck_validation_v3_release_candidate.json`.
- Complete-constructor matrix: **26/26 passed**, with no failed or missing
  counterfactual result.

## Production promotion

The controlled runtime change from `BUILD_CONSTRUCTOR_MODE=scaffold` to
`BUILD_CONSTRUCTOR_MODE=complete` was completed on 2026-11-06. Production
loaded and verified semantic bundle
`semantic:4d7560cdb28bd3015e8b0e09f9337efd8bbfe221c3c712fb47c16f408aa4b482`
with 120 construction-registry cards and 16 reviewed commander profiles. The
public API reports `complete_drafts_enabled: true`, and both the API health
check and Cloudflare-hosted frontend return successfully.

The flag remains independently reversible; changing it does not alter the
served deck-analysis recommendation path.
