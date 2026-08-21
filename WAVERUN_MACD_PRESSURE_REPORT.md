# WAVERUN Simple MACD Pressure Backtest

## Final decision

**SIMPLE MACD EDGE: NOT FOUND**

The deterministic hypothesis was tested without ranking or ML:

`MACD cross + histogram sign + histogram slope + histogram acceleration + extreme histogram/acceleration + optional causal price confirmation`

Timeframes: 30s, 60s, 3m, 5m. Extremes: top 20%, 10%, 5%, 2%, 1%, with thresholds frozen from Q1/2025. Targets: `$100/$150/$200/$300/$400/$500`. Windows: 5m/10m/15m/30m/60m. LONG and SHORT were separate. Fixed cost proxy: `$17`; historical Vantage Bid/Ask was unavailable and was not imputed.

## Actual coverage

- Historical rows: 3,663,360
- Result rows: 10,260
- Q1/2025: the 30s SHORT, top-20% setup reached `$100` in 91.89% of N=37 at 60m, but only 0.41 signals/day and median MAE was -$684.51.
- Apr-Jun/2025: the same extreme setup had at most 14 LONG or 8 SHORT independent candidates across 91 days; no meaningful N threshold was reached.
- Jul/2026: the tested extreme setups had at most 1–2 independent candidates across 31 days; no meaningful OOS estimate exists.

The apparent Q1 70%+ result therefore fails the predefined requirements: later-period replication, meaningful N and useful frequency. It must not be frozen.

## Filters

MACD-only was compared with MACD plus causal price response. One-at-a-time Spot/Futures agreement, expansion and flow-efficiency filters were also evaluated. No filter produced a replicated later-period improvement. Historical L2 confirmation is `NOT ESTIMABLE` because L2 history is absent from this tier.

## Outcomes and limitations

The result matrix stores target reach, net-positive rate, MFE, MAE and signals/day. The current historical feature tier does not contain a persisted future Vantage tick path or per-tick execution path, so Vantage-specific time-to-target/time-to-profit cannot be claimed. The live Vantage path remains separate. No locked 2026-08-16/17 data was accessed. Execution remains `DISABLED`.

Conclusion: the manual visual MACD observation may describe a rare Q1 subgroup, but it does not survive later-period coverage. No simple MACD strategy is selected.
