# Bitcoin Historical Entry Quality Monitor

## Scope

`Historical Entry Quality` is a live research context derived from `BEST_ENTRY_REFERENCE_SET_V1`. It is not a calibrated probability, signal, order, or replacement for Entry Timing. MASTER production decisions do not consume its score or state.

## Current state (BTC close 2026-08-07)

- BTC: **$64,877.77**
- Historical Entry Quality: **MODERATE, 49.0/100**
- Archetype: **HISTORICAL_SUPPORT_RETEST**
- Research evidence: **MODERATE**, n=8 independent episodes
- MASTER Long-Term / New Entry / Risk: **ACCUMULATE / ACCUMULATE / CAUTION**
- Entry Timing: **WAIT**
- Production: **NO_PRODUCTION_SIGNAL**
- Execution: **DISABLED**

Matched factors: deep drawdown, major historical support context, high value and price below 200D.

Missing factors: extreme drawdown, price below 200W, weak Daily RSI, weak Weekly RSI and capitulation stress. No required factor is currently unavailable.

Current values:

- Drawdown: **-47.98%**, historical severity percentile 47.58
- Price versus 200D: **-7.81%**
- Price versus 200W proxy: **+1.90%**
- Daily RSI: **not weak**
- Weekly RSI: **41.56, not weak under the frozen research threshold**
- Major support context: **available**, nearest zone $55,244.90-$60,864.85

## Closest historical episodes

| Date | Similarity | Archetype | Historical 365D | Historical MAE |
|---|---:|---|---:|---:|
| 2012-06-03 | 77.8% | Historical Support Retest | +2,274.2% | -1.0% |
| 2019-02-14 | 77.8% | Historical Support Retest | +191.1% | -0.4% |
| 2024-09-07 | 77.8% | Historical Support Retest | +105.3% | -0.9% |

These are historical outcomes, not forecasts. Similarity measures agreement of the frozen factor states, including contradictions; it is not probability.

Episode-level further-drawdown context for the three nearest references: median **-0.94%**, best **-0.44%**, worst **-0.96%**. The full reference set still contains the 2018 lesson with approximately -50.5% MAE: high long-term entry quality never means low risk or a confirmed bottom.

## Successful versus control context

The monitor loads the versioned factor matrix and reports five failed high-value references plus neutral control frequencies. Strong historical differentiators remain deep drawdown, price below 200D, high value, depressed long-horizon location and momentum. Missing success factors are displayed, not converted into a BUY penalty or hidden optimization.

## Fixed staged-entry research

Exactly four predefined research variants were evaluated across eight episodes:

| Variant | n | Median MAE | Median 365D return | Median delay |
|---|---:|---:|---:|---:|
| Single entry | 8 | -1.08% | +182.8% | 0D |
| Two stage | 8 | -0.54% | +184.2% | outcome-only staging |
| Three stage | 8 | -0.36% | +184.7% | outcome-only staging |
| Recovery confirmed | 8 | -9.19% | +128.6% | 10D |

The staged variants use later episode lows as research outcomes and are not executable strategies. Recovery confirmation paid for later information with lower median return and did not uniformly eliminate subsequent drawdown.

## Integration

- Normal MASTER analysis computes the monitor automatically.
- MASTER state exposes the quality state, grouped factors, archetype, closest episodes, MAE and 200D/200W distances.
- Dashboard start page separates Historical Entry Quality, Entry Timing and MASTER Decision.
- Telegram `/master` and `/buy` contain compact context; `/history` provides detailed analogues and failed-buy context.
- Future control and MASTER snapshots store the complete research context.
- Historical Entry Quality state changes are append-only.
- Pine displays only locally calculable inputs and explicitly refuses to imitate Python similarity.

## Frozen boundaries

Reference: `BEST_ENTRY_REFERENCE_SET_V1`, eight episode IDs, episode CSV SHA-256 `186c1370cf957724adb3d21b40a37039f00550880c61658e61e31e3518677d25`, factor matrix SHA-256 `267576b6da48e4603a85a031e94f237c688522464ad247330c931401b2ef3a5e`.

No Production BUY/SELL rule, candidate threshold, risk rule, timing rule or automatic execution behavior was changed.
