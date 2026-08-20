# WAVERUN V2 Strategy Master Report

Final decision: **NO ROBUST V2 STRATEGY FOUND**

Product target `>=3/day & >=70%`: **FAIL**. No V2 candidate was frozen and the final August holdout remains closed.

## Data used

Q1 2025 discovery/train/validation/walk-forward excluding the three screenshot case days; blind April–June 2025; later OOS July 2026. In total: 209 research days, 14,616 non-overlapping hard-move windows, and 159 frozen-V1 baseline signals. Binance is a research proxy; Vantage Bid/Ask history and historical L2 remain unavailable.

## What WAVERUN learned

V1 did not generalize. Meaningful hard moves are common enough in the market, but the existing causal detector cannot isolate them with production precision. Broad MACD did not improve prior OOS work; expansion and Spot/Futures confirmation remain useful hypotheses, not stable rules. DOWN was somewhat easier than UP in the $200/600s/$100 baseline, but neither passed.

## True versus false precursors

At $200 before $100 within 600s, 66 of 159 V1 opportunities succeeded and 93 failed. Spot/Futures confirmation, expansion and extreme MACD all remained below 50% in this baseline. The false library points to divergence, late expansion, absorption/weak price response and pressure decay as blockers requiring unbiased OOS tests.

## Move size

| Target | Historical opportunities/day | Best current OOS precision | Predictive signals/day | Status |
|---:|---:|---:|---:|---|
| $200 | 69.93 | Not established | 0 | No V2 OOS model |
| $300 | 18.19 | Not established | 0 | No V2 OOS model |
| $400 | 9.73 | Not established | 0 | No V2 OOS model |
| $500 | 5.50 | Not established | 0 | No V2 OOS model |
| $600 | 3.29 | Not established | 0 | No V2 OOS model |
| $800 | 1.49 | Not established | 0 | No V2 OOS model |

## Unified strategy architecture

One system is retained: causal market state → continuation/reversion router → direction → monotone magnitude probabilities → target-before-adverse probability → remaining-move/readiness gate → `ACTIVITY_BUILDING / WATCH / ARMED / SIGNAL / ABSTAIN`. Setup families are explanations inside the router, never separately optimized trading systems.

Current defensible behavior is `ABSTAIN`: there is no calibrated V2 barrier model. A future signal requires aligned Spot/Futures evidence, efficient price response, early rather than mature expansion, sufficient remaining move, no absorption/divergence blocker, positive realistic-cost EV and a chronologically validated calibrated probability.

## When WAVERUN should not signal

Spot/Futures divergence; strong flow without price response; mature/exhausting expansion; pressure decay; adverse excursion already too large; less than $200 estimated remaining opportunity; event evidence without point-in-time timestamps; missing Vantage execution metadata; or any probability not calibrated on later unseen data.

## Current model evidence

Prior bounded comparisons covered Logistic, GradientBoosting and RandomForest in the seconds-research pipeline. Logistic was provisionally strongest, but walk-forward stability failed. HistGradientBoosting and ExtraTrees are queued for the unbiased barrier dataset; they were not fit to the positive-only move library plus V1-selected negatives because that would create selection bias.

## Feature evidence

- Flow and pressure: economically plausible, but absolute/extreme pressure alone creates many false positives.
- Spot/Futures confirmation: useful interaction hypothesis; not independently >=70% OOS.
- Expansion: strongest prior diagnostic subgroup, but time stability was not proven.
- MACD: broad use hurt prior OOS; anomaly/acceleration interactions remain bounded research hypotheses.
- Mean reversion: displacement alone is rejected; only exhaustion + absorption + structure change merits further testing.

## Precision-frequency goal

| Target frequency | Best validated precision | N | Net EV | Target magnitude |
|---:|---:|---:|---:|---:|
| 3/day | Not supported | 0 | n/a | n/a |
| 5/day | Not supported | 0 | n/a | n/a |
| 7/day | Not supported | 0 | n/a | n/a |
| 10/day | Not supported | 0 | n/a | n/a |

## Precision ladder

| Precision | Maximum stable signals/day | Status |
|---:|---:|---|
| 70% | 0 | Not found |
| 75% | 0 | Not found |
| 80% | 0 | Not found |
| 85% | 0 | Not found |
| 90% | 0 | Not found |

## Best current configuration

Best diagnostic baseline only: target $200, adverse $200, horizon 600s, frozen V1 source, precision 54.72%, 0.76 evaluated signals/day, proxy EV $-6.29. This is not a V2 strategy and is not eligible for freeze.

## Calibration and magnitude consistency

No 70/80/90 probability is displayed. Future P(>=200...>=800) outputs must be calibrated with Brier, Log Loss, ECE and reliability curves, then projected to non-increasing magnitude probabilities when necessary.

## Limitations

No historical L2; no real Vantage Bid/Ask cost validation; Binance proxy execution; selected-negative bias in existing false precursors; concept drift between 2025 and July 2026; limited point-in-time event history; no unbiased V2 base-state dataset yet.

## Next research queue

1. Build unbiased causal base-state samples at fixed intervals with embargoed target paths.
2. Freeze fresh discovery/train/validation/walk-forward boundaries before model fitting.
3. Compare Logistic, HistGradientBoosting, GradientBoosting, RandomForest and ExtraTrees on identical barrier labels.
4. Test confirmation/absorption, early expansion, pressure acceleration, failed pullback and MACD interactions as bounded ablations.
5. Calibrate the winning architecture and evaluate monthly/fold stability; only then consider a V2 freeze.

## Final gates

- `>=3/day & >=70%`: FAIL
- `>=5/day & >=75%`: FAIL
- `>=3/day & >=80%`: FAIL
- `90% ELITE`: NOT FOUND
- V2 freeze: NOT PERMITTED
- Execution: `DISABLED`
- Final holdout: `CLOSED / UNTOUCHED`
