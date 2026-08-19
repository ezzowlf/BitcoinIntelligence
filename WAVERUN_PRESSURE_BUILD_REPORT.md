# WAVERUN Pressure Build Report

Date: 2026-08-20

Mode: research-only
Execution: `DISABLED`

## Data activation

| Metric | Result |
| --- | ---: |
| Requested UTC days | 30 |
| Vantage BTCUSD days | 30 |
| Binance Spot BTCUSDT days | 30 |
| Binance USD-M Futures BTCUSDT days | 30 |
| Complete overlap days | 30 |
| Vantage ticks | 2,974,652 |
| Spot aggregate trades | 17,352,403 |
| Futures aggregate trades | 22,797,685 |

All source partitions cover 2026-07-20 through 2026-08-18. Vantage days
2026-07-25, 2026-08-01, 2026-08-08 and 2026-08-15 are retained but flagged
for six gaps over 60 seconds in total. Binance has no gaps over 60 seconds in
this range. No bad day was silently removed.

The split was declared before multi-day research:

```text
TRAIN          2026-07-20 .. 2026-08-06
VALIDATION     2026-08-07 .. 2026-08-11
WALK_FORWARD   2026-08-12 .. 2026-08-15
FINAL_HOLDOUT  2026-08-16 .. 2026-08-17 (unopened)
EXPLORATORY    2026-08-18 (excluded from OOS claims)
```

Machine-readable daily audits are generated locally at
`data/reports/waverun_30d_data_quality.json`. Raw Parquet is Git-ignored.

## Causal feature foundation

The new observation-only pressure module provides:

- right-labelled completed bars for 1s, 5s, 10s, 30s, 1m, 3m, 5m and 15m;
- MACD line, signal, histogram, slopes, accelerations, distances, cross
  direction and cross age;
- price velocity, acceleration and bounded pressure derivatives;
- Spot/Futures delta, normalized delta, CVD, trade rate and acceleration;
- flow/price efficiency with explicit zero-flow handling and absorption state;
- rolling mean, EMA, VWAP, z-score and displacement;
- a reversion state that cannot become `REVERSION_CONFIRMED` without both
  exhaustion and confirmation;
- transparent source pressures and move-origin classification.

The fixed equal-weight `DirectionalPressureEngine` is a baseline only. It is
not fitted and is not a probability or trading signal.

## Multi-day baseline research

The pre-existing simple Spot/Futures lead-lag and naive mean-reversion studies
were rerun separately on Train, Validation and Walk-forward with fixed horizons
and reaction delays. Best observed cells in each out-of-train split remained
negative after real Vantage Bid/Ask execution:

| Split | Spot best Net EV | Futures best Net EV | Naive MR best Net EV |
| --- | ---: | ---: | ---: |
| Validation | -0.0245% | -0.0231% | -0.0268% |
| Walk-forward | -0.0267% | -0.0265% | -0.0271% |

Because no baseline survived Validation and Walk-forward costs, the final
holdout was not opened and no champion, WATCH, ARMED or SIGNAL rule was
promoted. Advanced model fitting, feature ablation and dashboard signal
integration remain gated behind a credible validation candidate; implemented
feature primitives are not represented as proven predictive value.

## Validation

```text
Focused WAVERUN tests: 20 passed
Full pytest:            385 passed
Ruff changed scope:     PASS
Compile:                PASS
git diff --check:       PASS
Secrets pattern scan:   PASS
Execution:              DISABLED
Edge status:            NO PROVEN EDGE YET
```

A bounded 10-second public-WebSocket smoke test produced a fresh LIVE snapshot:
Binance Spot and Futures both reported `CONNECTED`, with zero reconnects and
zero sequence gaps. The snapshot contained eight observation-only forecasts,
all with `execution: DISABLED`; the current quality gate returned `NO_EDGE`.
The MT5 read-only validation reported Vantage `ONLINE`, BTCUSD visible and
terminal trading disabled. Pressure/MACD dashboard wiring was not claimed as
live because the new research features have not demonstrated OOS value.

No historical L2 was invented. It remains
`HISTORICAL_L2_UNAVAILABLE`; live L2 recordings must retain feature-availability
timestamps and cannot be backfilled into these historical runs.
