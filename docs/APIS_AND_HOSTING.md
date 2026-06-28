# Trade Insight — APIs & Hosting Guide

This document lists the external services the app can use and how to deploy it.

---

## 1. External APIs

| Purpose | Provider (recommended) | Needed? | Free tier? | Env var |
|---|---|---|---|---|
| Market candles (forex/gold/crypto) | **Yahoo Finance** (built-in, keyless) | Works out of the box | Yes (no key) | — |
| Market candles (higher quality) | **Twelve Data** | Optional upgrade | Yes (8 req/min) | `TWELVE_DATA_API_KEY` |
| News / sentiment | **Finnhub** | Optional (falls back to fixtures) | Yes | `FINNHUB_API_KEY` |
| Transactional email (verification) | **Resend** or SMTP (SendGrid, Mailgun, SES) | For real signup emails | Resend: yes | `RESEND_API_KEY` **or** `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` |
| Payments (real billing) | **Stripe** | For real subscriptions | — | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |

### Notes
- **Data**: With no keys, candles come from Yahoo Finance (real prices). Source priority is `Twelve Data → Yahoo → simulated fixtures`. Gold uses the futures front month `GC=F`.
- **Email**: Without an email provider, signup runs in **dev mode** and returns the verification link in the API response (shown on the signup screen). Set `RESEND_API_KEY` or SMTP_* to send real emails — wire the send in `app/auth.py::_send_verification_email`.
- **Payments**: Checkout is currently **simulated** (`/billing/subscribe` just records the plan). To take real money, replace that endpoint with a Stripe Checkout session + webhook that sets `users.plan` on `checkout.session.completed`.

### Backend environment variables
```
TWELVE_DATA_API_KEY=        # optional
FINNHUB_API_KEY=            # optional
RESEND_API_KEY=             # optional (email)
SMTP_HOST= SMTP_USER= SMTP_PASS=   # optional (email, alternative to Resend)
WEB_BASE_URL=https://yourapp.com   # used to build verification links
ADMIN_EMAIL= ADMIN_PASSWORD=       # seeds the one guaranteed admin account on boot
DB_PATH=                           # optional, override the SQLite file location
STRIPE_SECRET_KEY= STRIPE_WEBHOOK_SECRET=  # optional, enables real checkout
OAUTH_BRIDGE_SECRET=<random 32+ char secret>  # required if you enable Google sign-in (see below)
```

### Frontend environment variables
```
NEXT_PUBLIC_API_BASE_URL=https://api.yourapp.com   # the analysis-service URL
NEXTAUTH_SECRET=<random 32+ char secret>
NEXTAUTH_URL=https://yourapp.com
GOOGLE_CLIENT_ID=           # optional — enables "Continue with Google"
GOOGLE_CLIENT_SECRET=       # optional
OAUTH_BRIDGE_SECRET=<same value as the backend's OAUTH_BRIDGE_SECRET>
```

### Trusted auth provider (Google) setup
1. Google Cloud Console → **APIs & Services → Credentials** → Create OAuth client ID (type: Web application).
2. Authorized redirect URI: `https://<your-web-domain>/api/auth/callback/google`.
3. Copy the Client ID/Secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` on the **frontend** service.
4. Generate one random secret and set it as `OAUTH_BRIDGE_SECRET` on **both** the frontend and backend services — it's how the frontend's server-side NextAuth callback proves to the backend that a sign-in was genuinely verified by Google (without it, the bridge endpoint refuses every request).
5. Leave `GOOGLE_CLIENT_ID`/`SECRET` unset and the "Continue with Google" button simply doesn't render — email/password still works standalone.

---

## 2. Architecture

```
apps/web              Next.js frontend (the site users see)
apps/analysis-service FastAPI backend (data, indicators, strategies, signals, auth, billing)
data/                 SQLite DB (dev). Use Postgres in production.
```

The frontend calls the backend over HTTP. They deploy as two services.

---

## 3. Hosting (recommended path)

### Frontend → Vercel
1. Push the repo to GitHub.
2. In Vercel, "Import Project", set **Root Directory** = `apps/web`.
3. Add the frontend env vars above.
4. Deploy. Vercel auto-builds Next.js.

### Backend → Render (or Railway / Fly.io)
1. New **Web Service** from the repo, root `apps/analysis-service`.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add backend env vars.
5. Note the public URL → put it in the frontend's `NEXT_PUBLIC_API_BASE_URL`.

### Database
- Dev uses SQLite (`data/trade_insight.db`). It is fine for a demo but resets on redeploy on most PaaS.
- **Production**: provision Postgres (Render/Railway/Supabase/Neon) and point the app at it. The SQL in `app/db.py` is standard; switch `sqlite3` for `psycopg`/SQLAlchemy and set a `DATABASE_URL`.

### CORS
`app/main.py` currently allows `http://localhost:3000`. Add your deployed frontend origin to the `allow_origins` list before going live.

