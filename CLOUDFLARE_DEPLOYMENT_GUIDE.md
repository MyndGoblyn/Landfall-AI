# Cloudflare frontend deployment guide

LandFall AI uses Cloudflare Workers Static Assets for the React frontend while retaining the existing backend and data services:

```text
Browser -> landfallai.live on Cloudflare
        -> api.landfallai.live on Render
        -> MongoDB Atlas
```

This design keeps the validated V2 recommendation engine unchanged, requires no Cloudflare Container, and fits Cloudflare's free Workers Static Assets plan. MongoDB Atlas remains the production database.

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
