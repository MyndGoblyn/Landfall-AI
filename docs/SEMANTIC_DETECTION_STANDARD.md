# Semantic Detection Standard

Purpose: keep LandFall AI's deterministic intelligence broad, evidence-led, and resistant to commander-specific patches.

## Core Rule

Detection must identify reusable patterns in card text, type line, color identity, mana value, and deck composition. Do not branch on a commander name to create a strategy result.

Commander names may appear in fixtures, examples, and QA reports. They must not drive production logic.

## Evidence Tiers

- Primary signal: text that defines what the commander rewards, enables, or restricts.
- Supporting signal: text that improves a plan only when primary evidence exists.
- Texture signal: a keyword or card type that may matter, but does not define the deck by itself.
- Reject signal: evidence that blocks or heavily penalizes an otherwise tempting match.

## Detection Rules

- A theme needs a payoff, enabler, or constraint. A single shared word is not enough.
- Support-only mechanics cannot become deck themes alone.
- Card type alone is not a strategy unless the text rewards that card type.
- Combat keywords are support unless the commander rewards attacks, combat damage, or commander damage.
- Counter text must preserve counter type and counter context.
- Token text must distinguish creature tokens from artifact/resource tokens.
- Graveyard text must distinguish recursion/value from graveyard hate.
- Flash is timing support unless the commander or deck has an instant-speed plan.
- Expensive commanders need a payoff before they become late-game control or big-mana profiles.

## Composite Archetypes

Composite archetypes are scored from signal combinations. For example:

- `high_mana_value_commander` + `major_payoff_text` can indicate a late-game control finisher.
- `combat_damage_trigger` + `evasion_needed` can indicate combat-damage value.
- `death_trigger` + `sacrifice_outlet` can indicate aristocrats.

The archetype registry owns those combinations. The mechanics registry should remain focused on mechanics and keywords.

## Required QA Standard

Every new detector must include:

- A positive case showing the intended pattern.
- A negative case showing the false positive it avoids.
- A reason-builder assertion when the detection affects recommended cards.
