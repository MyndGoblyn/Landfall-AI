# Render Deployment Guide

This project is a two-service Render deployment: a Python FastAPI backend and a React static frontend.

Primary production URL:

```text
https://landfallai.live
```

Recommended backend API URL:

```text
https://api.landfallai.live
```

## Backend Web Service

- Root directory: `backend`
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python start.py`
- Health check path: `/api/`

Set these backend environment variables in Render:

```text
ENVIRONMENT=production
PORT=<Render provides this automatically>
MONGO_URL=<your MongoDB connection string>
DB_NAME=landfall_ai
JWT_SECRET=<32+ character random secret>
CORS_ORIGINS=https://landfallai.live,https://www.landfallai.live
APP_PUBLIC_URL=https://landfallai.live
USE_IN_MEMORY_DB=false
REQUIRE_EMAIL_VERIFICATION=true
AUTH_COOKIE_NAME=landfall_session
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_DOMAIN=.landfallai.live
CAPTCHA_REQUIRED=true
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>
SMTP_HOST=<smtp host>
SMTP_PORT=587
SMTP_USERNAME=<smtp username>
SMTP_PASSWORD=<smtp password>
SMTP_FROM_EMAIL=<from address>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20
LOGIN_ATTEMPT_LIMIT=5
LOGIN_ATTEMPT_WINDOW_MINUTES=15
AUTH_ACTION_ATTEMPT_LIMIT=5
AUTH_ACTION_WINDOW_MINUTES=15
```

Use a managed MongoDB provider such as MongoDB Atlas. Do not use the in-memory database for production.

## Frontend Static Site

- Root directory: `frontend`
- Build command: `npm install && npm run build`
- Publish directory: `build`

Set this frontend environment variable in Render:

```text
REACT_APP_API_URL=https://api.landfallai.live
REACT_APP_BACKEND_URL=https://api.landfallai.live
REACT_APP_TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
```

Because the app uses React Router, add a static site rewrite in Render:

```text
Source Path: /*
Destination Path: /index.html
Action: Rewrite
```

Add custom domains in Render:

```text
Frontend static site: landfallai.live
Backend web service: api.landfallai.live
```

When you add the root domain `landfallai.live`, Render automatically adds the matching `www.landfallai.live` domain and redirects it to the root domain.

After Render verifies the custom domains, keep `landfallai.live` as the primary URL and redeploy both services.

## Prelaunch Checklist

- Use a strong generated `JWT_SECRET`; never reuse the example value.
- Confirm registration creates only `player` users.
- Confirm registration and login require a Turnstile challenge in production.
- Confirm verification and password reset emails are delivered.
- Confirm login throttling returns HTTP 429 after repeated failed attempts.
- Confirm the frontend can call `/api/auth/me` after login.
- Confirm imported decks and analyses persist after backend redeploys.
- Keep MongoDB network access restricted to the minimum Render needs.
