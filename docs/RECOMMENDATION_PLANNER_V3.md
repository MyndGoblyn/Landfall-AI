# Recommendation Planner V3

Planner V3 is the strategy and portfolio layer above Evidence Ranker V2. It
keeps deterministic legality, intent, invariant, and semantic checks as hard
boundaries, then improves which searches are spent, how candidates are
compared across roles, and which additions and cuts can be presented together.

## Goals

- Prefer the highest-value recommendation portfolio over the first matching
  cards returned by a search.
- Explain the measured deck need, exact card evidence, intent alignment, and
  portfolio contribution without overstating certainty.
- Preserve intentional budget, power, typal, package, and joke-deck choices.
- Abstain when the input or replacement evidence is too weak.
- Retain a one-setting rollback to the V2/legacy planning path.

## Planning pipeline

1. Build a versioned strategy profile from commander evidence, registered
   archetypes, deck role coverage, declared intent, and deck invariants.
2. Allocate the bounded query budget across measured role gaps, commander-plan
   lanes, and competitive registry access. One theme cannot consume every
   search slot while interaction, protection, or mana needs are unaddressed.
3. Evaluate each retrieved candidate independently across every compatible
   plan and role lane. Retrieval lane is weak corroboration, never permission
   to reuse another candidate's classification.
4. Apply legality, commander color identity, main-deck eligibility, intent,
   budget, invariant, and competitive-evidence gates.
5. Select a complementary portfolio with bounded deterministic beam search.
   The objective rewards distinct roles, full matched-lane coverage, reliable
   marginal role gain, and engine balance while penalizing redundant jobs.
6. Pair additions and cuts with maximum-weight assignment. V3 will not present
   a swap with negative net measured role gain, and it emits a standalone
   addition when no cut is safe.
7. Apply the versioned evidence-strength confidence policy. Confidence is not
   a probability and can only preserve or lower an existing policy cap.
8. Optionally refresh only the selected cards' current Scryfall legality and
   price. A new illegality or strict-budget violation vetoes the card; an
   outage leaves the deterministic catalog result intact.

## Semantic distribution

Mechanics, archetype, and competitive registries are packaged into one
canonical semantic bundle. The production backend downloads it from the
Cloudflare R2 read-only route, verifies compressed and uncompressed SHA-256,
size, schema, semantic version, and every resource checksum, and promotes it
atomically. A failed download or reload restores the previous bundle or uses
the reviewed registries shipped with the application.

The manifest is revalidated; checksum-addressed release objects are immutable.
Publishing order is always release object first and manifest second.

## Modes and rollback

`RECOMMENDATION_PLANNER_MODE` supports:

- `legacy`: use the pre-V3 query plan and swap pairing.
- `shadow`: retain the prior served behavior while recording V3 planning
  comparisons.
- `v3`: serve balanced planning, portfolio optimization, joint swap selection,
  conservative confidence, and the optional dynamic fact overlay.

Production defaults to `v3` after the 2026-11-05 promotion review. Development
defaults to `shadow` unless explicitly configured. Set the production variable
to `shadow` for immediate behavioral rollback; the Ranker V2 rollback remains
independent through `RECOMMENDATION_RANKER_MODE`.

## Diagnostics

Analysis responses expose stage timing, query budget/count, strategy profile,
planner version, selected V2/V3 portfolios, whether the portfolio changed, and
dynamic-overlay counts. Admin diagnostics expose planner comparison counters,
candidate-provider state, and semantic bundle state/version.

Critical rollback triggers are an illegal card, an intent or protected-package
violation, an unsafe cut, competitive output without curated evidence, or a
negative-value paired swap. Any confirmed miss must become a frozen regression
case before V3 is reactivated.
