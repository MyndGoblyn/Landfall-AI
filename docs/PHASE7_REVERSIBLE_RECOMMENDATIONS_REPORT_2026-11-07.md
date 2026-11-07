# Phase 7 Reversible Recommendations Report — 2026-11-07

## Decision

**The reversible recommendation workflow satisfies its release-candidate
quality and non-regression gates.** Users can apply one reviewed addition, cut,
or complete swap from a current analysis, and every change preserves a private
restorable copy of the previous list.

The workflow does not change search, semantic evidence, confidence, Planner V3
selection, or output order. Engineering confidence that it improves usability
without degrading recommendation intelligence is **0.94** over the covered
matrix.

## Safety contract

An action is accepted only when all applicable checks pass:

- the authenticated user owns both the deck and analysis;
- the requested card or pair exactly exists in that analysis;
- the analysis contains a Phase 7 source fingerprint;
- the deck, commander, color identity, and intents still match that fingerprint;
- an added card resolves by exact canonical name;
- the card remains Commander legal and inside the deck's color identity;
- singleton and 99-card main-deck limits remain valid; and
- the user explicitly confirms the mutation.

Old analyses cannot mutate a deck. After one successful action, every other
action on that analysis becomes stale until the user runs a fresh analysis.

## Revision and restore behavior

Each applied recommendation stores:

- workflow version, user, deck, analysis, and monotonic revision number;
- source and result fingerprints;
- exact add/cut recommendation snapshots and Planner provenance;
- human-readable added/removed quantities; and
- full before/after deck-card snapshots for private restoration.

History list responses omit the full snapshots and return compact metadata.
Restoring a snapshot creates a new revision, preserving the list being replaced.
Restore is blocked if commander, color identity, deck intent, or build intent no
longer matches the saved revision context.

Applying a recommendation is also recorded as private acceptance feedback. Per
the Phase 6 policy, that event has no automatic learning or production-ranking
influence.

## Reproducible validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run smoke:source
npm --prefix frontend run build
.\.venv\Scripts\python.exe backend\scripts\run_builder_validation.py `
  --output test_reports\phase7-builder-nonregression.json
.\.venv\Scripts\python.exe backend\scripts\run_real_deck_validation.py `
  --output test_reports\phase7-public-v3-nonregression.json
```

Results:

- Backend: **281 passed**.
- Frontend source smoke: **17 groups passed**.
- Frontend production build: **compiled successfully**.
- Complete constructor: **26/26 cases passed**, with no failed or missing
  counterfactual result.
- Public V3: **18/18** fixture integrity and input-expectation checks passed.
- Public V3 additions, cuts, and swaps: exact promoted order in **18/18** cases.

The runtime reports are intentionally ignored artifacts. Frozen fixtures and
the promoted V3 release candidate remain the versioned comparison sources.

## Rollback boundary

The action workflow is additive. Disabling its frontend controls and API routes
does not change existing decks, analyses, ranking, construction, or semantic
data. Stored revision history remains private and can be retained for recovery
or removed with its owning deck/account.
