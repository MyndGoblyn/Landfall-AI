# Real-Deck Recommendation Validation Report

**Evaluation date:** 2026-08-04 (America/New_York)
**Validation set:** 18 Commander decklists supplied in the human-reviewed
validation manifest
**Reviewed output:** Evidence Ranker V2, fast/default deck analysis
**Production decision:** **Do not promote V2. Keep
`RECOMMENDATION_RANKER_MODE=shadow`.**

## Executive verdict

The fresh reviewed run does not meet the promotion threshold. The result is
**6 strict passes, 2 partial results, and 10 failures**; at least 15 strict
passes are required.

LandfallAI is materially safer than it was in the 2026-07-30 review. Deck
intent, protected packages, measurable archetype floors, incomplete-list
blocking, joke-deck restraint, and like-for-like swap requirements are all
visible in real outputs. Budget Yuriko, budget Meren, Light-Paws, and the three
pause/block controls pass their individual reviews.

The suggestion engine still misses the requested quality level in the places
that matter most for promotion:

- cEDH Yuriko and Najeela receive casual combat and typal suggestions instead
  of tournament-speed interaction and compact win support;
- the budget and cEDH Yuriko top fives overlap on three cards;
- several cuts remove strategically important cards because printed mana value
  or broad role counts outweigh actual engine utility;
- budget/power intent changes filtering and confidence but does not reliably
  calibrate the best-ranked cards;
- unrelated counter types and attack/extra-combat text still produce false
  strategic matches; and
- the Grist negative control is offered a second copy of its own commander.

Engineering confidence that the complete system currently meets the intended
goal of versatile, accurate, well-reasoned recommendations is **0.55**. This is
a conservative engineering judgment, not a statistically estimated
probability. Input safety and intent preservation are strong; competitive
ranking, semantic cut safety, and power/budget calibration are not yet strong
enough.

## Reproducible evidence

Unlike the July review, this run freezes the inputs. The fixture directory
contains:

- normalized JSON with card quantities and oracle data;
- human-readable plain-text exports;
- SHA-256 hashes and count metadata in `snapshot_index.json`;
- structured intent and review labels in `review_manifest.json`; and
- the signed-off per-deck decisions in `review_results.json`.

Every JSON and text hash passed. Plain-text commander markers and every card
quantity were reparsed and matched against the normalized snapshots. The run
used the repository's configured catalog
`oracle_cards:2026-07-29T21:02:49.097+00:00`, containing 38,416 cards. No live
candidate-search ordering influenced the results.

Fixture: `tests/fixtures/real_deck_validation/2026-08-04/`

Reproduction command:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_real_deck_validation.py `
  --fixture-dir tests\fixtures\real_deck_validation\2026-08-04 `
  --output test_reports\real_deck_validation_2026-08-04_raw.json