---

## 4. Going to production — checklist
- [ ] Move from SQLite to Postgres.
- [ ] Set a strong `NEXTAUTH_SECRET`.
- [ ] Configure a real email provider and implement the send in `_send_verification_email`.
- [ ] Replace simulated billing with Stripe Checkout + webhook.
- [ ] Restrict CORS `allow_origins` to your domain.
- [ ] Add a scheduler/worker for the daily signal scan (already runs in-process via APScheduler; for multiple instances move it to a single worker/cron).
- [ ] Add rate limiting and HTTPS (handled by Vercel/Render by default).

---

## 4b. Can I host this on my Hostinger Business plan?

**Short answer: the Business (shared) plan can't run the app as-is.** It is PHP/MySQL shared hosting and cannot run a long-lived Python (FastAPI/uvicorn) process or a Next.js SSR server. Options, best first:

1. **Hostinger VPS** (KVM 1/2) — full Linux box. Works perfectly: run the FastAPI backend with `uvicorn`/`gunicorn` behind Nginx, run the Next.js app with `npm run start` (or PM2), point a domain at it. This is the Hostinger-native path.
2. **Split hosting (free/cheap, recommended)** — frontend on **Vercel**, backend on **Render/Railway**. Then just point your Hostinger **domain** (DNS) at Vercel. You keep the domain on Hostinger, host the apps where they run best.
3. **Business shared plan alone** — only viable if you rewrite the backend in PHP and drop Next SSR for static export. Not recommended; you'd lose the live analysis engine.

**Recommendation:** keep your Hostinger domain, deploy frontend→Vercel and backend→Render (or upgrade to a Hostinger VPS if you want everything under Hostinger).

### Admin account
A default admin is seeded on first boot (override via `ADMIN_EMAIL` / `ADMIN_PASSWORD`):
```
email:    admin@tradeinsight.app
password: Admin1234!
```
Log in with it to reach `/admin`. **Change this password before going live.**

## 6. Step-by-step deployment (recommended: Vercel + Render)

This is the fastest reliable path. ~30–45 minutes.

### A. Put the code on GitHub
1. Create a new GitHub repo (e.g. `trade-insight`).
2. From `D:\trade-insight`: `git init`, `git add .`, `git commit -m "initial"`, then add the remote and `git push`.

### B. Deploy the backend (FastAPI) on Render
1. Go to render.com → **New → Web Service** → connect the GitHub repo.
2. **Root Directory:** `apps/analysis-service`
3. **Runtime:** Python 3
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Environment variables** (Add from section 1):
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (set your own admin login!)
   - `WEB_BASE_URL` = your frontend URL (fill after step C, then redeploy)
   - optional: `TWELVE_DATA_API_KEY`, `FINNHUB_API_KEY`, `RESEND_API_KEY`
7. Deploy. Copy the service URL, e.g. `https://trade-insight-api.onrender.com`.
8. Open `https://<that-url>/symbols` to confirm it returns JSON.

> Note: Render's free tier sleeps after inactivity and uses an ephemeral disk (SQLite resets). For real use, attach a **Postgres** DB (Render offers one) and add a persistent `DATABASE_URL` — see section 4.

### C. Deploy the frontend (Next.js) on Vercel
1. Go to vercel.com → **Add New → Project** → import the same repo.
2. **Root Directory:** `apps/web`
3. **Environment variables:**
   - `NEXT_PUBLIC_API_BASE_URL` = the Render URL from step B
   - `NEXTAUTH_SECRET` = a random 32+ char string (`openssl rand -base64 32`)
   - `NEXTAUTH_URL` = your Vercel URL (e.g. `https://trade-insight.vercel.app`)
4. Deploy. Open the Vercel URL — the landing page should load.

### D. Wire the two together
1. In Render, set `WEB_BASE_URL` to the Vercel URL and **redeploy** the backend.
2. In `apps/analysis-service/app/main.py`, add your Vercel URL to the CORS `allow_origins` list, commit, push (Render auto-redeploys).
3. Done — sign up on the live site, verify with the emailed code (configure `RESEND_API_KEY` to actually send), and log in.

### E. Point your Hostinger domain at it (optional)
- In Vercel → Project → **Settings → Domains**, add your domain.
- In Hostinger hPanel → **DNS Zone**, add the CNAME/A records Vercel shows.
- Update `NEXTAUTH_URL` and `WEB_BASE_URL` to the custom domain and redeploy.

