# WAVERUN Decision Layer live integration

LIVE DECISION LAYER INTEGRATED: YES (canonical Binance runner)

- Canonical branch: `codex/waverun-microstructure`
- Real live runner: `scripts/waverun_live.py`
- Decision persistence: `runtime/waverun/decision_records.jsonl`
- Execution: `DISABLED`
- Focused tests: 11 passed
- Full pytest: 431 passed, 1 environment cache warning

Real MT5 read-only smoke:

- status: ONLINE
- provider: MetaTrader 5
- symbol: BTCUSD
- terminal version: 500.6090
- connected/logged in: true/true
- Bid: 77879.98
- Ask: 77896.96
- Spread: 16.98

The 60-second live Binance session produced 1,897 decision evaluations. Binance Spot and Futures were CONNECTED with zero reconnects and zero sequence gaps in the final live snapshot. The integrated decision gate produced 1,897 `BLOCKED / NO_TRADE` results. This is expected because the live adapter has no calibrated V5 probability, no valid timing signal, and only partial evidence groups.

The runner now persists causal input provenance including bid/ask/spread, signal groups, data quality, freshness, timing, regime, calibration status, and cost-edge status. No MT5 order operation exists in this path.
