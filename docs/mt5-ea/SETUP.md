# PIP HIVE MT5 EA Bridge — setup (DEMO accounts only)

This bridge lets the PIP HIVE bot auto-execute signal trades on your **MT5 demo
account**. There is no live/real-money mode — the backend only ever queues
orders for a connection made through the "MT5 demo (EA bridge)" option on the
Auto-Trade page, and that connection is always demo.

## 1. Get your API key
1. Log in, go to **Auto-Trade**, select "MT5 demo (EA bridge)".
2. Optionally enter your MT5 demo login number (for your own reference only).
3. Click "Generate API key" and copy the key shown — it's only shown once. If
   you lose it, disconnect and reconnect to get a new one.

## 2. Install the EA
1. Open MetaEditor (F4 inside MT5), create a new Expert Advisor, and paste in
   the contents of `PipHiveBridge.mq5` (this folder).
2. Compile it (F7). Fix any compile errors before continuing — this file has
   not been compiled by an automated agent (no MT5 terminal is available in
   that environment), so treat the first compile as the first real test.
3. In MT5, open **Tools > Options > Expert Advisors** and check "Allow
   WebRequest for listed URL", then add your backend's URL (e.g.
   `https://your-backend.up.railway.app`) to the list. Without this step every
   request fails with error 4060.
4. Drag the EA onto any chart on your **demo account**. In the inputs:
   - `InpApiBaseUrl` — your backend's base URL (no trailing slash).
   - `InpApiKey` — the key from step 1.
   - `InpPollSeconds` — how often it checks for new orders (default 5).
   - `InpSymbolSuffix` — only needed if your broker appends a suffix to
     symbol names (e.g. `EURUSDm`, `EURUSD.a`). Leave blank otherwise.
5. Make sure "Algo Trading" is enabled (top toolbar button) and the EA's
   smiley face in the chart's top-right corner is not crossed out.

## 3. Verify it's working
- Open the **Experts** and **Journal** tabs in MT5's terminal panel.
- Turn the bot on from the Auto-Trade page (Start bot). When it queues an
  MT5 order, you should see `PipHiveBridge: order <id> ... filled, ticket ...`
  in the Experts log within one poll interval.
- Check the Auto-Trade page's open positions list — the trade also appears
  there (tagged `mt5-demo`), and closes automatically once price hits its
  stop-loss or take-profit (same engine that tracks simulated/OANDA-demo
  trades).

## Notes
- If a symbol from a signal isn't available on your broker, that order is
  marked failed and skipped — it does not retry forever.
- If the EA reports a failed execution (e.g. a requote), the backend
  re-queues that exact order so the next poll picks it up again.
- Disconnecting on the Auto-Trade page stops new orders from being queued;
  any already-open MT5 positions are unaffected (manage those from MT5
  directly, same as any other trade).
