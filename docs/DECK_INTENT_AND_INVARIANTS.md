# Deck Intent and Invariant Enforcement

LandFallAI stores a user-owned `DeckIntentProfile` with each deck. The profile
separates facts the user knows from patterns the engine infers. Inference can
supplement this profile, but it must not silently replace it.

## Intent contract

The version 1 profile records:

- whether the profile is confirmed;
- minimum and maximum target power;
- strict, target, flexible, unrestricted, or unknown budget handling;
- total budget context and an enforceable maximum price per suggested card;
- preserve, tune, competitive, or repair optimization mode;
- primary strategy and desired play experience;
- structured strategy priorities, desired-experience tags, and cut-protected
  strategic roles;
- explicit power-outlier and generic-staple tolerance;
- individually protected cards and named protected packages;
- excluded recommendation cards; and
- intentional typal, spell-density, jank, flavor, land, fast-mana, tutor, and
  combo constraints.

Existing decks receive an unconfirmed `preserve` profile. This is intentionally
fail-safe: additions are marked as intent-unconfirmed, while cuts are limited to
two candidates and capped at 0.48 confidence until the owner confirms the deck's
goals.

The profile can be saved through `PUT /api/decks/{deck_id}/intent` or included
in an analysis request. Analysis requests persist the supplied profile before
running so replacement requests and later deep analyses use the same contract.

## Enforced behavior

| Declared intent | Deterministic behavior |
|---|---|
| Protected card/package | Never enters the cut candidate pool |
| Excluded card | Never enters the addition candidate pool |
| Strict per-card price cap | Reject candidates above the cap or without a verifiable current price |
| Target/flexible card cap | Keep the candidate with a disclosed warning and ranking penalty |
| Total deck budget without a card cap | Apply soft per-card share and combined recommendation-portfolio pressure |
| No fast mana | Reject known or text-confirmed zero/one-mana burst artifacts |
| No nonland tutors | Reject nonland library-search candidates while retaining land-ramp searches |
| Competitive target | Reward efficient/alternate-cost role cards and penalize generic cards above three mana without an alternate cost |
| Preserve intentional jank/flavor | Abstain from generic role goodstuff and all cuts; retain directly evidenced plan cards |
| Low-power/political power preservation | Reject curated high-power outliers even when they superficially match the plan |
| Structured strategy priority | Reward matching recommendation lanes and protect declared closers, engines, or fixing roles |
| V2 competitive evidence | Require a versioned competitive function or compatible compact-package prerequisite |
| Unconfirmed intent | Lower addition confidence and severely restrict cut confidence/count |
| No infinite combos | Suppress generated combo lines; package-level detection remains a later stage |
| Severe land shortage | Put a quantified multi-slot land repair ahead of ordinary synergy suggestions |
| Confirmed preserve + intentional low lands | Respect the risk premise and suppress automatic land repair |

Every affected recommendation carries its intent alignment, warnings, score
delta, and explanation in the API response and analysis UI.

## Measurable invariants

When `typal_core` is declared, the analyzer quantity-weights creature subtypes,
identifies a sufficiently dense primary type, and records the current on-type
floor. On-type cards and matching creature tokens receive explicit evidence.
Off-type creature suggestions are penalized, and generic token/creature lanes
that do not create the declared type are rejected.

When `spell_density` is declared, the analyzer records the current
instant/sorcery count and nonland share. The spell-plan lane requires an instant
or sorcery.

Aura-tutor commanders automatically receive an Aura-ladder invariant. It tracks
total and unique Auras, mana-value coverage, and missing core rungs from one
through four. Aura-specific recommendation lanes reject non-Auras, missing rungs
receive a measured boost, and cutting the only Aura at a mana value requires a
same-rung Aura replacement.

Card-type-diversity commanders track the card types named by their ability.
Scarce types are protected across swaps, while role-valid candidates that fill
an underrepresented type receive explicit evidence. Merely enumerating card
types no longer creates unrelated artifact, enchantment, creature, or
spellslinger themes. Permanent-recursion commanders use the same framework for
permanent types and penalize one-shot nonpermanent role cards without banning
necessary stack interaction.

Sacrifice commanders track three engine components separately: repeatable
outlets, death/sacrifice payoffs, and reusable or token fodder. Deficient
components receive priority, while scarce outlets/payoffs/fodder require a
like-for-like replacement.

Named protected packages are editable in the analysis UI. Their members are
excluded from cuts, present and missing cards are reported together, and a
missing declared member receives package evidence if it appears in an otherwise
valid candidate lane. The engine does not invent undeclared package membership.

Cuts that occupy an enforced invariant receive a like-for-like replacement
requirement. The swap mapper will not pair that cut with an addition lacking all
required traits. Standalone cut reasoning states the same requirement.

When a complete deck contains 20 or fewer lands, the analyzer now creates a
critical multi-slot repair action to reach a conservative 30-land functional
floor. The action is not paired with one cut because it represents several deck
slots. A confirmed `preserve` profile with `low_land_count` suppresses that
repair; selecting `repair` explicitly restores it.

## Structured intent resolution

The UI exposes the structured fields directly. For older confirmed profiles
that contain only strategy/experience prose, a bounded vocabulary resolver can
populate the same fields from explicit terms. It recognizes nearby negation, so
phrases such as "without converting to cEDH" do not activate competitive mode.
The original prose remains visible, while filtering and scoring use the
inspectable structured result.

## Known boundaries

- A total deck budget is a soft ranking target because complete historical deck
  prices are not always available. A per-card cap remains the only hard price
  filter.
- Free-form intent is not treated as unrestricted rules language. Only the
  documented bounded vocabulary is resolved; users can edit the structured
  result directly.
- Combo suppression is reliable for generated combo advice, but detecting every
  emergent infinite interaction requires curated, human-labeled combo data.
- Aura ladders, card/permanent-type spread, sacrifice components, declared
  packages, typed tutor targets, and exact named-card links are enforced.
  Strategic dependencies not stated in oracle text remain outside automatic
  discovery.
- The immutable 2026-08-04 baseline remains historical evidence. A candidate
  implementation must receive a new reviewed rerun before the machine-readable
  promotion status changes.
## Deterministic dependency discovery

LandfallAI also derives a bounded dependency graph from card oracle text. It
recognizes explicit typed library searches (including type, subtype, and
numeric mana-value limits) and exact named-card links such as `partner with`
or `card named`.

- Tutor packages are reported as healthy (three or more distinct in-deck
  targets), fragile (one or two), or dead (zero).
- A candidate that restores a dead or fragile tutor target receives bounded,
  inspectable evidence; it does not bypass legality, budget, role, or quality
  validation.
- Cutting a target from a fragile package requires a replacement that satisfies
  the same tutor restriction.
- Cards in exact named links are excluded from automatic cuts. A missing exact
  target receives an evidence boost if it enters the validated candidate pool.

This is not a combo detector. It does not infer loops, strategic dependencies,
or interactions that are not stated explicitly in oracle text. Those require a
separately curated, human-labeled package dataset before they can safely affect
recommendations.
