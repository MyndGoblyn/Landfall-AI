# Render Deployment Guide

This project is a two-service Render deployment: a Python FastAPI backend and a React static frontend.

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
CORS_ORIGINS=https://<your-frontend-service>.onrender.com
APP_PUBLIC_URL=https://<your-frontend-service>.onrender.com
USE_IN_MEMORY_DB=false
REQUIRE_EMAIL_VERIFICATION=true
AUTH_COOKIE_NAME=landfall_session
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
CAPTCHA_REQUIRED=true
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>
SMTP_HOST=<smtp host>
SMTP_PORT=587
SMTP_USERNAME=<smtp username>
SMTP_PASSWORD=<smtp password>
SMTP_FROM_EMAIL=<from address>
SMTP_USE_TLS=true
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
REACT_APP_API_URL=https://<your-backend-service>.onrender.com
REACT_APP_BACKEND_URL=https://<your-backend-service>.onrender.com
REACT_APP_TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
```

Because the app uses React Router, add a static site rewrite in Render:

```text
Source Path: /*
Destination Path: /index.html
Action: Rewrite
```

After Render gives you the final frontend URL, update the backend `CORS_ORIGINS` value to that exact HTTPS origin and redeploy the backend.

## Prelaunch Checklist

- Use a strong generated `JWT_SECRET`; never reuse the example value.
- Confirm registration creates only `player` users.
- Confirm registration and login require a Turnstile challenge in production.
- Confirm verification and password reset emails are delivered.
- Confirm login throttling returns HTTP 429 after repeated failed attempts.
- Confirm the frontend can call `/api/auth/me` after login.
- Confirm imported decks and analyses persist after backend redeploys.
- Keep MongoDB network access restricted to the minimum Render needs.
