# Product Development Pipeline

## Purpose

This roadmap adds three connected product capabilities without weakening
LandFall's deterministic quality boundaries:

1. **Track List** for saving commanders found in Discover or Commander Lab.
2. **Commander Atlas** for browsing commanders and opening an evidence-backed
   profile built from LandFall's existing analysis.
3. **Guided Build** for turning explicit user choices into a reviewable deck
   draft through deterministic planning rather than unconstrained generation.

The features should form one path:

```text
Discover / Commander Atlas / Commander Lab
                 |
                 v
             Track List
                 |
                 v
        Commander profile or Guided Build
                 |
                 v
       Deck editor -> analysis -> recommendations
```

## Reference review

The ManaTap commander directory and guided deck-builder were reviewed on
2026-11-05 as product references. The useful patterns are:

- A searchable commander catalog with color filters and separate archetype,
  strategy, and trending views.
- Commander pages that join identity and legality with a game plan, common
  mistakes, likely win paths, card roles, packages, cost/power context, and
  related commanders.
- A staged builder that asks for the format, starting point, build style,
  commander/card/idea, playstyle, power bracket, budget, build shape,
  collection preference, and extra constraints before producing a deck.
- Clear handoffs between browsing a commander, studying it, and starting a
  build around it.

LandFall will use these as interaction concepts only. It will not copy their
content, assets, generated guides, rankings, or proprietary data. Popularity
must never become a substitute for card fit. LandFall's own Scryfall catalog,
reviewed semantic registries, validation fixtures, and explicit user intent
remain the sources of truth.

## Design principles

- **One analysis system.** Commander Atlas, Commander Lab, Discover, Track
  List, and Guided Build must call the same commander-analysis and
  recommendation services. No page-specific recommendation logic.
- **Intent before inference.** Confirmed structured choices outrank inferred
  themes. Prose can suggest fields, but it cannot silently set protected,
  excluded, budget, or power constraints.
- **Hard gates remain hard.** Legality, color identity, singleton rules,
  budget limits, protected packages, exclusions, and evidence floors cannot be
  bypassed to complete a deck.
- **Incomplete is better than fabricated.** If LandFall cannot fill a slot with
  enough evidence, it returns a visible gap and explains what is missing.
- **Popularity is context, not proof.** It may be displayed later as a labeled,
  time-stamped secondary signal, but it cannot provide fit confidence.
- **Current intelligence on reopen.** Tracked commanders store identity and
  user metadata, not a frozen analysis. Opening one runs the current engine so
  engine improvements reach previously saved items.
- **Explain packages, not just cards.** A generated deck must say which role,
  strategy lane, package, or constraint earned every non-land slot.

## Phase 1 - Track List foundation

**Goal:** let a user preserve a commander discovery and return to its current
analysis in one action.

### Backend

- Add a `tracked_commanders` collection with a unique compound index on
  `(user_id, commander_oracle_id)` and an index on `(user_id, updated_at)`.
- Store stable identity and presentation data only: oracle ID, canonical name,
  image URL, color identity, type line, source surface, user note, created and
  updated timestamps.
- Add authenticated list, create/upsert, update-note, and delete endpoints.
- Include `tracked_commanders` in account deletion/reset behavior and the
  in-memory database used by tests.
- Re-resolve stale presentation fields from the current catalog when needed;
  do not persist recommendation output in this record.

### Frontend

- Add Track/Tracked controls to Commander Lab and Discover results.
- Add `/track-list` with commander art, identity, source, optional note, and
  saved date.
- Opening an item routes to Commander Lab with a canonical commander query and
  runs the current analysis.
- Add a `Start a build` action that will become active when Guided Build ships.
- Put Track List in the primary authenticated navigation. Keep Guide reachable
  from the dashboard/help surface.

### Exit criteria

- Track and untrack are idempotent and isolated by user.
- Account reset removes every tracked record.
- Reopening a tracked commander returns the same current analysis as a fresh
  Commander Lab search.
- Responsive, keyboard, empty, loading, duplicate, and error states pass UI
  tests.

