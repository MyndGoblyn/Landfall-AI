# LandFall AI Production Setup Guide

LandFall AI uses a split production architecture:

- Backend: Python FastAPI on Render from `backend`
- Frontend: React on Cloudflare Workers Static Assets from `frontend`
- Data: MongoDB Atlas

The primary public URL for the app is:

```text
https://landfallai.live
```

Recommended production domains:

```text
Frontend: https://landfallai.live
Optional www alias: https://www.landfallai.live
Backend API: https://api.landfallai.live
```

Do the setup in this order so each later step has the URLs and keys it needs.

## 1. Create MongoDB Atlas Database

The backend needs a persistent MongoDB database. Do not use the in-memory database in production.

1. Go to MongoDB Atlas and create a project.
2. Create a free or paid cluster.
3. Create a database user for this app.
4. In Network Access, allow Render to connect.
   - For an initial Render launch, `0.0.0.0/0` is the easiest option.
   - Tighten this later if you move to fixed egress networking.
5. Click Connect, choose Drivers, and copy the connection string.
6. Replace `<username>`, `<password>`, and any placeholder database name in the connection string.

Render backend variables from this step:

```text
MONGO_URL=mongodb+srv://<user>:<password>@<cluster-host>/?retryWrites=true&w=majority
DB_NAME=landfall_ai
USE_IN_MEMORY_DB=false
```

## 2. Create Render Backend Web Service

1. In Render, create a new Web Service.
2. Connect the GitHub repo: `MyndGoblyn/Landfall-AI`.
3. Use these service settings:

```text
Root Directory: backend
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: python start.py
Health Check Path: /api/
```

4. Add the backend environment variables below.

Core backend variables:

```text
ENVIRONMENT=production
MONGO_URL=<from MongoDB Atlas>
DB_NAME=landfall_ai
JWT_SECRET=<generated secret>
CORS_ORIGINS=https://landfallai.live,https://www.landfallai.live
APP_PUBLIC_URL=https://landfallai.live
USE_IN_MEMORY_DB=false
```

Generate `JWT_SECRET` with PowerShell:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Max 256 }))
```

For a temporary Cloudflare preview hostname, add only that exact origin while
testing and remove it after the custom domains are active.

## 3. Create Cloudflare Turnstile CAPTCHA

Turnstile gives you two values:

- Site key: public, used by the React frontend.
- Secret key: private, used only by the backend.

1. Go to Cloudflare Turnstile.
2. Create a new widget.
3. Add these hostnames:

```text
landfallai.live
www.landfallai.live
```

4. Copy the site key and secret key.

Backend Render variables:

```text
CAPTCHA_REQUIRED=true
TURNSTILE_SECRET_KEY=<secret key from Cloudflare>
```

Frontend build variable:

```text
REACT_APP_TURNSTILE_SITE_KEY=<site key from Cloudflare>
```

For local development, keep CAPTCHA disabled unless you are actively testing it:

```text
CAPTCHA_REQUIRED=false
REACT_APP_TURNSTILE_SITE_KEY=
```

## 4. Set Up Email Sending

Email is required for account verification and password reset. Use a transactional email provider such as Postmark, Brevo, Mailgun, or SendGrid. Gmail app passwords can work for testing, but a transactional provider is better for production deliverability.

You need SMTP settings from your provider:

```text
REQUIRE_EMAIL_VERIFICATION=true
SMTP_HOST=<smtp host>
SMTP_PORT=587
SMTP_USERNAME=<smtp username>
SMTP_PASSWORD=<smtp password or API key>
SMTP_FROM_EMAIL=<verified sender email>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20
EMAIL_PROVIDER=smtp
EMAIL_FROM_NAME=LandFall AI
BREVO_API_KEY=
```

Make sure `SMTP_FROM_EMAIL` is a sender address verified by your provider. If your provider gives you an API key for SMTP, it usually goes in `SMTP_PASSWORD`.

On Render free tier, use Brevo's HTTP API if SMTP delivery fails:

```text
EMAIL_PROVIDER=brevo_api
BREVO_API_KEY=<Brevo API v3 key>
SMTP_FROM_EMAIL=<verified Brevo sender email>
EMAIL_FROM_NAME=LandFall AI
```

Keep the SMTP variables in place if you want, but when `EMAIL_PROVIDER=brevo_api`, the app sends verification and reset emails through Brevo's HTTPS API instead of SMTP.

## 5. Deploy the Cloudflare Frontend

Follow [CLOUDFLARE_DEPLOYMENT_GUIDE.md](CLOUDFLARE_DEPLOYMENT_GUIDE.md).
The checked-in build helper pins the production API origin, and Wrangler's
`single-page-application` handling provides the React Router fallback.

## 6. Update Backend URLs After the Frontend Exists

Once the frontend custom domain is verified, go back to the backend service and update:

```text
CORS_ORIGINS=https://landfallai.live,https://www.landfallai.live
APP_PUBLIC_URL=https://landfallai.live
```

Then redeploy the backend.

## 6.5. Custom Domains

Cloudflare Worker custom domains own `landfallai.live` and
`www.landfallai.live`. Keep `api.landfallai.live` as a DNS-only record pointing
to the Render backend. Do not proxy or cache authenticated API responses at the
edge.

Production URLs:

```text
Primary app URL: https://landfallai.live
Backend API URL: https://api.landfallai.live
```

## 7. Cookie Settings

For the custom-domain setup with `landfallai.live` and `api.landfallai.live`, use:

```text
AUTH_COOKIE_NAME=landfall_session
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
```

Set this so the session cookie is scoped to your domain family:

```text
AUTH_COOKIE_DOMAIN=.landfallai.live
```

## 8. Rate Limit Settings

These defaults are good for launch:

```text
LOGIN_ATTEMPT_LIMIT=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15
AUTH_ACTION_ATTEMPT_LIMIT=5
AUTH_ACTION_WINDOW_MINUTES=15
```

## 9. Final Backend Env Var Checklist

Your backend Render service should have:

```text
ENVIRONMENT=production
MONGO_URL=<mongodb atlas connection string>
DB_NAME=landfall_ai
JWT_SECRET=<32+ character generated secret>
CORS_ORIGINS=https://landfallai.live,https://www.landfallai.live
APP_PUBLIC_URL=https://landfallai.live
USE_IN_MEMORY_DB=false
REQUIRE_EMAIL_VERIFICATION=true
CAPTCHA_REQUIRED=true
TURNSTILE_SECRET_KEY=<cloudflare secret key>
SMTP_HOST=<smtp host>
SMTP_PORT=587
SMTP_USERNAME=<smtp username>
SMTP_PASSWORD=<smtp password or api key>
SMTP_FROM_EMAIL=<verified sender email>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20
EMAIL_PROVIDER=brevo_api
EMAIL_FROM_NAME=LandFall AI
BREVO_API_KEY=<Brevo API v3 key>
AUTH_COOKIE_NAME=landfall_session
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=.landfallai.live
LOGIN_ATTEMPT_LIMIT=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15
AUTH_ACTION_ATTEMPT_LIMIT=5
AUTH_ACTION_WINDOW_MINUTES=15
```

Do not manually set `PORT`; Render provides it.

## 10. Final Frontend Build Checklist

The Cloudflare build must resolve these values:

```text
REACT_APP_API_URL=https://api.landfallai.live
REACT_APP_BACKEND_URL=https://api.landfallai.live
REACT_APP_TURNSTILE_SITE_KEY=<cloudflare site key>
```

## 11. Launch Test

After both services deploy:

1. Open the frontend URL.
   - Use `https://landfallai.live`.
