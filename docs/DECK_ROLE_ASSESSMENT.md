# Deck Role Assessment and Marginal Utility

Deck analysis now keeps two views of every core role:

- **Raw count**: how many cards contain text associated with the role.
- **Effective count**: the sum of conservative 0–1 reliability contributions
  from those cards.

This prevents ten incidental cantrips, self-only Ward creatures, land-to-hand
effects, or highly conditional answers from being treated as ten dependable
sources. Raw counts remain in the response for transparency and backward
compatibility.

## Effective coverage

`DeckRoleAssessor` evaluates draw, ramp, removal, sweepers, stack interaction,
and protection. The contribution considers:

- mana value and setup cost;
- repeatable versus one-shot output;
- broad versus narrow answer scope;
- conditions such as combat damage or commander dependence;
- real acceleration versus merely finding a land; and
- protection that can save deck assets versus a card protecting only itself.

The result is exposed under `stats.role_quality`. Each role includes raw and
effective counts, the target band, effective gap, suggested additions, status,
and per-card contributions. A `quality_gap` means the raw count reaches the
floor but the reliable coverage does not.

Configure `DECK_ROLE_ASSESSMENT_MODE` as:

- `effective`: use effective gaps to drive suggestions. This is the default.
- `shadow`: calculate and report effective coverage but use raw gaps.
- `raw`: use count-only gap detection as the rollback path.

The admin `/api/admin/scryfall-cache` diagnostic reports the mode, assessment
version, assessment count, changed gap sets, hidden quality gaps, change rate,
and the ten most recent raw/effective differences. Recent gap records contain
role names only and retain no deck, user, commander, or card identity.

## Marginal utility

Every deck addition now records:

- `marginal_utility` on a bounded 0–100 scale;
- `effective_role_gain` and all `role_gains`;
- effective coverage before and after the addition; and
- the applicable role floor.

Ranking receives positive evidence for dependable coverage and multi-role gap
coverage. Weak role riders receive an explicit reliability penalty. Reasons
state the estimated effective gain and the movement toward the deck's floor,
so the user can see why the card helps this list rather than only why the card
is generally playable.

Replacement requests use the same full-pool filtering and ranking path as the
main analysis. They no longer return the first legal search result.

## Safe swap pairing

The API returns explicit `swap_pairs` instead of relying on positional pairing
between independent addition and cut lists. A proposed cut is rejected when it
would:

- push a covered role below its minimum;
- make an existing role deficit worse without the addition replacing that
  coverage; or
- erase more of the same role than the proposed upgrade adds.

Each pair includes a net role gain, confidence, and explanation. If no listed
cut is safe, the addition is presented as a standalone option instead of
inventing a one-for-one swap.

## Regression gates

The golden benchmark includes deck cases for draw reliability, true ramp,
answer flexibility, and protection scope, in addition to commander semantic
cases. Focused unit tests cover hidden quality gaps, rollback behavior,
multi-role utility, scarce-role cut protection, and ranked replacements.

Run both ranking paths before promotion:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker legacy
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py --ranker v2
backend\.venv\Scripts\python.exe -m pytest tests\test_deck_role_assessment.py -q
```
