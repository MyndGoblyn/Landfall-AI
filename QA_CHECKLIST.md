# LandFall AI QA Checklist

Run this before pushing user-facing changes.

## Automated Checks

- `cd frontend && npm.cmd run smoke:source`
- `cd frontend && npm.cmd run build`
- `backend\\.venv\\Scripts\\python.exe -m pytest tests backend_test.py`

## Browser Smoke Pass

Use the local app at `http://localhost:3000`.

- Dashboard renders after auth and shows Commander Lookup, Random Commander, Deck Analysis, deck cards, and logout.
- Commander Lookup renders search, Deep Strategy, result sections, Pilot/Strategy tabs, Recommended Cards, and Find More Cards.
- Random Commander shows Colorless as a separate color identity option and keeps the strategy search box usable on mobile width.
- Deck Import switches between URL Import and Text Import, and loading copy appears after import starts.
- Deck Analysis renders Pilot Notes section tabs, Upgrade Board, Possible Cuts, Swap Map, Deep Analysis, and Export Markdown.
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