2. Register with a real email address.
3. Confirm the Turnstile widget appears.
4. Confirm the verification email arrives.
5. Click the verification link.
6. Confirm you land in the dashboard.
7. Log out.
8. Test password reset.
9. Import a deck and confirm it persists after a backend redeploy.

If login fails after verification, check:

- `CORS_ORIGINS` exactly matches the frontend origin.
- `APP_PUBLIC_URL` exactly matches the frontend origin.
- `REACT_APP_API_URL` exactly matches the backend origin.
- `AUTH_COOKIE_SECURE=true`
- `AUTH_COOKIE_SAMESITE=lax`
- `AUTH_COOKIE_DOMAIN=.landfallai.live`

If email verification links show `Not Found`, confirm Wrangler still sets
`assets.not_found_handling` to `single-page-application`.

The app also sends verification and reset links through the root URL as a fallback:

```text
https://landfallai.live/?verify_email_token=<token>
https://landfallai.live/?reset_password_token=<token>
```

## 12. Reset All Accounts

Use this only when you intentionally want to wipe all current users and their data.

This deletes:

- `users`
- `decks`
- `analysis_runs`
- `auth_tokens`
- `rate_limits`

Preferred method if your Render plan includes shell access:

```bash
RESET_ACCOUNTS_CONFIRM=delete-all-accounts python scripts/reset_accounts.py
```

If your Render plan does not include shell access, use the guarded reset endpoint:

1. Generate a temporary secret locally:

```powershell
[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

2. In the Render backend service env vars, set:

```text
RESET_ACCOUNTS_KEY=<the temporary secret>
```

3. Redeploy the backend.

4. From local PowerShell, call the endpoint:

```powershell
$resetKey="<the temporary secret>"
Invoke-RestMethod `
  -Method Post `
  -Uri "https://api.landfallai.live/api/admin/reset-accounts" `
  -Headers @{ "X-Reset-Key" = $resetKey }
```

5. Confirm the response shows documents deleted.

6. Remove `RESET_ACCOUNTS_KEY` from Render and redeploy the backend. This disables the endpoint again.

From local PowerShell, run this only if your shell has the production `MONGO_URL` and `DB_NAME` set:

```powershell
$env:RESET_ACCOUNTS_CONFIRM="delete-all-accounts"
python backend/scripts/reset_accounts.py
```
