# WAVERUN Data Activation Report

Date: 2026-08-19/20 UTC

Mode: research-only
Execution: `DISABLED`

## Baseline

The existing ignored local SQLite research databases from the original
checkout were used only for local regression verification; none are tracked or
copied into Git. With those generated databases present, the complete suite
passed: **377 passed**.

The repository already documents the reproducible public baseline commands:
`scripts/update_data.py` and `scripts/seed_golden_events.py`. A fresh checkout
must run those commands before the historical tests can use generated local
SQLite data.

## Binance Vision download

The official daily aggregate-trade archives were downloaded into the ignored
local Parquet lake using `scripts/download_binance_history.py`:

| Source | Day | Events | Start UTC | End UTC | Timestamp | Audit |
| --- | --- | ---: | --- | --- | --- | --- |
| Binance Spot BTCUSDT | 2026-08-18 | 403,321 | 00:00:00.452184 | 23:59:59.057863 | microseconds | 0 duplicates, 0 backwards, 0 gaps >60s, 0 invalid prices/quantities |
| Binance USD-M Futures BTCUSDT | 2026-08-18 | 545,233 | 00:00:00.015 | 23:59:59.014 | milliseconds | 0 duplicates, 0 backwards, 0 gaps >60s, 0 invalid prices/quantities |

The raw partitions are local only:

```text
runtime/waverun_data/raw/binance_spot/BTCUSDT/2026/08/2026-08-18.parquet
runtime/waverun_data/raw/binance_futures/BTCUSDT/2026/08/2026-08-18.parquet
```

The downloader is idempotent by trade identifier and writes no orderbook data.
Historical L2 is therefore explicitly `HISTORICAL_L2_UNAVAILABLE`; no
orderbook features were generated from these files.

Official source: `https://data.binance.vision/`. Binance's public-data schema
documents aggregate-trade archives and notes that Spot timestamps from 2025
onwards are microseconds; USD-M Futures data for this sample is milliseconds.

## Vantage MT5

The active read-only MT5/Vantage session was confirmed with:

```text
status: ONLINE
server: VantageMarkets-Live 14
symbol: BTCUSD
terminal version: 500.6090
logged in: true
server UTC offset: +3h
```

The exact UTC day was loaded through `copy_ticks_range`:

```text
ticks: 80,709
earliest: 2026-08-18T00:00:02.791Z
latest:   2026-08-18T23:59:57.024Z
bid/ask: available
duplicates: 0
backwards timestamps: 0
zero quotes: 0
crossed quotes: 0
gaps >60s: 0
spread median/p75/p90/p95/p99/max: 17.03 / 17.08 / 17.10 / 17.11 / 17.12 / 17.12
```

## Binance/Vantage overlap

The three sources overlap from approximately `2026-08-18T00:00:02.791Z` to
`2026-08-18T23:59:57.024Z` (about 23h 59m 54s). Vantage is used as the
execution truth: long entries use Ask and exits Bid; short entries use Bid and
exits Ask.

## First seconds research

The event-based runner uses fixed horizons `10s, 20s, 30s, 45s, 60s, 90s,
120s, 180s, 300s`, reaction delays `0s, 1s, 2s, 3s, 5s, 10s`, and no model
training. The 2026-08-18 results are exploratory and one-day only:

| Study | Best observed configuration | Samples | Gross directional consistency | Net EV after Vantage Bid/Ask |
| --- | --- | ---: | ---: | ---: |
| Binance Spot event lead | 60s / 5s reaction | 199 | 53.3% | -0.0249% |
| Binance USD-M event lead | 120s / 3s reaction | 283 | 52.3% | -0.0228% |
| Vantage mean reversion | 10s / 10s reaction | 51,305 | not applicable | -0.0270% |

Mean reversion's worst tested cell was 120s / 0s at `-0.0293%` net EV.
The machine-readable full matrix is written to
`data/reports/waverun_seconds_research.json` locally. No champion or live
signal was promoted.

## Research status

The activated data is now suitable for trade-arrival, aggressor-flow, CVD,
Bid/Ask cost and event-based cross-source research. Historical orderbook and
liquidation features remain unavailable because the free archives used here do
not contain them.

Edge status: **NO PROVEN EDGE YET**.

## 30-day extension (2026-08-20)

The same read-only adapters were subsequently used for 2026-07-20 through
2026-08-18: 30 requested days, 30 Vantage days, 30 Spot days, 30 Futures days
and 30 complete-overlap days. Totals are 2,974,652 Vantage ticks, 17,352,403
Spot aggregate trades and 22,797,685 Futures aggregate trades. Four retained
Vantage weekend days are flagged for six gaps over 60 seconds in total.

The full split, quality audit and multi-day baseline results are documented in
`WAVERUN_PRESSURE_BUILD_REPORT.md`. The previously inspected 2026-08-18 remains
exploratory, and the 2026-08-16..17 final holdout remains unopened because no
Validation/Walk-forward baseline achieved positive Net EV.
