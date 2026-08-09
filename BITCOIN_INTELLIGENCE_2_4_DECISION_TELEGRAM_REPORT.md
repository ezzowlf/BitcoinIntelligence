# Bitcoin Intelligence 2.4 - Decision, Telegram and Frozen Forward Validation

## Release state

- Frozen champion: `2.3-FROZEN`
- Frozen baseline commit: `0c55061`
- Frozen configuration SHA-256: `db4b6ed6e40fd9f6ce7efe4b0748c61dee83ddcf0603962eb836eeafa8e3ee5f`
- Development branch: `codex/decision-telegram-forward`
- Research cutoff: `2026-08-07T00:00:00Z`
- Forward start: `2026-08-10T00:00:00Z`
- Execution: `DISABLED`

The later forward start is deliberate: funding and open-interest observations through 8/9 August were visible during development. No observation before 10 August is eligible for frozen forward evidence.

## Current decision (last confirmed daily close: 2026-08-07 UTC)

| Field | Result |
|---|---:|
| BTC price | $64,877.77 |
| Market state | VALUE_WITHOUT_CONFIRMATION |
| Long term | ACCUMULATE |
| Swing | WAIT |
| Risk action | CAUTION |
| Decision confidence | MODERATE |
| Value | 70.3 / HIGH_VALUE |
| Historical value percentile | 52.4 |
| Regime | BEAR, LOW stability, 40% agreement |
| Timing | WAIT, score 0 |
| Risk | 7d 37.2 / 30d 43.8 / 90d 48.2 |
| Tail state | NORMAL |
| Evidence | 60.38 / MODERATE |
| Uncertainty | 57.1 / HIGH |
| Data health | 76 / MODERATE; critical feeds healthy |

Interpretation: long-term value supports only small accumulation. The swing engine remains at WAIT because there is no confirmed lower-low rejection, structure reclaim, or H4/D1 confirmation. This is explicitly not a trade instruction.

## Evidence-derived zones

| Zone | Range | Confidence | Confluence |
|---|---:|---:|---:|
| Buy zone 1 / major support | $63,176.58-$64,752.82 | HIGH | 7 |
| Buy zone 2 | $61,243.72-$62,493.90 | MODERATE | 6 |
| Invalidation | below $61,243.72 | MODERATE | - |
| Resistance | $65,216.20-$65,329.02 | LOW | 2 |

These are technical-confluence zones already present in the analyzer, not forecasts or optimized price targets.

## Historical decision research

This is historical research only, uses fixed decision proxies, and was not used to optimize thresholds.

| Decision | Independent episodes | Median 30d | Median 90d | Median adverse excursion |
|---|---:|---:|---:|---:|
| ACCUMULATE | 36 | +14.33% | +28.07% | -3.84% |
| BUY | 19 | +26.08% | +15.10% | -1.03% |
| WAIT | 37 | +14.13% | +12.60% | -5.22% |
| REDUCE | 0 | insufficient evidence | insufficient evidence | insufficient evidence |
| SELL | 0 | insufficient evidence | insufficient evidence | insufficient evidence |

There is therefore no empirical basis in this run to call REDUCE or SELL validated. SELL remains a separate, strict evidence path and is not the inverse of BUY.

## Frozen forward ledger

The SQLite ledger stores frozen daily snapshots, state-change alerts, and later horizon outcomes. Snapshot and alert rows are protected by database triggers against update and delete. Snapshots before the forward start are rejected. Current ledger state is correctly `0 snapshots / 0 alerts`; the source close is 7 August and is not eligible.

Each eligible snapshot records price, value, cycle, regime, timing, risk/capitulation, on-chain, derivatives, evidence, confluence, uncertainty, data quality, market state, system conclusion, decision, frozen model, commit and config hash.

## Telegram decision layer

Implemented read-only commands: `/btc`, `/decision`, `/value`, `/timing`, `/risk`, `/cycle`, `/zones`, `/why`, `/health`.

The default is `TELEGRAM_DRY_RUN=true`. No message was sent. Alerts are emitted only for a material state change, fingerprint-deduplicated, and persisted to the append-only alert ledger. Every message identifies the frozen model and keeps execution disabled.

Verified dry-run headline:

```text
LONG TERM  ACCUMULATE
SWING      WAIT
RISK       CAUTION
Confidence MODERATE
Model      2.3-FROZEN
Execution  DISABLED
```

## Verification

- Test suite: 73 passed
- Python compilation: passed
- Git whitespace check: passed
- Decision CLI: passed
- Telegram `/decision` dry-run: passed, no delivery
- Frozen mutation/cutoff and append-only database tests: passed
- Phase-A PIT replay (2020-03-12): passed; `CAPITULATION`, execution disabled
- Historical decision research: completed
- Dashboard HTTP smoke test: passed

Research-labelled modules remain timing, regime and risk; their outputs are ordinal research signals, not calibrated probabilities. ETF, macro and news are currently unavailable. Price, on-chain, derivatives and seasonality are available; decision confidence is reduced for the three missing groups.

Forward performance is intentionally unreported until eligible observations have matured. Challenger development must use a new version and cannot mutate this champion or its ledger.
