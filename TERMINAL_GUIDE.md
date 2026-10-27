# Kronos India terminal

Open http://127.0.0.1:8765 after starting the existing launcher. Refresh an already open page after an update. Connect Dhan privately in the app; never paste a token into chat.

## Faster forecasts

Fast is now the default: 400 completed candles, one sampled path and a six-candle horizon. Balanced preserves the original average of three sampled paths. The model stays loaded in memory. A bounded 16-result cache keys every input candle, instrument metadata, model, horizon and mode; corrected candle values invalidate reuse. Unchanged automatic history refreshes preserve the displayed forecast.

CPU measurements on this PC, same saved Nifty inputs and six-candle horizon:

| Mode | Two warm runs |
| --- | --- |
| Balanced (three paths) | 8.677 s / 8.817 s |
| Fast (one path) | 2.850 s / 2.820 s |
| Matching Fast result reused | 0.001 s model request |

First use also loads Python libraries and model weights (the browser Fast test took 8.702 seconds). UI polling and data retrieval add time. Speed does not establish prediction accuracy: Fast is a single stochastic scenario. This update did not retrain the model. The previous Nifty accuracy assessment still applies.

Market context shows SMA 20, SMA 50 and the simple average true range over 14 completed bars. These are descriptive indicators, not confidence scores.

## Paper trading

Choose an NSE/BSE cash instrument, Paper account and CNC product. Enter quantity in units and a limit price, then review and confirm. The simulation starts with ₹1,000,000. It fills against a recent Dhan quote only if the limit permits it; non-marketable tickets are not retained as pending orders. It rejects trades older than 60 seconds, overspending and sales exceeding virtual holdings. Fees, slippage, order queue, margin and corporate actions are not modeled. Paper cash and holdings belong to this local app and persist across broker connections.

## Real orders

Real tickets support NSE/BSE cash and F&O. Indices cannot be traded directly. Commodity and currency instruments remain chart/forecast-only. Choose Real account, side, product, units and LIMIT price. Review the immutable 60-second preview, check its acknowledgement box, then personally click Confirm REAL action. Each cancellation also requires its own review. Kronos never submits a trade automatically.

Dhan requires a whitelisted static IP for order placement/cancellation. Your broker enforces tick size, freeze limits, available funds/margin, market hours, enabled segments and selling authorization. This terminal does not configure IP whitelisting or bypass broker checks. It does not support order modification, market/stop orders, AMO or bracket orders. Manage unsupported operations in Dhan.

Order books and positions refresh on request. An acknowledged order is not a fill. After an action, verify its broker status. If an outcome is UNKNOWN or SUBMITTING, check Dhan's order book and the preview's correlation reference before doing anything else. The same preview is never automatically resubmitted, including after server restart. A newly created preview is a new order, so do not recreate an uncertain order blindly.

## Local records and privacy

`data/terminal.sqlite3` stores paper fills and the submission journal, including order details and hashed connection identity. It never stores access tokens. The journal panel shows the current connection; database records remain after token rotation. Credentials remain memory-only and clear when the server restarts. Protect this folder as local financial records. Do not run multiple servers against this database.

## Verification and limits

Live placement/cancellation were tested with a mocked broker only. No real orders were placed or cancelled during development. Paper accounting, lot/product validation, expiry, explicit confirmation, account binding, duplicate confirmation, uncertain submission persistence and stale-quote rejection are covered by tests. A real six-candle inference and cached repeat were exercised in the browser.

Official references: [Dhan orders](https://dhanhq.co/docs/v2/orders/), [positions](https://dhanhq.co/docs/v2/portfolio/), [authentication and static IP](https://dhanhq.co/docs/v2/authentication/).

## Chart workspace (26 October 2026)

The app now opens as a chart-centered terminal with a dark workspace, right sidebar and bottom dock. It is a custom Kronos interface inspired by common charting-terminal workflows, not an embedded TradingView product or a complete replacement for all TradingView features.

- Scroll over the chart or use +/− to zoom. Drag to pan; Left/Right keys pan, Home resets, and the expand button gives the chart more space.
- Choose 5m, 15m, 30m or 1h. Higher chart intervals aggregate the loaded five-minute data by session; faded bars are incomplete aggregates. The app does not download one-minute candles.
- Use Indicators for SMA 20, EMA 50, volume and Wilder RSI 14. Indices typically do not report volume.
- Use the left toolbar for horizontal levels and two-click trend lines. Undo removes the last drawing; clear affects only the current instrument/source/timeframe. Drawings persist in browser storage.
- The right tabs switch between Watchlist, Kronos and Order. Manual order confirmation rules are unchanged.
- The bottom tabs show Orders, Positions, Activity, Live tape and Market context.
- Kronos still predicts five-minute candles. Its purple dashed scenario appears on the 5m chart at the latest candles; reset the chart to return there after panning. Higher chart intervals do not retrain or change the model's input interval.
- Dhan quotes remain five-second snapshots. Completed historical candles refresh every minute; the yellow snapshot price line is separate from completed candles. Connect Dhan to use fresh market data.
