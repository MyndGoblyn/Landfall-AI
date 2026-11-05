# V3 Planner Real-Deck Validation Report

**Evaluation date:** 2026-11-05 (America/New_York)  
**Validation set:** 18 immutable Commander snapshots  
**Reviewed output:** Planner V3 with Evidence Ranker V2, fast/default analysis  
**Decision:** **V3 satisfies the controlled-promotion gate.**

## Verdict

All 18 fixtures passed integrity and expected-input-path checks. The 14
analyzable decks produced manually reviewed, intent-compatible output; the four
negative controls retained their required warning, review, or block behavior.
No protected-package cut, illegal recommendation, competitive evidence leak,
or negative-net-role swap was found.

Engineering confidence that V3 achieves the requested quality and versatility
goals on the covered Commander use cases is **0.93**. This is an engineering
assessment, not a statistical probability or a claim of universal card-game
accuracy. Remaining uncertainty is concentrated in unregistered archetypes,
new rules/card interactions, rapidly changing competitive packages, and intent
combinations not represented by these fixtures.

## Reproducible evidence

- Catalog: `oracle_cards:2026-11-05T10:02:05.865+00:00` (39,287 cards)
- Raw artifact: `test_reports/real_deck_validation_v3_release_candidate.json`
- Raw SHA-256: `38341b8cbb50d45af844612ee52b3211f49c5226bf78f9ce382a0b6250d8445c`
- Average V3 analysis: 1,351.18 ms
- Average addition retrieval/ranking: 1,167.38 ms
- Maximum V3 analysis: 1,861.98 ms
- Backend tests: 229 passed
- Cloudflare TypeScript and production dry-run builds: passed

Reproduction command:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_real_deck_validation.py `
  --fixture-dir tests\fixtures\real_deck_validation\2026-08-04 `
  --output test_reports\real_deck_validation_v3_release_candidate.json
```

## Reviewed outcomes

| ID | Deck | Result | V3 reviewed behavior |
|---:|---|---|---|
| 01 | Budget Yuriko | Pass | Ninja density, removal, budget ramp/draw, protection, then budget interaction |
| 02 | Budget Lathril | Pass | Token draw, protection, Elf ramp, on-plan sweeper, flexible removal |
| 03 | Budget Meren | Pass | Affordable draw, utility, interaction, counter support, sacrifice outlet |
| 04 | Light-Paws | Pass | Tutorable Aura removal/protection leads; no high-cost Aura false positive |
| 05 | Budget Talrand | Pass | Efficient spell, protection, token payoff, and card-flow mix |
| 06 | Political Zedruu | Pass | Only concrete donation/exchange effects survive |
| 07 | High-power Krenko | Pass | Goblin/token velocity, protection, and engine support |
| 08 | Atraxa Blink | Pass | Blink cantrips, protection, removal, and repeatable blink support |
| 09 | Budget Wilhelt | Pass | Zombie/sacrifice value, removal, recursion/protection, and ramp fodder |
| 10 | Budget Vadrik | Pass | Five low-cost curated stack-interaction choices |
| 11 | Optimized Muldrotha | Pass | Curated interaction, acceleration, tutor, protection, and reset |
| 12 | cEDH Yuriko | Pass | Curated interaction, acceleration, card advantage, and reset |
| 13 | cEDH Najeela | Pass | Curated interaction, tutor access, and red stack protection |
| 14 | Janky Zedruu | Pass | One concrete exchange card; no blind power optimization |
| 15 | 18-land Grist | Pass | Severe mana warning retained; premise preserved; no cuts proposed |
| 16 | 97-Mountain joke | Pass | Recommendations paused pending constraint confirmation |
| 17 | Unfinished Urza | Pass | Missing commander and incomplete list block analysis |
| 18 | Partial Lathril | Pass | Severe incompleteness blocks fabricated optimization |

## Specific regression evidence

- Interaction and draw explanations no longer inherit the previous candidate's
  lane within a query.
- Full multi-lane coverage determines visible ordering, so a stronger on-plan
  card is not demoted merely because its primary lane already appeared.
- Cards that only make opponent tokens are not token support for the user.
- Landcycling and hand-only land search are not counted as acceleration.
- Self-only mass exile is not a board wipe.
- A card that sacrifices itself for its own effect is not automatically a
  sacrifice engine for Meren.
- Talrand no longer receives the reviewed token, sweeper, or ramp false
  positives.
- Light-Paws no longer receives an uncastable high-mana Aura recommendation.
- Competitive mode requires exact curated registry evidence.
- V3 pairing rejects every negative-net-role exchange and may abstain on cuts.

## Semantic release

- Semantic version:
  `semantic:2eb6417cc286ccdfafa201d2f39b8006471379a3e41ffc5b053d5d89096b1e4a`
- Compressed release SHA-256:
  `538b61496aff90a671269a4162f5665a917335a925760cdd87756509657e06f6`
- Resources: 298 mechanics, 30 archetypes, 48 competitive registry entries
- Cloudflare Worker deployment:
  `31d7a8b4-9303-4e14-bea2-13124e0d7877`
- Live manifest and release download passed complete checksum, size, schema,
  semantic-version, and per-resource verification.

## Promotion and rollback

Production may serve V3. Preserve `shadow` as the immediate planner rollback
and keep Ranker V2's independent rollback setting. Monitor abstention, changed
top choices, dynamic-overlay failures, semantic refresh state, and user
corrections. Any critical intent, legality, protected-package, or cut-safety
failure requires rollback and a new frozen regression fixture.
