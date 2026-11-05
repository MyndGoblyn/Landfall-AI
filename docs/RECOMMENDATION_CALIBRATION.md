# Recommendation Promotion Calibration

LandFallAI promotes Recommendation Ranker V2 only while labeled recommendation
decisions, full-deck role behavior, and the dated real-deck review pass the same
promotion report.

Run the report from the repository root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_calibration.py
```

Add `--details` to include every ranker ordering and deck-profile result. The
command emits JSON and exits nonzero when any promotion gate fails.

## Inputs

The report combines three versioned fixtures:

- `golden_recommendation_benchmark.json`: labeled candidate pools with core,
  strong, weak, and reject judgments plus evidence requirements.
- `golden_deck_calibration.json`: eight representative 99-card profiles that
  isolate reliable coverage, misleading raw counts, expensive utility,
  conditional effects, and efficient multi-role cards.
- `real_deck_validation_status.json`: the latest human-reviewed real-deck gate
  and its dated report. This gate fails closed until the real-deck thresholds
  pass.

The deck profiles intentionally use grouped functional slots rather than
claiming to be published decklists. This keeps each quality boundary small,
deterministic, and reviewable while still exercising a complete 99-card role
distribution.

## Promotion gates

A report is `ready_for_controlled_promotion` only when:

- legacy and V2 both pass every labeled recommendation case;
- all deck calibration profiles match their expected effective gaps;
- V2 has no per-case precision, NDCG, core-recall, hard-rejection, or reason
  regression against legacy;
- mean V2 NDCG is not lower than legacy; and
- V2 has zero hard rejections and zero reason failures; and
- the latest real-deck validation status is passing.

Top-choice changes are reported but are not automatically treated as failures
when the labels consider both orderings equally correct. They are the priority
manual-review queue for a controlled rollout.

Passing this report authorizes `RECOMMENDATION_RANKER_MODE=v2`. The repository
default is V2 after the 2026-08-04 review; deployed environments should still
set the value explicitly so rollback ownership remains clear.

## Real-deck validation layer

The deterministic benchmark fixtures test isolated ranking and role-assessment
boundaries. Promotion also requires a passing dated real-deck report. The latest
report is
[REAL_DECK_VALIDATION_REPORT_2026-08-04_V2_PROMOTION.md](REAL_DECK_VALIDATION_REPORT_2026-08-04_V2_PROMOTION.md);
the pre-correction August review remains in
[REAL_DECK_VALIDATION_REPORT_2026-08-04.md](REAL_DECK_VALIDATION_REPORT_2026-08-04.md),
and the original baseline remains in
[REAL_DECK_VALIDATION_REPORT_2026-07-30.md](REAL_DECK_VALIDATION_REPORT_2026-07-30.md).

The supplied 18-deck set covers budget and cEDH versions of the same commander,
political and intentionally janky versions of the same commander, typal density,
graveyard engines, spellslinger, Voltron, card-type diversity, severe mana-base
defects, extreme repetition, and incomplete lists. The corrected V2 run passes
all 18 strict reviews and authorizes controlled activation while the rollback
modes remain available.

The versioned `tests/fixtures/real_deck_validation/2026-08-04/` directory now
contains dated plain-text exports, normalized JSON, hashes, intent labels, and
reviewed results. Live URLs remain importer smoke inputs only; the immutable
fixture is the promotion source of truth.

A real-deck report passes only when it satisfies the thresholds recorded in the
dated report, including intent separation, archetype-floor preservation,
conservative cuts, negative-control behavior, and manual approval of changed
top choices.

Deck intent and the first typal/spell invariant layer are documented in
`DECK_INTENT_AND_INVARIANTS.md`. Calibration cases that declare intent must
submit the profile with the deck rather than embedding budget or power assumptions
only in prose. A changed recommendation does not pass merely because it is
mechanically relevant; it must also satisfy the declared intent and every active
before/after invariant.

The invariant review must now include Aura ladder rungs, scarce card/permanent
types, sacrifice-engine components, every declared protected package, typed
tutor targets, and exact named-card links. A cut that occupies one of those
structures passes only when its paired addition satisfies every recorded
preservation requirement. Typed-tutor labels must be checked against oracle
text, and deterministic dependency results must never be treated as inferred
combo coverage.

## Runtime shadow diagnostics

The admin `/api/admin/scryfall-cache` response includes:

- comparison and top-choice-change rates;
- separate Commander and deck-addition counters;
- candidate-set overlap by recommendation kind;
- the ten most recent changed recommendation lists;
- raw-versus-effective deck-gap change rate; and
- the ten most recent gap changes expressed only as role names.

Deck-gap diagnostics deliberately exclude user ids, deck ids, commander names,
and card names. Recommendation changes contain only public candidate card names
and do not retain user or deck identity.
