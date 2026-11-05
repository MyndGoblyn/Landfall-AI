# Real-Deck Recommendation Validation Report

**Evaluation date:** 2026-07-30
**Validation set:** 18 public Commander decklists supplied in
`mtg_commander_validation_set.txt`
**Decision:** Recommendation Ranker V2 is **not ready for promotion**. Keep
`RECOMMENDATION_RANKER_MODE=shadow`.

## Executive verdict

The validation set materially improved LandFallAI. It exposed and led to fixes
for importer drift, quantity-aware deck validation, incomplete-list handling,
recommendation restraint, and several false semantic matches. Those controls
now behave reliably on the supplied decks.

The set also establishes that ranking quality cannot reach the requested level
by inferring intent from card text and the commander alone. The paired Yuriko
lists have budget-casual and cEDH goals, while the paired Zedruu lists have
political and intentionally janky goals. The current deck record does not store
those distinctions. Consequently, the engine can find mechanically plausible
cards while still making the wrong recommendation for the user's deck.

Current confidence that the complete system meets the intended goal of
versatile, accurate, well-reasoned recommendations is **0.42**. This is an
engineering confidence rating, not a statistically estimated probability. It
reflects strong import/diagnostic behavior but insufficient intent preservation,
cut safety, budget awareness, and competitive-context calibration.

Confidence after the P0 and P1 roadmap below is **0.82**, provided the immutable
validation snapshots and human labels pass the stated promotion gates.

## Method

Each public URL was imported on 2026-07-30. Main-deck quantity, submitted-card
quantity, commander assignment, land quantity, and input status were checked.
Complete analyzable decks were then reviewed using legacy and V2 ordering, with
manual inspection of:

- commander and archetype fit;
- stated budget, power, and intentional constraints;
- missing-role suggestions;
- top additions and their explanations;
- possible cuts and preservation of engine pieces;
- addition-to-cut pairing; and
- behavior on malformed, incomplete, or intentionally nonfunctional lists.

This run used live public sources. It is dated evidence, not yet a reproducible
fixture, because source owners can edit those lists. Plain-text exports must be
stored before this suite becomes a deterministic CI gate.

## Import and input-control results

The importer successfully fetched all 18 sources after adapting to the current
Moxfield and Archidekt response shapes. `main` excludes the commander,
maybeboard, and sideboard consistently.

| ID | Deck | Main | Submitted | Unique | Lands | Input result |
|---:|---|---:|---:|---:|---:|---|
| 01 | Budget Yuriko | 99 | 100 | 72 | 32 | Ready |
| 02 | Budget Lathril | 99 | 100 | 84 | 35 | Ready |
| 03 | Budget Meren | 99 | 100 | 84 | 30 | Ready |
| 04 | Light-Paws | 99 | 100 | 65 | 35 | Ready |
| 05 | Talrand | 99 | 100 | 70 | 35 | Ready |
| 06 | Political Zedruu | 99 | 100 | 80 | 35 | Ready |
| 07 | Krenko | 99 | 100 | 70 | 33 | Ready |
| 08 | Atraxa | 99 | 100 | 90 | 40 | Ready |
| 09 | Wilhelt | 99 | 100 | 73 | 36 | Ready |
| 10 | Vadrik | 99 | 100 | 71 | 34 | Ready |
| 11 | Muldrotha | 99 | 100 | 99 | 29 | Ready |
| 12 | cEDH Yuriko | 99 | 100 | 99 | 25 | Low-land notice; analysis allowed |
| 13 | cEDH Najeela | 99 | 100 | 99 | 24 | Low-land notice; analysis allowed |
| 14 | Janky Zedruu | 99 | 100 | 78 | 35 | Ready |
| 15 | 18-land Grist | 99 | 100 | 83 | 18 | Severe mana-base warning |
| 16 | 97-Mountain joke | 99 | 100 | 3 | 97 | Intent confirmation; recommendations paused |
| 17 | Unfinished Urza | 98 | 98 | 90 | 36 | Blocked: commander missing and incomplete |
| 18 | Partial Lathril | 23 | 24 | 24 | 0 | Blocked: severely incomplete |

The count controls now use quantities rather than the number of unique card
names. Missing commanders and severely incomplete lists block analysis with a
specific explanation. An extreme repetition control pauses recommendations for
the 97-Mountain list instead of attempting to repair the joke. An analyzable
incomplete list can only receive additions for open slots and cannot receive
cuts.

## Recommendation-quality results

`Pass` means the observed behavior preserved the supplied intent at the level
required for a promotion decision. `Partial` means the engine found relevant
cards but violated or could not verify an important constraint. Passing a
negative control means the system correctly warned, paused, or blocked; it does
not mean the deck received normal recommendations.