### Alternative: everything on a Hostinger VPS
1. Buy a Hostinger **VPS** (KVM 1+). SSH in.
2. Install Python 3.11+, Node 20+, Nginx.
3. Backend: clone repo, `cd apps/analysis-service`, `pip install -r requirements.txt`, run with `gunicorn -k uvicorn.workers.UvicornWorker app.main:app` under **systemd** or **pm2**.
4. Frontend: `cd apps/web`, `npm install`, `npm run build`, `npm run start` (port 3000) under pm2.
5. Nginx reverse-proxies `yourdomain.com` → Next (3000) and `api.yourdomain.com` → uvicorn (8000). Add SSL with `certbot`.
6. Set the same env vars as above.

## 7. Host everything on Railway (one project)

Railway can run the **entire app** — backend, frontend, and database — in a single
project as three components. ~20–30 minutes.

### 1. Create the project + database
1. railway.app → **New Project → Deploy from GitHub repo** (connect the repo).
2. In the project, **+ New → Database → PostgreSQL**. Railway provisions it and
   exposes `DATABASE_URL` (and private-network vars) to the project.

### 2. Backend service (FastAPI)
1. **+ New → GitHub Repo** → pick the repo → name it `api`.
2. Service **Settings → Root Directory:** `apps/analysis-service`.
   (Railway's Nixpacks auto-detects Python from `requirements.txt`.)
3. **Settings → Deploy → Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Variables:**
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (your admin login)
   - `ALLOWED_ORIGINS` = your frontend URL (fill after step 3, then redeploy)
   - optional: `TWELVE_DATA_API_KEY`, `FINNHUB_API_KEY`, `RESEND_API_KEY`
5. **Settings → Networking → Generate Domain.** Copy the URL (e.g. `https://api-production.up.railway.app`).
6. Open `https://<that-url>/symbols` to confirm JSON.

### 3. Frontend service (Next.js)
1. **+ New → GitHub Repo** → same repo → name it `web`.
2. **Root Directory:** `apps/web` (Nixpacks auto-detects Node/Next; build `npm run build`, start `npm run start`).
3. **Variables:**
   - `NEXT_PUBLIC_API_BASE_URL` = the backend domain from step 2
   - `NEXTAUTH_SECRET` = random 32+ chars
   - `NEXTAUTH_URL` = this service's own Railway domain (generate it first)
4. **Generate Domain**, then set `NEXTAUTH_URL` to it.
5. Back in the **api** service, set `ALLOWED_ORIGINS` to the web domain and redeploy.

### Persistence — two choices
- **Postgres (recommended):** the project already has it. Migrate `app/db.py` from
  `sqlite3` to `psycopg`/SQLAlchemy and read `DATABASE_URL`. This survives every deploy.
- **Quick path (SQLite on a volume):** the app uses SQLite at `data/trade_insight.db`.
  On the **api** service add **Settings → Volumes → mount** at `/app/data` so the DB file
  persists across deploys. Good enough for a small single-instance app; don't scale the
  api service past 1 replica (the in-process daily scan + SQLite assume one instance).

### Notes
- CORS is now env-driven (`ALLOWED_ORIGINS`) — no code edit needed, just set the var.
- Custom domain: add it on the **web** service (Settings → Networking → Custom Domain),
  point your registrar's DNS at the value Railway shows, then update `NEXTAUTH_URL` +
  `ALLOWED_ORIGINS` to the custom domain.
- Keep the api service at **1 replica** so the APScheduler daily signal scan doesn't run twice.

## 8. Account security (what's already implemented)
- **Password hashing**: scrypt (memory-hard, stdlib). Any account created before this upgrade is verified against the legacy PBKDF2 hash and silently re-hashed to scrypt on its next successful login.
- **Input validation**: every signup/login field (email, password, full name, phone, verification code) is normalized and re-validated server-side — never trusts client-side checks alone.
- **Rate limiting**: in-memory sliding-window limits per client IP on `/auth/signup` (5/hour), `/auth/login` (10/15min), `/auth/verify-code` (10/15min), `/auth/resend-code` (3/10min), returning `429` with `Retry-After`. This state is per-process — keep the backend at 1 replica, or move it to Redis if you ever scale out.
- **Account lockout**: 5 failed password attempts locks the account for 15 minutes (`423 Locked`), independent of the IP-based rate limit.
- **Generic error messages**: login always returns "Incorrect email or password." for both a wrong password and a nonexistent email (plus a dummy-hash comparison on the not-found path) to reduce account enumeration via timing.
- **Trusted OAuth provider**: Google sign-in bridges through a backend endpoint gated by a shared secret (`OAUTH_BRIDGE_SECRET`) — it can't be hit directly to mint accounts.

## 5. Honesty / compliance note
This product presents **informational technical analysis**, not financial advice. Win-rates shown are real backtested results of each rule — never marketing figures. Keep the disclaimer banner and the "not financial advice" language in place; depending on your jurisdiction, distributing trading signals may require regulatory registration (e.g. FCA in the UK). Get legal advice before charging real customers.