**Delivery confidence: 96%.** This is a bounded persistence and navigation
feature built on existing authenticated patterns.

## Phase 2 - Commander Atlas and profile registry

**Goal:** make the complete commander catalog browsable while improving the
structured commander evidence available to every deterministic feature.

### User experience

- Add `/commanders` with name search, exact/inclusive color identity, mana
  value, and supported archetype/playstyle filters.
- Rank by query and filter fit. Do not default to global popularity.
- Each commander profile reuses the current Commander Lab output and adds
  stable sections for game plan, support needs, win paths, common construction
  risks, package relationships, similar commanders, and data confidence.
- Display a coverage label and freshness stamp. Exploratory profiles must look
  different from profiles backed by reviewed registry evidence.
- Provide direct Track, Analyze, Discover similar, and Start a build actions.

### Deterministic intelligence

Add a versioned `CommanderProfile` resource to the semantic bundle. A profile
may contain:

- stable commander/oracle identity and color identity;
- supported archetype priors and playstyle affinities;
- primary engine requirements and support-role targets;
- win-path families and required setup/payoff relationships;
- package membership, prerequisites, and anti-synergies;
- common failure modes and false-positive warnings;
- comparable commander relationships with an explicit reason;
- evidence sources, review status, confidence, and last-reviewed timestamp.

The registry supplements oracle-text detection; it does not override legality
or invent a theme. Generated profile prose is a view over the evidence and
must never be fed back into scoring as if it were independent evidence.

Start with the existing real-deck validation commanders and a deliberately
diverse reviewed seed set. Unreviewed commanders continue to use the current
mechanics/archetype detector with honest exploratory coverage.

### Exit criteria

- Every legal commander is searchable from the local catalog without a live
  Scryfall dependency.
- Filters are deterministic and URL-addressable.
- Every displayed strategic claim names its registry, oracle, or heuristic
  evidence class.
- A frozen profile benchmark verifies archetype precision, false-positive
  resistance, support needs, and similarity reasons.
- The semantic-bundle checksum, rollback, and last-known-good protections also
  cover commander profiles.

**Delivery confidence: 92%.** Catalog and profile presentation are low risk;
the score assumes a reviewed seed registry rather than auto-generated profiles
being promoted as ground truth.

**Implementation status — November 6, 2026:** deployed. Commander Atlas now
uses the verified local catalog with shareable deterministic filters, reviewed
and exploratory profile states, current Commander Lab analysis, Track List,
Discover-similar, and commander-seeded deck creation. The semantic bundle
contains 13 exact-identity reviewed profiles; every other legal commander keeps
the explicit exploratory path. Release validation passed 235 backend tests,
the frozen profile evidence benchmark, frontend source smoke and production
builds, responsive workflow QA, and the Cloudflare deployment dry run.

## Phase 3 - Guided Build intent contract

**Goal:** collect the missing facts that deterministic deck construction needs
before any cards are selected.

Create a versioned `BuildIntent` schema that references, rather than replaces,
`DeckIntentProfile`:

- format and deck name;
- starting point: blank, imported list, existing deck, commander, card, or
  concept;
- commander or partner/background pair;
- build mode: manual, guided scaffold, or complete draft;
- playstyle: balanced, aggressive, value, control, combo, or explicit custom
  priorities;
- target bracket/power range;
- budget mode, total budget, and per-card ceiling;
- full deck, core shell, mana base, or missing-slots-only build shape;
- all cards, prefer owned, or owned-only candidate pool;
- protected cards/packages, exclusions, and intentional constraints;
- confirmed notes describing the desired experience.

Map the contract into the existing engine instead of adding hidden prompt
logic:

- playstyle becomes inspectable strategy-lane weights;
- bracket becomes power range plus explicit fast-mana, tutor, combo, and
  interaction policies;
- budget maps to current budget gates;
- build shape bounds the requested slot allocator;
- collection preference constrains or biases the candidate provider;
- extra notes are normalized into proposed structured fields that the user
  confirms before construction.

The first release of the wizard may save an intent and open a manual deck. It
must not generate a complete list until Phase 4 and its validation gates are
ready.

