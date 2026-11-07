# Phase 6 Collection and Feedback Validation Report — 2026-11-07

## Decision

**Phase 6 satisfies the collection-awareness, privacy, and recommendation
non-regression gates.** Saved card quantities can now guide or constrain the
promoted deterministic constructor, while user recommendation choices are
captured only as private evaluation history.

No behavioral data can alter production ranking. A fresh public V3 validation
run exactly matches the promoted additions, cuts, and swaps across all 18
reviewed decks. Engineering confidence that this release improves user
continuity without degrading recommendation intelligence is **0.94** over the
covered matrix.

## Delivered behavior

- Authenticated users can import, search, update, and remove canonical saved
  collection records. Imports accept simple quantity-prefixed card lists.
- `prefer_owned` changes candidate order without making ownership evidence of
  strategic fit. `owned_only` is a hard candidate constraint.
- Owned-only construction respects basic-land quantities and leaves unsupported
  slots visible instead of silently using unowned copies.
- Build intents reference a saved collection rather than persisting a stale
  snapshot. The current collection is hydrated for preview and generation, and
  its content participates in the draft source fingerprint.
- Analysis add, cut, and swap feedback is validated against the referenced
  analysis before storage. Reversing a choice updates the same private event.
- Applied deterministic drafts store constructor/version/fingerprint and
  selected-card provenance as a private review event.
- Users can delete feedback history independently. Deck deletion and account
  reset also remove the Phase 6 records within their respective scopes.

## Feedback promotion boundary

The active feedback policy reports:

- storage scope: `private_user_history`;
- production ranking influence: `false`;
- automatic learning: `false`;
- aggregation: disabled;
- future minimums: 25 unique users and 50 events per cohort; and
- required future gates: provenance, offline review, a versioned semantic
  release, and a rollback path.

The feedback service intentionally exposes no scoring hook. Meeting a sample
minimum in the future would permit analysis, not automatic promotion.

## Reproducible validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run smoke:source
npm --prefix frontend run build
.\.venv\Scripts\python.exe backend\scripts\run_builder_validation.py `
  --output test_reports\phase6-builder-nonregression.json
.\.venv\Scripts\python.exe backend\scripts\run_real_deck_validation.py `
  --output test_reports\phase6-public-v3-nonregression.json
```

Results:

- Backend: **278 passed**.
- Frontend source smoke: **16 groups passed**.
- Frontend production build: **compiled successfully**.
- Complete constructor: **26/26 cases passed**, with zero failed or missing
  counterfactual results.
- Public V3: **18/18** fixture integrity and input-expectation checks passed.
- Public V3 ranked outputs: exact addition, cut, and swap order in **18/18**
  cases against `test_reports/real_deck_validation_v3_release_candidate.json`.

The generated reports are intentionally ignored runtime artifacts; the frozen
fixtures and promoted release candidate remain the versioned comparison
sources.

## Quality boundaries retained

- Collection membership does not manufacture synergy, role coverage, or
  confidence.
- Saved ownership is consulted only in build flows that explicitly select a
  collection mode.
- Recommendation feedback does not alter the suggestion engine, Planner V3,
  semantic registry, confidence model, or constructor evidence thresholds.
- Complete drafts retain legality, identity, singleton, count, budget,
  invariant, evidence, and portfolio gates.
- Unsupported cards and quantities produce explicit abstention, warnings, or
  unresolved slots.

## Rollback

The Phase 6 collections are additive and user-scoped. Removing their UI routes
does not change the existing analysis data model. Complete construction retains
its independent `BUILD_CONSTRUCTOR_MODE` runtime rollback. The feedback policy
has no production-ranking path to disable because none is implemented.
