# Bitcoin Historical Entry Quality Live Integration

- Integration commit: `5d0f4fa` (`Bitcoin MASTER historical entry quality live integration`)
- Branch: `codex/bitcoin-master-3`
- Tests: **144 passed**
- Compile / diff / PIT / secrets: passed
- Dashboard: project `.venv` AppTest 0 exceptions; real HTTP **200**
- HTTP root cause: the bundled desktop runtime produced the Windows OpenSSL Applink abort; the project-local Python 3.13.15 / Streamlit 1.61.1 runtime is reproducible and succeeds without disabling TLS verification.

## Current live state

- BTC: **$64,877.77**
- MASTER Long-Term: **ACCUMULATE**
- MASTER New Entry: **ACCUMULATE**
- MASTER Existing Position: **HOLD**
- MASTER Risk: **CAUTION**
- Production Signal: **NO_PRODUCTION_SIGNAL**
- Historical Entry Quality: **MODERATE, 49.0/100**
- Archetype: **HISTORICAL_SUPPORT_RETEST**
- Entry Timing: **WAIT**
- Execution: **DISABLED**

Matched: `DEEP_DRAWDOWN`, `MAJOR_HISTORICAL_SUPPORT`, `HIGH_VALUE`, `BELOW_200D`.

Missing: `EXTREME_DRAWDOWN`, `BELOW_200W`, `DAILY_RSI_WEAK`, `WEEKLY_RSI_WEAK`, `CAPITULATION_STRESS`.

Unavailable current core factors: none.

## Current values

- Drawdown: **-47.98%**
- Historical drawdown percentile: **47.58**
- Price versus 200D: **-7.81%**
- Price versus 200W proxy: **+1.90%**
- Weekly RSI: **41.56**
- Nearest major support: **$55,244.90-$60,864.85, HIGH**

## Closest historical entries

1. 2012-06-03, 77.8%, Support Retest, historical 365D +2,274.2%, MAE -1.0%
2. 2019-02-14, 77.8%, Support Retest, historical 365D +191.1%, MAE -0.4%
3. 2024-09-07, 77.8%, Support Retest, historical 365D +105.3%, MAE -0.9%

Historical outcomes are not forecasts. Nearest-reference MAE: median -0.94%, best -0.44%, worst -0.96%. The complete frozen set retains the 2018 case with approximately -50.5% further drawdown as an explicit warning.

## Live surfaces

- Normal `master` command contains every Historical Entry Quality field.
- Dashboard MASTER start page shows quality, archetype, timing, decision, checklist, raw values, analogues and downside warning separately.
- Telegram `/master` and `/buy` include compact context.
- Telegram `/history` includes factor states, three analogues, outcomes, MAE and failed-buy reference count.
- Future control snapshots include `historical_entry_quality`.
- Future MASTER snapshots include the expanded state.
- Quality state changes are stored in an append-only ledger.
- TradingView shows drawdown, 200D, 200W proxy, Weekly/Monthly RSI, support, resistance and Bollinger inputs; Python similarity is explicitly not represented in Pine.

## Forward and freeze

- Reference set: `BEST_ENTRY_REFERENCE_SET_V1`, eight episodes.
- Episode and factor-matrix SHA-256 hashes verified.
- MASTER source hash verified.
- Forward start remains `2026-08-10T00:00:00Z`.
- Historical Entry Quality status: `LIVE_RESEARCH_CONTEXT`.

No Production BUY/SELL decision, threshold, Candidate completion, risk rule, Entry Timing rule, Telegram production trigger or automatic execution behavior was changed. No push or deployment was performed.
