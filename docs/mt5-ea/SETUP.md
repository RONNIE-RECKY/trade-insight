# PIP HIVE MT5 EA Bridge — setup

This bridge lets the PIP HIVE bot place signal trades on **any broker's MT5
terminal** — demo or live. It doesn't matter which broker you use; the EA
just acts on whatever account your MT5 terminal is already logged into.

- **Demo connections** auto-execute every qualifying signal with no
  confirmation — same as the simulator, just on real broker infrastructure
  with practice money.
- **Live connections** never auto-execute. Every signal is queued as
  "awaiting confirmation" and the EA will not see it until you confirm it
  yourself — either with the "Confirm & Execute" button on the Auto-Trade
  page, or the link emailed to you when the signal fires. Unconfirmed trades
  expire after 15 minutes and are never sent.

## 1. Get your API key
1. Log in, go to **Auto-Trade**, and select either "MT5 demo (EA bridge)" or
   "MT5 LIVE (confirm each trade)".
2. For live, tick the risk-acknowledgment checkbox — required to connect.
3. Optionally enter your MT5 login number (for your own reference only).
4. Click "Generate API key" and copy the key shown — it's only shown once. If
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
4. Drag the EA onto any chart on the account you connected above. In the
   inputs:
   - `InpApiBaseUrl` — your backend's base URL (no trailing slash).
   - `InpApiKey` — the key from step 1.
   - `InpPollSeconds` — how often it checks for new orders (default 5).
   - `InpSymbolSuffix` — many brokers append a suffix to symbol names (e.g.
     `EURUSDm`, `EURUSD.a`, `EURUSD_`). Check your broker's **Market Watch**
     panel for the exact symbol name and set this to match — if it's wrong,
     orders for that symbol fail with "symbol not found" in the Experts log
     rather than silently trading the wrong instrument.
5. Make sure "Algo Trading" is enabled (top toolbar button) and the EA's
   smiley face in the chart's top-right corner is not crossed out.

## 3. Verify it's working
- Open the **Experts** and **Journal** tabs in MT5's terminal panel.
- Demo: turn the bot on from the Auto-Trade page (Start bot). When it queues
  an order, you should see `PipHiveBridge: order <id> ... filled, ticket ...`
  in the Experts log within one poll interval.
- Live: when a signal fires you'll see it under "Trades awaiting your
  confirmation" on the Auto-Trade page (and get an email). Click Confirm —
  the EA picks it up on its next poll, same log message as above.
- Check the Auto-Trade page's open positions list — the trade appears there
  (tagged `mt5-demo` or `mt5-live`) and closes automatically once price hits
  its stop-loss or take-profit.

## Notes
- If a symbol from a signal isn't available on your broker (wrong suffix or
  unsupported instrument), that order is marked failed and skipped — it does
  not retry forever.
- If the EA reports a failed execution (e.g. a requote), the backend
  re-queues that exact order so the next poll picks it up again.
- Disconnecting on the Auto-Trade page stops new orders from being queued;
  any already-open MT5 positions are unaffected (manage those from MT5
  directly, same as any other trade).
- One EA instance handles one MT5 terminal/account at a time. If you trade
  through multiple brokers, run a separate terminal + EA + API key per
  account.