| ID | Result | Review |
|---:|---|---|
| 01 | Partial | Yuriko/top-deck logic improved and alternate-cost high-MV cards are protected, but budget and casual power are not enforced. |
| 02 | Fail | Generic token cards can outrank Elves and the cut logic does not preserve the required typal density. |
| 03 | Partial | Graveyard and creature-recursion matching improved, but premium or generic cards can violate the budget creature-toolbox identity. |
| 04 | Pass | Aura-ladder, protection, and Voltron cards are prioritized; Equipment and unrelated enchantment draw are rejected. |
| 05 | Pass | Suggestions now retain instant/sorcery density and prefer spells or true spell payoffs over generic token makers. |
| 06 | Partial | Donation/political matching is substantially better, but the system lacks a declared politics-versus-control target. |
| 07 | Fail | Generic token cards and unsafe Goblin cuts show missing typal and high-power combo preservation. |
| 08 | Fail | Generic card-type mentions are mistaken for Atraxa's deliberate type-diversity/blink plan. |
| 09 | Pass | Zombie, sacrifice, graveyard, and replacement-token suggestions remain connected to Wilhelt's engine. |
| 10 | Partial | Spell density is mostly preserved, but Vadrik power-growth, cost reduction, combo compactness, budget, and cut safety are not modeled deeply enough. |
| 11 | Fail | False graveyard/sweeper matches were removed, but proposed cuts are unsafe for an optimized permanent-recursion shell. |
| 12 | Fail | Casual-value cards can outrank cEDH-speed interaction, enablers, or compact combo pieces. |
| 13 | Fail | Slow generic five-color cards can outrank tournament-speed Najeela needs. |
| 14 | Fail | Mechanically efficient Jeskai cards can erase the explicitly janky bad-gift identity. Donation payload protection alone is insufficient. |
| 15 | Fail | The severe 18-land condition is detected, but the recommendation lane does not make mana-base repair the dominant next action. |
| 16 | Pass | Extreme repetition and deliberate nonfunctionality are surfaced; recommendations are paused. |
| 17 | Pass | The actual 98-card state is preserved and analysis is blocked with exact missing-input reasons. |
| 18 | Pass | The partial list is preserved and distinguished from a merely low-power complete deck. |

Strict result: **6 pass, 4 partial, 8 fail**. This is deliberately conservative.
The synthetic benchmark remains useful for isolated ranking behavior, but it
does not override failures on complete human-built decks.

## Improvements implemented from this set

### Import correctness

- Read the current Moxfield `boards.*.cards` structure and embedded card data.
- Use a source-compatible Moxfield request path when its current edge protection
  rejects the previous client.
- Respect Archidekt deck categories and exclude commander, maybeboard, and
  sideboard entries.
- Normalize URL and plain-text imports to the same main-deck convention.

### Input safety

- Count card quantities, land quantities, unique names, and submitted cards.
- Emit exact incomplete, oversized, low-land, and extreme-repetition findings.
- Block missing-commander and severely incomplete analysis.
- Pause blind optimization for extreme repetition/joke-deck behavior.
- Do not manufacture cuts for an incomplete list.
- Surface the assessment in both import and analysis user interfaces.

### Semantic quality

- Do not classify graveyard return-to-battlefield text as blink without an
  exile event.
- Reject nondeck supplementary objects and cards not legal in Commander.
- Reject opponent-only draw/Treasure as the user's draw/ramp.
- Reject graveyard hate, blink, and unrelated mass exile as removal/sweepers.
- Require real Aura context for Light-Paws draw and Voltron fixes.
- Require spells or real spell payoffs in a Talrand-style spellslinger plan.
- Add Yuriko-style top-deck mana-value value and protect alternate-cost reveal
  cards from simplistic high-cost cuts.
- Protect recognizable Zedruu bad-gift/donation payloads, including discard-hand
  and maximum-hand-size drawbacks.

## Why promotion is blocked

1. **Intent is absent from the stored deck model.** Budget, power target,
   optimization mode, political experience, pet cards, and intentional defects
   are only present in the human annotations.
2. **Archetype invariants are not first-class.** Elf/Goblin/Zombie density,
   instant/sorcery density, Aura mana-value ladders, and Atraxa card-type spread
   need measurable floors during both adds and cuts.
3. **Cut safety is weaker than add relevance.** A plausible new card does not
   justify removing a combo piece, free spell, tutor target, typal enabler, or
   deliberately donated drawback.
4. **Power context is under-modeled.** Casual, high-power, and cEDH lists require
   different mana-efficiency, interaction, tutor, and combo standards.
5. **Mana-base defects are diagnostic only.** A severe land shortage needs its
   own repair lane before ordinary synergy upgrades.
6. **Live URLs are mutable.** Human-reviewed immutable inputs and labels are
   needed for reliable longitudinal comparison.

## Remaining roadmap

### P0. Add a deck intent contract

Persist and expose a `DeckIntentProfile` before ranking:

- target power band;
- budget mode and optional ceiling;
- optimization mode: preserve, tune, competitive, or repair;
- primary archetype and desired play experience;
- protected/pet cards and protected packages;
- excluded cards/packages; and
- intentional constraints such as low lands, joke construction, or flavor-first
  choices.

The engine must explain which declared constraint affected each recommendation.
If required intent is unknown, it should lower confidence and avoid aggressive
cuts. Estimated confidence contribution: **+0.20**.

### P0. Make archetype invariants measurable

