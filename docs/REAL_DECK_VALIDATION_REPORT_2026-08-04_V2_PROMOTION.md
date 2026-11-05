# V2 Promotion Real-Deck Validation Report

**Evaluation date:** 2026-08-04 (America/New_York)
**Validation set:** 18 immutable Commander snapshots
**Reviewed output:** Evidence Ranker V2, fast/default analysis
**Decision:** **V2 satisfies the controlled-promotion gate.**

## Verdict

The reviewed result is **18 strict passes, 0 partial results, and 0 failures**.
The required threshold is 15 strict passes with no critical negative-control,
intent, cut-safety, or paired-experience failure.

This result supports controlled V2 activation. It does not establish universal
accuracy: the registry and deterministic semantic rules should continue to be
expanded from reviewed production misses, and shadow comparison should remain
available as an immediate rollback path.

Engineering confidence that V2 achieves the requested next-stage goals on the
covered Commander use cases is **0.91**. This is a reasoned engineering rating,
not a statistical probability. The remaining uncertainty comes from archetypes,
new cards, and unusual intent combinations outside this 18-deck set.

## Reproducible evidence

- Catalog: `oracle_cards:2026-07-29T21:02:49.097+00:00` (38,416 cards)
- Raw artifact: `test_reports/real_deck_validation_2026-08-04_v2_promotion_raw.json`
- Raw SHA-256: `00c5f652d972c0dd51407b067201804cc3b7d7c9068895b1c68d9fc85fc55f71`
- Runtime: 62.8 seconds, within the prior run's approximately 62-second envelope
- Compact review: `tests/fixtures/real_deck_validation/2026-08-04/review_results_v2_promotion.json`

Reproduction command:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_real_deck_validation.py `
  --fixture-dir tests\fixtures\real_deck_validation\2026-08-04 `
  --output test_reports\real_deck_validation_2026-08-04_v2_promotion_raw.json
```

## Material improvements verified

- Active commanders and other command-zone cards cannot enter addition pools.
- Alternate casting modes, exact named-counter domains, and actual extra-combat
  text are evaluated through a shared semantic layer.
- Declared closers, combat-copy enablers, mana fixing, typed tutors, political
  defenses, and repeatable engines receive strategic cut protection.
- Desired experience is resolved into bounded strategy priorities, experience
  tags, protected roles, generic-staple tolerance, and power-outlier policy.
- Numeric total-deck budgets affect individual and portfolio ranking. A budget
  profile without a numeric limit uses a disclosed $10 soft per-card proxy;
  missing prices cannot bypass it.
- Competitive suggestions require curated function evidence and compatible
  package prerequisites; low mana value alone is insufficient.
- V2 selects a portfolio rather than five independent maxima, defers budget
  pressure when clean alternatives exist, and lets a close plan-specific card
  lead over a generic role fix.
- Reasons name measured evidence, intent alignment, budget pressure, invariant
  effects, and the strongest V2 ranking component.

## Reviewed deck outcomes

| ID | Deck | Result | Key reviewed behavior |
|---:|---|---|---|
| 01 | Budget Yuriko | Pass | Cheap Ninja/interaction portfolio; no fast-mana conversion |
| 02 | Budget Lathril | Pass | Protection and draw improve; Elf floor and closer survive |
| 03 | Budget Meren | Pass | Affordable sacrifice/recursion utility; packages survive |
| 04 | Light-Paws | Pass | Tutorable Aura interaction leads; Aura ladder preserved |
| 05 | Talrand | Pass | Five legal spells; no colorless-mana false positives or unsafe cut |
| 06 | Political Zedruu | Pass | Only donation cards selected; generic control filler abstained |
| 07 | Krenko | Pass | Velocity/protection/Goblin portfolio; Pyrokinesis protected |
| 08 | Atraxa Blink | Pass | Three blink cards; weak fixing claims and mana-base cuts abstained |
| 09 | Budget Wilhelt | Pass | Entire top five under $2 total; Zombie/sacrifice plan retained |
| 10 | Budget Vadrik | Pass | Five efficient answers; premium/unpriced budget leaks removed |
| 11 | Optimized Muldrotha | Pass | Curated competitive portfolio; protected interaction survives |
| 12 | cEDH Yuriko | Pass | Tournament-speed output; zero overlap with budget Yuriko |
| 13 | cEDH Najeela | Pass | Tournament interaction/tutor output; compact enabler protected |
| 14 | Janky Zedruu | Pass | One donation card, no cuts, no Gilded Drake power outlier |
| 15 | 18-land Grist | Pass | Warning retained, premise preserved, no commander duplicate |
| 16 | 97-Mountain joke | Pass | Recommendations paused |
| 17 | Unfinished Urza | Pass | Missing commander and 98 cards block analysis |
| 18 | Partial Lathril | Pass | Severe incompleteness and zero lands block analysis |

## Promotion gates

| Gate | Result |
|---|---|
| Immutable fixture integrity and import expectations | Pass |
| Four negative controls take expected paths | Pass |
| At least 15 strict passes | Pass (18) |
| Budget/cEDH Yuriko materially differ | Pass |
| Political/janky Zedruu preserve distinct experiences | Pass |
| No top-five intent violation | Pass |
| No unsafe protected/floor cut | Pass |
| Swap explanations state preserved coverage and gain | Pass |
| Synthetic benchmarks and role calibration | Pass |
| Every changed top choice manually reviewed | Pass (11) |
| Runtime within baseline tolerance | Pass |

## Activation recommendation

Promote through configuration rather than deleting the rollback path:

1. Set `RECOMMENDATION_RANKER_MODE=v2` in the controlled environment.
2. Retain `shadow` and `legacy` as rollback values.
3. Monitor abstention rate, changed-top-choice rate, candidate overlap, budget
   warnings, missing competitive evidence, and user correction feedback.
4. Roll back on any critical intent violation, illegal recommendation, or
   protected-package cut; add the miss to a frozen regression fixture before
   reactivation.
