# Cloudflare frontend deployment guide

LandFall AI uses Cloudflare Workers Static Assets for the React frontend while retaining the existing backend and data services:

```text
Browser -> landfallai.live on Cloudflare
        -> api.landfallai.live on Render
        -> MongoDB Atlas
```

This design keeps the validated V2 recommendation engine unchanged, requires no Cloudflare Container, and fits Cloudflare's free Workers Static Assets plan. MongoDB Atlas remains the production database.

## Candidate catalog distribution

The private `landfall-ai-catalog` R2 bucket stores immutable, compressed
Scryfall releases. The Worker exposes only these read-only paths:

```text
/catalog/manifest.json
/catalog/releases/<sha256>.json.gz
```

The manifest revalidates on every request; release objects are immutable for a
year. The backend downloads only at startup, verifies the compressed and
uncompressed sizes and SHA-256 hashes, validates the catalog envelope and card
count, then atomically activates the snapshot. A failed refresh or validation
uses the last-known-good file or live Scryfall search.

Create a new release locally:

```powershell
.venv\Scripts\python.exe backend\scripts\sync_scryfall_catalog.py
.venv\Scripts\python.exe backend\scripts\package_scryfall_catalog.py
```

Upload the immutable release and versioned rollback manifest first. Upload the
current manifest last so readers can never observe a manifest before its
artifact exists:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID='67cb3cabfef7ae0b67f864d8c8a1cf65'
npx wrangler r2 object put landfall-ai-catalog/catalog/releases/<sha256>.json.gz --file <release-path> --content-type application/gzip --cache-control "public, max-age=31536000, immutable" --remote
npx wrangler r2 object put landfall-ai-catalog/catalog/manifests/<sha256>.json --file <versioned-manifest-path> --content-type application/json --cache-control "private, max-age=0" --remote
npx wrangler r2 object put landfall-ai-catalog/catalog/manifest.json --file <manifest-path> --content-type application/json --cache-control "public, max-age=0, must-revalidate" --remote
```

Do not publish a newly synced catalog until the benchmark, calibration, fresh
18-deck run, output-drift review, and memory gate pass. Versioned manifests are
retained privately for rollback. Promoting one as `catalog/manifest.json` and
restarting Render restores that catalog without deleting newer releases.

## Deployment target

The Wrangler configuration is pinned to:

- Account: `Chasingshipsonahorizon@gmail.com's Account`
- Account ID: `67cb3cabfef7ae0b67f864d8c8a1cf65`
- Worker: `landfall-ai`

Verify the active identity before every deployment:

```powershell
npm run cf:whoami
```

## Build and validate

```powershell
npm install
npm run cf:dry-run
```

The Cloudflare frontend build intentionally sets:

```text
REACT_APP_API_URL=https://api.landfallai.live
REACT_APP_BACKEND_URL=https://api.landfallai.live
```

The public Turnstile site key currently used by `landfallai.live` is included in the build helper. It can be overridden by setting `REACT_APP_TURNSTILE_SITE_KEY` before building.

The frontend's `public/_headers` file gives fingerprinted `/static/*` assets a
one-year immutable browser cache and applies baseline security headers to every
frontend response. Keep `index.html` revalidated so deployments become visible
without waiting for an old application shell to expire.

## Deploy and validate

Deploy the static assets and configured custom-domain triggers:

```powershell
npm run cf:deploy
```

Verify:

- Landing page and client-side routes load directly and after refresh.
- Registration and login succeed.
- Auth cookies are accepted when the frontend calls `api.landfallai.live`.
- Deck import and one full analysis complete.
- Commander suggestions return expected results.
- Logout succeeds.
- `https://landfallai.live/catalog/manifest.json` returns the expected version.
- `https://api.landfallai.live/api/` reports the same loaded catalog version and
  card count.

The Render backend must continue to allow these CORS origins with credentials:

```text
https://landfallai.live
https://www.landfallai.live
```

Wrangler disables the `workers.dev` route when the custom-domain routes are present. If a future preview deployment explicitly enables `workers_dev`, add that exact origin to `CORS_ORIGINS` on Render only for the duration of authenticated testing.

## Production domain cutover

The production cutover completed on November 5, 2026. The `landfall-ai` Worker owns these Custom Domains through `wrangler.jsonc`:

- `landfallai.live`
- `www.landfallai.live`

The domain uses Cloudflare's assigned authoritative nameservers:

- `alexa.ns.cloudflare.com`
- `jacob.ns.cloudflare.com`

The obsolete Render frontend records at the zone apex and `www` were removed before Wrangler created the Worker-managed records. Keep these records DNS-only:

- `api.landfallai.live` -> `landfall-ai-cpoo.onrender.com`
- `brevo1._domainkey.landfallai.live` -> Brevo DKIM
- `brevo2._domainkey.landfallai.live` -> Brevo DKIM

Keep `api.landfallai.live` pointed at the Render backend. Do not remove the Render web service or MongoDB Atlas database. Preserve the imported MX, SPF, DMARC, Brevo verification, and Google verification records.

Update the Turnstile widget's allowed hostnames if necessary, then repeat registration, login, deck analysis, and logout on the production domain.

The initial production deployment version was `c4833d49-566f-4d94-9fa7-565758d9201a`. Cutover validation confirmed HTTP 200 responses for the apex, `www`, a direct client-side route, and the Render API. Credentialed CORS preflights pass for both production frontend origins.

## Rollback

If production validation fails, restore the previous Render frontend DNS/custom-domain target. The backend and MongoDB never move, so rollback requires no database migration or restore.
