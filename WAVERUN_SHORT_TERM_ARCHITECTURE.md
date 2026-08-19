# WAVERUN BTC Short-Term Foundation

This checkout now contains an observation-only short-term foundation at
`src/bitcoin_cycle_analyzer/short_term`. It is an extension of Bitcoin
Intelligence, not a replacement for the existing structural analysis.

The current pipeline is:

```text
MarketTick -> FeatureEngine -> transparent baseline predictors
           -> multi-horizon fusion -> cost/data quality gate
           -> 5m-focused state machine -> Forecast / SQLite store
```

Supported horizons are 30s, 1m, 3m, 5m, 10m, 15m, 30m and 60m. Every tick
records exchange, received and processed timing and can be replayed through
the same pipeline. Missing order-book data is explicitly unavailable. Stale
data and insufficient cost-adjusted edge produce `NO_EDGE`; no BUY/SELL
claim is forced. All outputs carry `execution: DISABLED`.

Live integration is provided by `short_term/binance.py` and
`scripts/waverun_live.py`. Binance Spot trade, book-ticker and depth events,
plus public Futures mark-price/liquidation streams, are normalized before they
reach the feature engine. Feed health and orderbook sequence gaps fail closed.
`START_WAVERUN.ps1` starts the observation-only engine and existing Streamlit
dashboard from the project venv; `STOP_WAVERUN.ps1` stops those local processes.
The existing Streamlit application reads the DTO snapshot from
`runtime/waverun/latest.json`; it does not import internal predictor objects.

For a fresh checkout, install `.[dev,dashboard,live]`, run
`scripts/update_data.py`, and run `scripts/seed_golden_events.py`. The ignored
`database/*.db` files are generated local baselines, not committed production
artifacts. Replay uses the same normalized event and core engine pipeline.

The baseline predictors are research scaffolding only. They are not calibrated
models and do not establish a trading edge. Real feed adapters, point-in-time
training data, walk-forward evaluation, calibration, and dashboard wiring must
be added and validated before any forecast is presented as production-quality.
