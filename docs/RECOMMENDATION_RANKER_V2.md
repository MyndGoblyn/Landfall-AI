# Recommendation Ranker V2

Ranker V2 is an evidence-first ordering layer for commander and deck-addition
suggestions. It does not replace the engine's hard legality, commander-context,
or minimum-quality filters. It ranks only candidates that already passed those
checks.

## Why it exists

The legacy rank multiplied each branch quality score by 100. Evidence tags,
penalties, efficiency, and role diversity therefore acted mostly as tie-breakers.
V2 caps the legacy branch assessment at 18 points and builds a bounded 0–100
score from independently inspectable components:

- plan alignment;
- functional value;
- mechanic or constraint corroboration;
- the capped legacy quality assessment;
- mana efficiency appropriate to setup versus payoff jobs;
- evidence density;
- a small source-popularity prior; and
- explicit context penalties.

Hard mismatch penalties such as wrong token type, unrelated counter context,
dead colorless mana, and wrong card type outweigh superficial positive tags.
Job and role diversity are applied on the same normalized scale, so they can
materially affect a final list instead of disappearing next to a score in the
thousands.

V2 also ranks the recommendation portfolio rather than treating five isolated
cards as the final product. It taxes repeated generic jobs, applies a combined
budget-share ceiling, gives confirmed plan-specific evidence precedence, and
abstains when the remaining deck candidate score is below the evidence floor.
Each served V2 result includes the bounded rank assessment and a selection note
whose claim is generated from that assessment.

## Shared semantic safety layer

`services/card_function_profile.py` supplies facts used by additions, cuts, and
reasons together. It distinguishes printed from practical casting mode,
alternate-cost interaction, explicitly named counter resources, real additional
combat phases, untap support, repeatable engines, closing payoffs, multicolor
fixing, typed tutors, and high-leverage interaction.

The active commander, every supplied commander-zone card, modal faces, and
already-owned cards are excluded before ranking. Missing transform/modal face
data is hydrated before semantic review. Heuristic cuts abstain on strategic
functions unless deterministic replacement evidence exists; returning no cut
is an acceptable and preferred result when safety is uncertain.

## Competitive evidence

Competitive mode uses the versioned
`backend/data/competitive_card_labels.json` registry for efficient/free
interaction, acceleration, tutors, card advantage, enablers, and compact win
components. Package components with prerequisites are admitted only when a
compatible card is already present. Mana value alone never creates competitive
evidence. The registry is deliberately conservative and must be reviewed and
versioned as competitive card pools change.

## Rollout modes

Configure `RECOMMENDATION_RANKER_MODE` as one of:

- `legacy`: serve only legacy ordering; immediate rollback path.
- `shadow`: serve legacy ordering, calculate V2 from its own per-query
  shortlists, and record comparisons.
- `v2`: serve V2 ordering while still calculating legacy comparisons. This is
  the default after the 2026-08-04 promotion review passed every gate.

The admin `/api/admin/scryfall-cache` diagnostic exposes the active mode,
ranker version, order/top-choice comparison counters, and the ten most recent
top-choice changes. It also reports per-kind candidate overlap and comparison
rates. No user response is changed in `shadow` mode.

## Regression gates

Both paths must clear the same labeled benchmark:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker legacy
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker v2
```

The benchmark currently covers target scaling, creature-token semantics,
board conversion, enchantment tutor limits, named counters, spell chains, deck
draw quality, real acceleration, removal flexibility, protection scope,
own-creature targeting, permanent graveyard engines, and typal
payoff-versus-body distinctions. Each case gates recall, precision, NDCG, hard
rejections, and grounded reason evidence.

## Evidence corrections included with V2

The rollout work also tightened the evidence supplied to either ranker:

- matching a creature type line alone is density, not direct typal synergy;
- off-type personal attack triggers do not enter a typal combat lane;
- graveyard words that only describe spell resolution are not a graveyard plan;
- own-creature targeting commanders reject burn/removal that cannot create a
  useful repeatable loop;
- permanent-recursion commanders down-rank redundant one-shot reanimation; and
- own-graveyard exile is not mislabeled as graveyard value.

Additional promotion corrections include:

- energy, experience, +1/+1, and other named counters remain separate;
- untapping attackers is never described as creating another combat phase;
- cards with alternate/free casting modes are not cut on printed mana value;
- a declared total-deck budget creates soft per-card and portfolio pressure;
- low-power preserve modes can reject curated power outliers; and
- competitive recommendations require a curated function or compatible package.

The immutable 18-deck review and labeled calibration are green, so new
environments default to `v2`. Keep representative production comparisons under
review; rollback to `shadow` or `legacy` is a single environment change.

Use `backend\scripts\run_recommendation_calibration.py` for the combined
promotion decision. Any later failing report blocks further rollout and should
trigger review of whether the environment must return to `shadow`.
