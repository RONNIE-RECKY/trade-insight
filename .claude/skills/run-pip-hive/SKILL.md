---
name: run-pip-hive
description: Launch and drive the PIP HIVE app (FastAPI analysis-service on :8000 + Next.js web on :3000) locally or in a cloud container — install, start both services, curl-smoke the API, log in as the seeded admin and screenshot Charts/Signals with Playwright.
---

# Run PIP HIVE

Two services, both needed:

| Service | Dir | Port |
|---|---|---|
| Analysis API (FastAPI) | `apps/analysis-service` | 8000 |
| Web (Next.js 16) | `apps/web` | 3000 — talks to `NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000` |

Verified on Python 3.13 / Node 22. No `.env` is required; every key in
`apps/analysis-service/.env.example` is optional.

## 1. Install (from repo root)

Run these two in parallel — pip takes a few minutes (pandas, pandas-ta, numpy):

```bash
(cd apps/analysis-service && python3 -m venv venv && venv/bin/pip install -q -r requirements.txt)
(cd apps/web && npm ci)
```

`venv/` and `node_modules/` are gitignored.

## 2. Start both services in the background

```bash
LOGS=${LOGS:-/tmp}   # in a cloud session use the scratchpad dir
(cd apps/analysis-service && nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > $LOGS/api.log 2>&1 &)
(cd apps/web && NEXTAUTH_SECRET=dev-local-secret NEXTAUTH_URL=http://localhost:3000 nohup npm run dev > $LOGS/web.log 2>&1 &)
timeout 90 bash -c 'until curl -s -o /dev/null localhost:8000/docs && curl -s -o /dev/null localhost:3000; do sleep 2; done'
```

- `NEXTAUTH_SECRET` is passed on the command line only; don't write it to a file.
- Google sign-in stays off unless `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are set — expected.
- The API creates/uses SQLite at `data/trade_insight.db` (repo root, gitignored).
  Override with `DB_PATH`. The admin account is seeded on startup.

## 3. Smoke the API

```bash
for p in /symbols "/candles/XAUUSD?interval=1h" /signals/today /news-intel/xauusd /analyze/XAUUSD; do
  echo "== $p"; curl -s -w "\n[%{http_code}]\n" "localhost:8000$p" | head -c 400; echo
done
```

Expected: first four return 200. `/analyze/XAUUSD` returns
**403 "the 1h timeframe requires a higher plan"** unauthenticated — that's
plan gating, not a bug.

## 4. Drive the web UI

Uses the globally installed `playwright` (cloud containers ship Chromium at
`/opt/pw-browsers`; never run `playwright install`):

```bash
OUT=${OUT:-/tmp}
NODE_PATH_PW=$(npm root -g) node .claude/skills/run-pip-hive/drive.mjs $OUT
```

It screenshots `home.png`, logs in as the seeded admin
(`admin@tradeinsight.app` / `Admin1234!`, or `ADMIN_EMAIL`/`ADMIN_PASSWORD`),
expects to land on `/account`, then screenshots `charts.png` and `signals.png`
and exits non-zero on any page error. **Look at the screenshots** — Charts
should show a candlestick chart with Entry/SL/TP lines and the nav should show
`PLATINUM admin@tradeinsight.app`.

## Gotchas

- **Simulated data in sandboxes.** If the network policy blocks
  `query1.finance.yahoo.com` (api.log shows `Yahoo fetch failed ... 403`),
  the API falls back to generated prices: `/symbols` reports
  `"data_source":"simulated"` and news shows "demo data". The app still works.
  Note the Charts page still shows a green "Live" badge in this mode.
- Set `TWELVE_DATA_API_KEY` / `FINNHUB_API_KEY` in `apps/analysis-service/.env`
  for real prices/news (see `.env.example`).
- `apps/web/AGENTS.md`: this Next.js version has breaking changes — read
  `node_modules/next/dist/docs/` before editing web code.

## Stop

```bash
pkill -f "[u]vicorn app.main:app"; pkill -f "[n]ext dev"
```

The `[x]` bracket keeps `pkill -f` from matching (and killing) the shell
running the command itself.
