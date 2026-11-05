# LandFall AI QA Checklist

Run this before pushing user-facing changes.

## Automated Checks

- `cd frontend && npm.cmd run smoke:source`
- `cd frontend && npm.cmd run build`
- `npm.cmd run cf:dry-run`
- `backend\\.venv\\Scripts\\python.exe backend\\scripts\\run_recommendation_benchmark.py`
- `backend\\.venv\\Scripts\\python.exe backend\\scripts\\run_recommendation_benchmark.py --ranker v2`
- `backend\\.venv\\Scripts\\python.exe backend\\scripts\\run_recommendation_calibration.py`
- `backend\\.venv\\Scripts\\python.exe backend\\scripts\\run_real_deck_validation.py --fixture-dir tests\\fixtures\\real_deck_validation\\2026-08-04 --output test_reports\\real_deck_validation_2026-08-04_raw.json`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests\\test_deck_role_assessment.py -q`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests\\test_deck_parser.py tests\\test_deck_input_assessment.py -q`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests\\test_deck_intent.py tests\\test_deck_invariants.py tests\\test_deck_dependencies.py -q`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests\\test_card_function_profile.py tests\\test_competitive_registry.py tests\\test_v2_promotion_safety.py -q`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests\\test_local_candidate_provider.py -q`
- `backend\\.venv\\Scripts\\python.exe -m pytest -q`

## Real-Deck Calibration

- Use immutable dated plain-text exports; treat live Moxfield and Archidekt URLs
  as importer smoke tests only.
- Verify exact main-deck, submitted-card, land, unique-card, and commander counts.
- Confirm missing commanders and severely incomplete lists block analysis with a
  useful reason.
- Confirm extreme repetition and declared joke constraints pause ordinary
  optimization rather than silently repairing the deck.
- Compare budget and cEDH versions of the same commander; recommendations must
  differ in cost, speed, interaction, and combo expectations.
- Compare political and intentionally janky versions of the same commander;
  cuts must preserve the declared experience and protected bad-gift packages.
- Verify every proposed cut preserves typal density, spell density, required
  roles, engine pieces, and declared protected cards.
- Verify severe land/source defects receive a mana-repair recommendation before
  ordinary synergy upgrades unless the constraint is explicitly preserved.
- Confirm the severe-land action reports the number of land slots needed to
  reach its stated floor and is never paired with a single cut.
- Record manual approval or a labeled defect for every legacy/V2 top-choice
  change.
- Confirm unconfirmed intent limits cuts to two candidates at no more than 0.48
  confidence.
- Confirm strict budget mode rejects both over-cap and unpriced suggestions.
- Confirm total-budget target mode penalizes a single recommendation that
  consumes an excessive share and the V2 portfolio does not silently exceed its
  combined soft share.
- Confirm named counter resources do not cross-match and an untap spell is never
  labeled as an additional combat phase.
- Confirm alternate-cost interaction, repeatable engines, closing payoffs,
  multicolor fixing, and typed tutors do not enter heuristic cuts without
  explicit replacement evidence.
- Confirm competitive recommendations carry a versioned curated function or a
  compatible package prerequisite; low mana value alone is insufficient.
- Confirm protected cards and every card in a protected package are absent from
  cuts and swap pairings.
- For declared typal or spell-density decks, confirm each swap preserves the
  recorded on-type or instant/sorcery floor.
- For Aura-tutor decks, confirm a unique mana-value rung can only be replaced by
  another Aura at that rung.
- For card-type and permanent-recursion decks, confirm scarce types survive each
  swap and type enumeration does not create generic artifact/enchantment themes.
- For sacrifice decks, review outlet, payoff, and fodder counts separately;
  scarce components require like-for-like replacements.
- Confirm protected package members never appear as cuts and missing declared
  members are reported without inventing undeclared combo relationships.
- For every typed tutor, review the eligible-target count and any mana-value or
  subtype restriction. A fragile target cut must receive a legal target swap.
- Confirm exact named-card links are absent from automatic cuts, missing named
  cards are disclosed, and ordinary land ramp creates no dependency package.
- Confirm the UI and Markdown export state that dependency discovery is
  deterministic and does not claim to infer combo lines.
- Do not promote V2 unless the latest dated real-deck report passes every gate in
  `docs/RECOMMENDATION_CALIBRATION.md`.

## Browser Smoke Pass

Use the local app at `http://localhost:3000`.

- Dashboard renders after auth and shows Commander Lookup, Random Commander, Deck Analysis, deck cards, and logout.
- Commander Lookup renders search, Deep Strategy, result sections, Pilot/Strategy tabs, Recommended Cards, and Find More Cards.
- Random Commander shows Colorless as a separate color identity option and keeps the strategy search box usable on mobile width.
- Deck Import switches between URL Import and Text Import, and loading copy appears after import starts.
- Deck Analysis renders Pilot Notes section tabs, Upgrade Board, Possible Cuts, Swap Map, Deep Analysis, and Export Markdown.
- Deck Health shows effective and raw role coverage; Swap Map explains explicit safe pairings and leaves an upgrade standalone when no cut preserves role floors.
- How It Works explains deterministic intelligence, regular search, Deep Strategy, response-time tradeoffs, and user expectations.

## Responsive Checks

Check at roughly `1280x720`, `900x700`, and `390x844`.

- Top navigation does not overlap or clip.
- Search controls stack cleanly on mobile.
- Recommended card images and text do not overlap.
- Section tabs scroll or wrap without hiding labels.
- Loading/status banners fit within the viewport.

## Commander Quality Samples

- `Zur the Enchanter`: should prioritize enchantments and toolbox planning.
- `Graaz, Unstoppable Juggernaut`: should avoid pretending every artifact is synergy.
- `Gimli of the Glittering Caves`: counter recommendations should not assume proliferate unless the card text supports it.
- `Vivi Ornitier`: lookup should resolve the specific commander.
- `Gimli`: broad lookup should offer commander options instead of failing silently.