Build a deck-plan profile with before/after floors for typal density, spell
density, permanent-type spread, mana curve, Aura ladder coverage, sacrifice
outlets, enablers, payoff density, and known combo packages. Evaluate an add and
cut as a state transition, not as two independently ranked cards. Estimated
confidence contribution: **+0.12**.

### P0. Add conservative cut and swap policy

Every cut must include evidence that the replacement preserves required roles
and engine utility. Protect tutors and tutor targets, alternate-cost/free spells,
combo dependencies, scarce effects, typal density, and declared cards. Return
an addition without a cut when no safe pairing clears the threshold. Estimated
confidence contribution: **+0.10**.

### P1. Calibrate ranking by power and budget

Separate casual, optimized, and competitive efficiency priors. Use curated
labels for cEDH-speed interaction and compact win packages rather than treating
price or popularity as proof of fitness. Apply budget filters before ranking and
show when no qualified candidate exists. Estimated confidence contribution:
**+0.08**.

### P1. Add a mana-base recommendation lane

When lands, color sources, or early mana fail a severity threshold, reserve the
top recommendations for quantified mana repair. Explain the expected land/source
range and suppress ordinary synergy optimization until the critical defect is
addressed, unless the user explicitly preserves it. Estimated confidence
contribution: **+0.05**.

### P1. Freeze and label this validation set

Save dated plain-text exports, source metadata, commander, expected input status,
must-preserve invariants, unacceptable adds/cuts, and a small human-ranked
candidate set per deck. Never update snapshots in place. Estimated confidence
contribution: **+0.05**.

### P2. Calibrate confidence and production feedback

Measure acceptance, rejection, undo, and `not relevant` feedback by intent
segment without storing private deck contents in telemetry. Compare shadow and
served ranking on the same candidate pool. Calibrate displayed confidence to
observed correctness, and use abstention when evidence is weak.

## Promotion gates

V2 must remain in shadow mode until one dated report passes all of these gates:

- all 18 immutable snapshots import with exact commander and quantity results;
- all four negative controls take their expected warn, pause, or block path;
- at least 15 of 18 decks pass strict intent review, with no critical failure on
  incomplete-list handling, intentional constraints, or cEDH versus casual
  differentiation;
- the two Yuriko decks produce materially different budget/power-appropriate
  results and the two Zedruu decks preserve their distinct experiences;
- no top-five addition violates a declared budget, power, typal, card-type,
  spell-density, or intentional constraint;
- no proposed cut removes a protected card/package or lowers an archetype floor;
- every paired swap states the preserved role and marginal improvement;
- severe mana-base defects place quantified mana repair ahead of ordinary
  synergy suggestions unless explicitly preserved;
- all synthetic calibration gates and automated tests continue to pass; and
- manual review of every legacy/V2 top-choice change records an approval or a
  labeled defect.

The machine-readable gate is
`tests/fixtures/real_deck_validation_status.json`. The calibration command exits
nonzero while that reviewed status is failing, even when every synthetic gate
passes.

## Confidence by capability

| Capability | Current confidence | After roadmap |
|---|---:|---:|
| URL import and count preservation | 0.93 | 0.97 |
| Incomplete/joke-list restraint | 0.88 | 0.95 |
| Basic commander semantic alignment | 0.74 | 0.90 |
| Explanation grounded in card text | 0.72 | 0.90 |
| Safe cuts and swap pairing | 0.58 | 0.86 |
| Typal/package preservation | 0.45 | 0.88 |
| Budget and intentional-jank preservation | 0.30 | 0.85 |
| cEDH/high-power calibration | 0.25 | 0.75 |
| **Complete intended outcome** | **0.42** | **0.82** |

The after-roadmap values assume the new intent fields are actually supplied by
users or an immutable labeled source. They should not be interpreted as a
promise that an unlabeled deck can be assigned a reliable budget or play
experience automatically.

## Post-report implementation note

After this evaluation, LandFallAI implemented the first P0 tranche described
above: a persisted `DeckIntentProfile`, strict per-card budget and exclusion
filters, protected-card/package cut safety, conservative unconfirmed behavior,
intentional-jank abstention, and quantity-aware typal and spell-density floors
for swap pairing. Severe land shortages now also produce a quantified multi-slot
repair ahead of ordinary synergy upgrades unless the owner explicitly preserves
the low-land premise. See `docs/DECK_INTENT_AND_INVARIANTS.md`.

The next package tranche now also measures Aura mana-value ladders,
card/permanent-type spread, sacrifice outlets/payoffs/fodder, and explicitly
declared protected packages. Atraxa-style card-type enumeration no longer
creates unrelated generic type themes. As with the earlier note, these changes
require a new reviewed run before they alter the historical validation result.

The deterministic dependency tranche now reports explicit typed-tutor target
sets and exact named-card links. Fragile tutor targets require legal replacement
targets, exact named links are protected from automatic cuts, and missing named
targets receive bounded evidence when otherwise valid. It deliberately does not
infer emergent combos. This also requires a new reviewed run before changing the
historical result.

This note does not change the 6/4/8 result or the failing machine-readable gate.
Those values remain historical evidence until the immutable set is rerun and
manually reviewed against the same acceptance criteria.