```

The output artifact is intentionally under the ignored `test_reports/`
directory because it is approximately 2.1 MB and includes redundant full
recommendation payloads. The compact reviewed evidence is versioned with the
fixtures.

## Import and input-control results

The live sources were fetched once to create the immutable snapshots. Their
counts remained identical to the July observations.

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
| 15 | 18-land Grist | 99 | 100 | 83 | 18 | Severe mana warning; intentional low-land premise preserved |
| 16 | 97-Mountain joke | 99 | 100 | 3 | 97 | Recommendations paused for extreme repetition |
| 17 | Unfinished Urza | 98 | 98 | 90 | Blocked: commander missing and main deck incomplete |
| 18 | Partial Lathril | 23 | 24 | 23 | 0 | Blocked: severely incomplete |

All four negative controls take their expected input path. Case 15 still fails
recommendation review because its allowed output includes an illegal duplicate
of the commander; the input warning itself is correct.

## Recommendation-quality results

The strict result reviews V2 because V2 is the candidate for promotion. Legacy
was run on the same snapshots and candidate catalog solely for changed-choice
comparison.

| ID | Result | Reviewed evidence |
|---:|---|---|
| 01 | **Pass** | V2 replaces nearly deck-budget-sized legacy choices with inexpensive Ninja and combat-draw cards. Typal, enabler, reveal-value, and tutor packages survive the only cut. |
| 02 | **Fail** | Additions preserve Elf density, but Overwhelming Stampede—the declared go-wide closing payoff—is labeled off-plan and cut. |
| 03 | **Pass** | Affordable counter, permanent-interaction, fodder, recursion, and removal upgrades; declared outlets and toolbox creatures are protected. |
| 04 | **Pass** | Three top-five cards are tutorable Auras, the remainder address mana, and the Aura ladder survives the only cut. |
| 05 | **Fail** | Narrow colorless cards are overstated as broad interaction and Bident of Thassa, a Drake combat-draw payoff, is cut as redundant. |
| 06 | **Partial** | Donation packages are protected, but four of five additions are generic role fixes and Pyroblast outranks the political plan. |
| 07 | **Fail** | Pyrokinesis is cut as a six-mana off-plan card without respecting its alternate free-cast mode in a high-power list. |
| 08 | **Fail** | Blink cards appear, but Chromatic Lantern is removed from a demanding budget four-color mana base; generic premium cards crowd out fixing/blink value. |
| 09 | **Fail** | V2 finds a real cheap outlet, but the top-five prices exceed the deck's approximate total-budget identity and two choices lack sufficient package evidence. |
| 10 | **Fail** | Energy counters are falsely treated as Vadrik counter support and Urabrask is cut without recognizing its spell-chain value. |
| 11 | **Fail** | One-shot Unearth and Commander's Plate outrank better permanent-engine choices; Culling Ritual and Trinket Mage are unsafe optimized-shell cuts. |
| 12 | **Fail** | Casual combat/typal cards dominate instead of cEDH interaction and compact wins; three top-five cards overlap budget Yuriko. |
| 13 | **Fail** | Casual token/combat utility dominates; To Arms! is mislabeled as extra combat and no top-five card addresses tournament interaction or compact lines. |
| 14 | **Partial** | The engine correctly returns only donation cards and makes no cuts, but Gilded Drake violates the declared low-power jank experience. |
| 15 | **Fail** | The land warning and preservation behavior are correct, but Grist itself is suggested as an addition and an unrelated +1/+1-counter card leads. |
| 16 | **Pass** | Extreme repetition is detected; additions, cuts, and swaps are all paused. |
| 17 | **Pass** | The 98-card state and missing commander are preserved; analysis is blocked with exact reasons. |
| 18 | **Pass** | The 23-card main deck, 24 submitted cards, and zero lands are preserved; severe incompleteness blocks analysis. |

Strict result: **6 pass, 2 partial, 10 fail**.

## Manual review of changed top choices

All 12 legacy/V2 top-choice changes received a decision. An approval means the
ordering change itself is defensible; it does not override another defect in
the same deck.

| ID | Legacy top | V2 top | Decision | Rationale |
|---:|---|---|---|---|
| 01 | Sword of Fire and Ice | Satoru, the Infiltrator | Approved | Much cheaper and directly on-type with card flow. |
| 02 | Glissa Sunslayer | Selvala, Heart of the Wilds | Approved | On-type mana/card-flow upgrade; failure is in cuts. |
| 04 | Sheltered by Ghosts | Darksteel Mutation | Approved | Both are valid Aura-toolbox choices. |
| 05 | Kozilek's Command | Three Steps Ahead | Approved | Prefers an on-plan blue spell over generic token material. |
| 06 | Volatile Stormdrake | Pyroblast | **Defect** | Generic interaction displaces donation and is poorly budget-calibrated. |
| 07 | Goblin Trashmaster | Hexing Squelcher | **Defect** | Roughly one fifth of the total deck budget without stronger evidence. |
| 09 | Nuka-Cola Vending Machine | Vampiric Rites | Approved | Replaces an over-budget generic payoff with a cheap explicit outlet. |
| 10 | Izzet Generatorium | Arcane Denial | Approved | Better competitive spell, though the energy mismatch remains second. |
| 11 | Life from the Loam | Unearth | **Defect** | One-shot nonpermanent recursion displaces a proven optimized graveyard engine. |
| 12 | Combat Research | Mask of Memory | **Defect** | Neither choice reflects cEDH priorities. |
| 13 | Diamond Pick-Axe | Idol of Oblivion | **Defect** | Generic token draw replaces generic combat utility, not a tournament need. |
| 15 | Nuka-Cola Vending Machine | Ozolith, the Shattered Spire | **Defect** | Cheaper but still an unrelated counter plan; illegal commander duplication also remains. |

Six changes are approved and six are labeled defects.

## Promotion gates

| Gate | Result | Evidence |
|---|---|---|
| 18 immutable snapshots import with exact commander and quantities | **Pass** | JSON/text hashes, commander markers, quantities, and counts all match. |
| Four negative controls take expected warn/pause/block path | **Pass** | Cases 15–18 match every expected input code and state. |
| At least 15 strict passes with no critical control failure | **Fail** | 6 strict passes. |
| Yuriko budget/cEDH outputs materially differ | **Fail** | Three of five V2 cards overlap and cEDH priorities are absent. |
| Zedruu decks preserve distinct power/play experiences | **Fail** | Output is differentiated, but Gilded Drake violates the jank power target. |
| No top-five addition violates declared intent | **Fail** | Budget, competitive, power, and commander-duplication violations remain. |
| No cut removes declared protection or a measured floor | **Pass** | Protected packages and enforced floors survive, although unmodeled strategic-value cuts still fail case review. |
| Every paired swap states preserved role and marginal gain | **Pass** | The required explanation fields are present. |
| Severe mana defects lead repair unless explicitly preserved | **Pass** | Case 15 explicitly preserves low lands; warning remains and repair is suppressed. |
| Synthetic calibration and automated tests pass | **Pass** | Both 14-case ranker benchmarks and the eight deck-role cases pass. |
| Every changed top choice is manually reviewed | **Pass** | 12 decisions recorded above. |

The overall gate is **failing**. A passing input or structural-invariant gate
does not compensate for ranking or semantic recommendation failures.

## Required implementation before another review

1. Exclude the active commander and commander-zone cards from all addition
   candidate pools.
2. Model alternate/free casting and strategic engine utility in cuts, not only
   printed mana value, broad themes, and raw role coverage.
3. Add competitive labels for efficient interaction, enablers, and compact win
   packages; a low mana value alone is not cEDH evidence.
4. Make budget ranking sensitive to the stated total-deck context when no
   per-card cap exists, while remaining explicit that this is a soft target.
5. Separate named counter resources and distinguish untap effects from actual
   extra-combat effects.
6. Treat declared desired experience and closing payoffs as enforceable review
   features, not display-only prose.

Until those issues are implemented and this exact immutable set is rerun, V2
must remain shadow-only.