### Exit criteria

- Round-trip serialization is stable and older saved intents migrate safely.
- Every wizard choice has a visible mapping to an engine constraint or weight.
- Contradictory choices are rejected or resolved by the user, not silently
  prioritized.
- The same confirmed intent always produces the same normalized input.

**Delivery confidence: 94%.** The current `DeckIntentProfile`, invariant
system, and strategy profile already cover much of the required contract.

**Implementation status — November 6, 2026:** release-validated. Guided Build
now provides a five-stage, authenticated intent workspace with a versioned
`BuildIntent` v1 contract, stable normalization, explicit mappings for
playstyle, power policy, budget, build scope, and collection behavior, and
safe migration from saved `DeckIntentProfile` v1 records. Commander Atlas,
Commander Lab, Track List, and the deck dashboard can seed or reopen the same
contract. Contradictions are rejected, user-preserved constraints remain
visible. Phase 4 may serve only a bounded scaffold; complete construction
remains explicitly disabled until Phase 5 promotion.
Validation passed 250 backend tests, 14 frontend source-smoke groups, the
optimized production build, and desktop/mobile end-to-end workflow review.

## Phase 4 - Deterministic deck constructor

**Goal:** produce the highest-value legal portfolio for a confirmed build
intent, with an explanation and a safe abstention path.

### Construction pipeline

1. Resolve commander legality, partners/backgrounds, color identity, format,
   deck size, and singleton rules.
2. Combine confirmed intent with reviewed commander-profile evidence.
3. Allocate slots across mana, card flow, interaction, protection, engine,
   setup, payoff, recovery, and win-path packages.
4. Plan bounded retrieval lanes so one theme cannot consume the search budget.
5. Score every candidate independently through Ranker V2 and Planner V3 hard
   gates.
6. Select a complementary portfolio with package prerequisites,
   anti-synergies, role coverage, curve, and marginal utility in the objective.
7. Construct the mana base from color demand, curve, commander timing,
   land-matter evidence, budget, and owned-card constraints.
8. Validate deck count, legality, color identity, duplicates, budget, role
   floors, package completeness, curve, and protected/excluded cards.
9. Attach a reason ledger to each card and package. Mark unresolved slots
   instead of lowering an evidence floor.

### Required implementation work

- Generalize Planner V3 from add/cut portfolios to bounded slot portfolios.
- Add package dependency and anti-synergy edges to the semantic registry.
- Add a deterministic role/slot allocator and mana-base allocator.
- Add partial-build support so imported or manually chosen cards are fixed
  inputs, not suggestions to replace.
- Add draft persistence, revision history, and a re-run diff explaining why a
  card changed.
- Keep a separate runtime mode and rollback flag for construction; enabling it
  must not change existing analysis recommendations.

**Delivery confidence before builder validation: 84%.** The ranking foundation
is strong, but full-deck construction introduces package, mana-base, and
global-composition interactions that recommendation tests do not yet cover.

**Implementation status — November 6, 2026:** release-validated bounded
scaffold. The constructor reuses served Planner V3 output, preserves imported
cards and protected packages as fixed inputs, re-resolves every proposed card,
and independently enforces commander eligibility, partner/background pairing,
color identity, singleton, strict budget, exclusions, and owned-only rules.
For full-deck and mana-focused shapes it may add a conservative basic-land
baseline from measured mana-symbol demand. It never lowers evidence thresholds
to fill the list: unresolved in-scope and deferred slots stay visible in an
abstention ledger.

Authenticated draft persistence now records deterministic revisions, source
fingerprints, selected-card diffs, validation results, and explicit apply
state. Applying a stale or blocked draft is rejected. The dedicated build
workspace shows role allocation, hard-gate results, per-card reasoning,
evidence confidence, verified budget subtotal, revision history, and the Phase
5 boundary. Production remains capped at 40 proposed slots and protected by
`BUILD_CONSTRUCTOR_MODE`; complete-draft mode is not promoted.

