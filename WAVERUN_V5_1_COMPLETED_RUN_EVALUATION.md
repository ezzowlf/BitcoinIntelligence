# WAVERUN V5.1 completed six-hour run evaluation

## Executive result

The run is real and complete, but it is not an outcome-labeled research sample. The recorder stored decision-time MT5/Vantage quotes, not the future Vantage Bid/Ask path required to resolve targets and adverse barriers. Therefore no target-first precision, calibration, gate-value, product-frontier, or Net-EV claim is valid.

## Session integrity

| Item | Measured result |
|---|---|
| Start | 2026-08-21 09:54:35.107875 UTC |
| Last raw event | 2026-08-21 15:54:33.934199 UTC |
| Last candidate | 2026-08-21 15:54:33.049622 UTC |
| Usable duration | approximately 5:59:59 |
| Raw events | 12,053,112 |
| Binance Spot events | 9,285,106 |
| Binance Futures events | 2,768,006 |
| Pre-gate candidates | 21,468 |
| Decision records | 21,468 |
| Run data size | 4,664,742,242 bytes |
| stderr | empty |
| End-of-run file writes | raw event file updated 2026-08-21 15:54:33.934 UTC; candidate file updated 15:54:33.206 UTC |

Source/event details:

- Spot: 6,403,796 `BOOK_TICKER`, 2,215,310 `TRADE`, and 215,981 `DEPTH` events.
- Futures: 2,768,006 `TRADE` events. The normalized futures stream recorded these as trade events; no separate OI/liquidation event family was available in the persisted candidate inputs.
- Futures receive gaps over one second: 38.
- Spot sequence-gap health: 1.
- Last persisted feed health: Spot `CONNECTED`, Futures `CONNECTED`.
- L2 availability at candidate time: 21,468 / 21,468.
- MT5 quote availability at candidate time: 21,468 / 21,468.
- Continuous MT5 uptime: not independently measurable because MT5 ticks were not persisted as a time series.

## Candidate and gate results

| Result | Count |
|---|---:|
| BLOCKED | 21,468 |
| WATCH | 0 |
| ARMED | 0 |
| APPROVED | 0 |
| LONG bias | 9,917 |
| SHORT bias | 11,547 |
| NONE | 4 |

Observed invalidation-reason counts:

- `insufficient calibrated edge after costs`: 19,076
- cross-group directional conflict: 2,244
- same-group FLOW conflict: 148

The current Decision Layer does not persist independent boolean results for every gate; its invalidation reason is therefore not sufficient to claim that one gate alone caused each block. No blocked candidate can be classified as a correct block or missed winner without a future Vantage path.

## Feature evidence

The run stored candidate-time MomentumPressureState, flow, CVD velocity, L2 imbalance, microstructure availability, and MT5 quote context. `price_response_efficiency` was unavailable for all candidates because no causal price-response implementation was populated in the live candidate record. OI and liquidation evidence were unavailable in the live adapter. MACD anomaly was not part of this run.

Measured candidate-time examples are descriptive only, not predictive:

- finite flow-pressure observations: 21,466; mean 4.4870, median 10.8228.
- finite 60-second returns: 21,407; mean -0.00002562, median -0.00000937.
- L2 and MT5 were available for every candidate.

No True Pressure versus Absorbed Pressure comparison is possible without outcome labels. Consequently the run does not answer whether L2, Microprice, depletion, replenishment, Spot/Futures lead-lag, flow acceleration, or MACD predicts continuation.

## Target/barrier/horizon evaluation

The requested grid was recorded as candidate metadata:

- targets: $100, $150, $200, $300, $400, $500
- adverse barriers: $25, $50, $75, $100, $150
- horizons: 60s, 90s, 120s, 180s, 300s, 600s

But no target/adverse result was resolved. For every cell, target-first, adverse-first, MFE, MAE, time-to-target, time-to-adverse, remaining move, precision, N, and Vantage-aware cost EV are `NOT ESTIMABLE`.

Historical Binance AggTrade data was not mixed into this calibration because it lacks the live session's L2 and Vantage execution fields. Doing so would silently change feature availability and violate comparability.

## Calibration and product frontier

- Chronological calibration: not run; no valid labels.
- Brier: not estimable.
- Log loss: not estimable.
- ECE: not estimable.
- 3/5/7/10 signals per day frontiers: not estimable.
- 70/75/80/85/90% frequency frontiers: not estimable.
- >=70% at >=3/day: not demonstrated.
- robust 80% class: not demonstrated.
- 90% class: insufficient evidence.

No pressure score was converted into a probability.

## Replay and latency

Replay of all 21,468 persisted causal inputs reproduced the recorded business state with 0 mismatches.

- P50 persistence latency: 140.09 ms
- P95: 158.23 ms
- P99: 175.37 ms
- Max: 245.32 ms

These are receive-to-persistence measurements. Dashboard-update and audio latencies were not separately persisted.

## Dashboard and safety

The existing dashboard loaded in LIVE mode with no browser console errors. The new V5.1 pressure/decision fields were not exposed in the existing panel, so dashboard acceptance is partial. `execution: DISABLED` remains intact. The 2026-08-16 and 2026-08-17 holdout remains untouched.

## Final conclusion

The run proves a stable real-data recorder with 12.05 million market events, synchronized L2 at candidate time, decision-time MT5 quotes, 21,468 fail-closed decisions, and deterministic replay. It does not prove a tradeable edge. The single required next data correction is continuous Vantage Bid/Ask recording through every candidate horizon; only then can the requested outcome, calibration, gate, and product-frontier questions be answered.
