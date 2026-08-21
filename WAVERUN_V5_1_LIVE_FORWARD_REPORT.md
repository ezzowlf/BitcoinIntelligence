# WAVERUN V5.1 live forward report

REAL LIVE SESSION: 6h 00m usable recording

- Raw market events: 12,053,112
- Pre-gate candidates: 21,468
- Decision records: 21,468
- BLOCKED: 21,468
- WATCH: 0
- ARMED: 0
- APPROVED: 0
- L2 available at candidate time: 21,468 / 21,468
- MT5 quote available at candidate time: 21,468 / 21,468
- Binance Spot/Futures last health: CONNECTED / CONNECTED
- stderr: empty
- Execution: DISABLED
- Decision persistence latency: P50 140.09 ms, P95 158.23 ms, P99 175.37 ms, max 245.32 ms

## Gate interpretation

All candidates were blocked by the existing strict gates. The run did not lower thresholds or manufacture approvals.

## Outcome limitation

Each candidate contains the MT5/Vantage Bid/Ask observed at decision time, but the recorder did not persist a continuous future Vantage Bid/Ask path. Therefore target-first, adverse-first, MFE, MAE, time-to-target, time-to-adverse, remaining move, and Vantage-aware Net EV are not computable from this session. Binance events are not substituted for Vantage execution outcomes.