Validation passed 257 backend tests, 15 frontend source-smoke groups, the
optimized production build, and a fresh browser run using a real Meren intent.
That run preserved the protected card, accepted nine independently verified
Planner V3 additions, passed all six hard gates, and left 89 main-deck slots
open rather than inserting filler. Desktop and 390px mobile layouts passed
visual and horizontal-overflow review.

**Current delivery confidence: 94% for bounded scaffolds.** Confidence for
complete 100-card drafts remains 84% until the separate Phase 5 golden suite
and promotion gates pass.

## Phase 5 - Builder validation and promotion

The existing reviewed deck set remains the regression gate for analysis and
recommendations. Guided Build needs a separate golden suite because a good
single swap does not prove a good 100-card portfolio.

### Required evaluation set

- At least 24 reviewed build intents spanning aggro, control, value, combo,
  typal, spellslinger, graveyard, artifacts/enchantments, lands, Voltron,
  politics, intentional jank, budget, high power, and cEDH.
- Counterfactual pairs for the same commander with different budgets,
  playstyles, brackets, collection restrictions, and banned packages.
- Partner/background, colorless, five-color, expensive commander, and unusual
  mana-base cases.
- Negative controls for impossible budgets, contradictory constraints,
  insufficient owned pools, illegal commanders, and requests that should
  produce an incomplete scaffold rather than fabricated certainty.

### Promotion gates

- 100% legal commander, color identity, singleton, and deck-count compliance.
- 100% strict-budget, excluded-card, protected-card, and collection-only
  compliance.
- No unsupported high-confidence claim and no recommendation without a reason
  ledger.
- Reviewed role coverage, package coherence, mana-source sufficiency, curve,
  and strategy balance pass their calibrated thresholds.
- Counterfactual outputs change in the requested direction without unrelated
  instability.
- Deliberate jank, flavor, politics, and protected packages survive unchanged.
- Shadow comparisons and fresh real-build reviews pass before the constructor
  mode can be promoted.

**Promotion confidence after these gates: 92%.** This is the target confidence
for enabling complete drafts in production. Until then, Guided Build should
serve manual or partial deterministic scaffolds only.

## Phase 6 - Collection-aware and feedback improvements

- Add card collection storage only after the core builder works without it.
- Prefer-owned is a scoring bias; owned-only is a hard candidate constraint.
- Tracked commanders can prefill Guided Build, but tracking alone is not a
  global ranking signal.
- User keeps/cuts and accepted suggestions may support private history and
  later aggregated offline evaluation. They must not become automatic truth or
  silently tune production ranking.
- Add privacy, minimum-sample, provenance, and rollback requirements before
  any aggregate behavioral signal affects a semantic release.

**Delivery confidence: 88%.** The value is high, but it requires new user data,
privacy rules, and candidate-pool behavior that should not delay the core
commander and builder experience.

## Recommended build order

| Priority | Work | Why now | Promotion requirement |
| --- | --- | --- | --- |
| P1 | Track List | Small, high-value continuity feature and entry point for later flows | Auth, isolation, reset, and navigation tests |
| P2 | Commander Atlas catalog | Exposes existing intelligence and creates a shared browse/profile surface | Deterministic search/filter and coverage labels |
| P3 | Reviewed commander-profile seed | Adds independent evidence to profiles, suggestions, and construction | Frozen precision/false-positive benchmark |
| P4 | Guided Build intent wizard | Captures constraints before costly constructor work | Stable schema and visible mappings |
| P5 | Partial scaffold constructor | Reuses V3 while limiting global composition risk | Builder golden suite and abstention behavior |
| P6 | Complete draft constructor | Adds role allocation, package graph, and mana base | All Phase 5 promotion gates |
| P7 | Collection-aware building | Personalizes candidate availability | Privacy and owned-only hard-gate tests |

## Overall confidence

**91% confidence that this roadmap will improve versatility, accuracy, and
user continuity without degrading the current intelligence.**

The confidence comes from reusing the existing intent, invariant, semantic,
ranking, and planning systems instead of creating a second recommendation
stack. The remaining uncertainty is concentrated in full-deck construction,
which is intentionally isolated behind its own validation suite, runtime mode,
and promotion gate.
