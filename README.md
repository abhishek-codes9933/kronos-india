# Kronos India

A local Windows market terminal with Kronos AI, paper simulation and confirmed manual Dhan orders. See [Terminal guide](TERMINAL_GUIDE.md) for the trading workflow, limitations and measured speed.

## Open the app

Double-click **Start Kronos India.cmd** in this folder. It opens http://127.0.0.1:8765 in your browser. Keep its window open while using the app. If the app is already running, the launcher opens it instead of starting a second copy.

This installation uses your existing Python environment at `C:\Users\abhis\Documents\Kronos\.venv\Scripts\python.exe`. It is a local browser app, not a standalone packaged EXE. Keep this folder in its current location: pretrained model cache and the Nifty-trained checkpoint are stored alongside this chat's other outputs.

## Get live market data

1. Click **Connect Dhan**.
2. Enter your Dhan client ID and access token privately in the dialog.
3. Click **Connect securely**. An active Dhan Data API plan is required.
4. Search for an instrument and select it. Use the exchange filter to distinguish NSE, BSE, currency, and MCX listings.
5. Add instruments to your watchlist if desired.

Quotes are requested every five seconds. Completed five-minute candles refresh every minute. This is snapshot polling, not a tick-by-tick WebSocket feed. The quote receipt time is not the exchange's trade timestamp. Outside trading hours the provider may return the last available price. The chart identifies older candles.

The catalogue supports Dhan's documented IDX_I, NSE_EQ, BSE_EQ, NSE_FNO, BSE_FNO, MCX_COMM, NSE_CURRENCY and BSE_CURRENCY segments. Expired contracts are excluded. Availability depends on Dhan's catalogue, your account and history coverage; a segment can have no active contracts. This is not a claim to cover every security on every Indian exchange. Use the refresh arrow beside Market explorer to update the public catalogue.

## Use Kronos AI

1. Select an instrument with at least 400 completed five-minute candles.
2. Keep **Kronos-small · Original** selected, or choose the experimental Nifty model for Nifty 50 only.
3. Choose 6, 12 or 24 forecast candles.
4. Click **Generate forecast**. Kronos runs locally: Fast generates one path; Balanced averages three paths. Fast with six candles is the default.
5. The orange chart line is the model scenario. Export it with **Download forecast CSV**.

Historical preview works without Dhan using your saved Nifty CSV. Its forecasts are explicitly historical scenarios. Connecting to Dhan changes the source to provider data. Manual order placement and cancellation are available through explicit review and confirmation in the trading terminal; forecasts never trigger orders.

## Model limitations

The original model has not been validated for every listed instrument. Options and futures have expiry and structural differences; forecasts for them are experimental. Projection slots follow approximate regular weekday sessions. Exchange holidays, special sessions and seasonal MCX closing-time changes are not modeled. Horizons that exceed a derivative contract's expiry are rejected.

Nifty fine-tuning did not beat the original model in the small held-out test: 38.4 vs 37.8 points mean absolute error; an unchanged-price baseline achieved 27.5 points. Twelve test windows are not evidence of profitability. The app does not present a model forecast as a trade recommendation or confidence probability.

## Privacy and lifecycle

Credentials are held only in server memory. They are sent to Dhan over HTTPS, never written to disk or browser storage, and cleared by Disconnect or server shutdown. Watchlist instrument identifiers are stored in browser local storage. Paper fills and order submission records persist locally in data/terminal.sqlite3; no access tokens are stored there. The server listens only on 127.0.0.1; do not expose it to the internet. Browser requests are checked for expected host/origin and mutations require a per-run token.

Refreshing this browser page does not stop the server. Closing a normally launched command window stops that instance. A server started by Codex may run in the background; ask Codex to stop the local app when needed.

## Verification

- Automated tests cover segment mapping, index placeholder expiries, unknown instruments, incomplete candle filtering, weekday projection, invalid OHLC rejection, token errors, quote mapping, host/origin checks and mutation protection.
- Actual local Kronos inference tested with the cached model and saved Nifty history.
- Actual Dhan quote and candle requests verified through the user's connection for Nifty, Bank Nifty and Sensex. Other individual instruments have not all been tested.
- Test command: `C:\Users\abhis\Documents\Kronos\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"`

## Files and dependencies

`server.py` handles the local application and Dhan data; `engine.py` runs Kronos; `core.py` contains candle/session rules; `catalogue.py` refreshes the public instrument list. Static interface files are in `static/`. Public instrument data is in `data/`. Forecast and candle CSVs are downloaded through your browser.

Uses Python standard library plus requests, numpy, pandas, torch and the existing Kronos project dependencies. No additional framework install is needed.

Official integration references: https://dhanhq.co/docs/v2/instruments/ , https://dhanhq.co/docs/v2/market-quote/ , https://dhanhq.co/docs/v2/historical-data/ . Kronos source: https://github.com/shiyu-coder/Kronos .

Live price chart: collects Dhan quote snapshots every five seconds while the page is connected. Choose 5 minutes, 15 minutes, or 1 hour; Pause freezes the display while collection continues. Receipt timestamps are not exchange trade times. Gaps over 15 seconds break the line, and delayed receipts are labelled. Data stays in browser memory and clears on reload/disconnect. Completed candles remain the input to Kronos forecasts.

