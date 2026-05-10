# Archetype Signal Map

Purpose: describe how `backend/data/archetype_signal_registry.json` should be used.

## Layer Responsibilities

- Mechanics registry: detects individual mechanics and keywords.
- Archetype signal registry: scores composite strategies from multiple reusable signals.
- Enhanced suggestion engine: extracts raw signals, scores archetypes, and maps top archetypes back to recommendation lanes.
- Reason builder: explains the bridge between a recommended card and the detected plan.

## Signal Flow

1. Extract raw signals from commander text, mana value, type line, color identity, and optional deck stats.
2. Score archetypes from required, supporting, and reject signals.
3. Add only the resulting broad lanes needed for searching and ranking.
4. Use the matched archetypes to shape pilot notes, recommendation quality, and why-it-fits copy.

## Registry Entry Expectations

Each archetype should define:

- Required signals that must exist.
- Supporting signals that raise confidence.
- Reject signals that prevent false positives.
- Primary and secondary needs.
- Recommendation focus.
- Avoided recommendations.
- Pilot note guidance.
- Reason builder guidance.

Examples are QA anchors only. They do not drive logic.

## False-Positive Discipline

Common reject patterns:

- `combat_only_payoff` should block noncombat value archetypes.
- `typal_only_payoff` should block generic value/control readings.
- `cheap_aggressive_commander` should block late-game control readings.
- `sorcery_speed_engine_required` should block reactive flash-control readings.
- `normal_reanimation_plan` should block donation/drawback-abuse readings.

## Current First-Pass Archetype Coverage

The initial registry covers broad Commander plans such as control finishers, low-curve value, enchantment toolbox, Voltron, artifact recursion, artifact-token economy, aristocrats, reanimator, spellslinger, targeted spells, lands engines, counters, proliferate, blink, tokens, typal, combat, goad, lifegain, discard/graveyard value, stax, colorless big mana, donation, temporary-effect abuse, flash control, and hand-size pressure.
