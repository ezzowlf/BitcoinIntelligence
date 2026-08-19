# WAVERUN 80% Precision and Best-Horizon Research

Date: 2026-08-20

Mode: `RESEARCH_ONLY`

Execution: `DISABLED`
Edge classification: **PROMISING BUT NOT PROVEN**

## Research boundary

The experiment used complete day blocks only:

```text
CORE TRAIN       2026-07-20 .. 2026-08-03
CALIBRATION      2026-08-04 .. 2026-08-06
VALIDATION       2026-08-07 .. 2026-08-11
WALK FORWARD     2026-08-12 .. 2026-08-15 (four daily folds)
FINAL HOLDOUT    2026-08-16 .. 2026-08-17 (LOCKED / UNOPENED)
EXPLORATORY      2026-08-18 (EXCLUDED)
```

The derived dataset contains 466,558 sampled observations from 27 days. Each
feature is based only on completed/current data. Outcomes use future Vantage
Bid/Ask solely as labels. The cost model uses the observed Vantage spread plus
1 bp roundtrip slippage. No holdout partition was generated or loaded.

The append-only registry currently records 65 experiments, three model
families, nine feature sets, eight probability thresholds and three strategy
families. A failed technical run remains counted.

## Horizon discovery

The table reports the Logistic two-stage model's Validation top-1% bucket.
Training metrics are not used for ranking.

| Horizon | Precision | Signals | Net EV | Status |
| ---: | ---: | ---: | ---: | --- |
| 30s | 58.91% | 864 | -0.0282% | cost-negative |
| 1m | 53.47% | 864 | -0.0248% | cost-negative |
| 90s | 60.76% | 864 | -0.0149% | cost-negative |
| 2m | 63.15% | 863 | -0.0096% | cost-negative |
| 3m | 67.32% | 863 | +0.0044% | positive Validation |
| 4m | 66.47% | 862 | +0.0043% | positive Validation |
| 5m | **68.18%** | 861 | **+0.0153%** | Validation leader |

Best forecast horizon: **5 minutes**, provisionally. It is not a champion.

## Precision versus coverage

For Logistic 5m on Validation:

| Coverage | Precision | Signals | Net EV |
| ---: | ---: | ---: | ---: |
| 50% | 54.13% | 43,048 | -0.0292% |
| 25% | 56.57% | 21,524 | -0.0236% |
| 10% | 59.35% | 8,610 | -0.0166% |
| 5% | 59.05% | 4,305 | -0.0149% |
| 2% | 63.94% | 1,722 | -0.0019% |
| 1% | **68.18%** | 861 | **+0.0153%** |

Selectivity improves precision materially, but the current data does not show
a robust 80% class. Validation 95% CI at 1% coverage is 64.99–71.20%.

Calibration diagnostics for the direction model are Brier 0.2490, log loss
0.6911, direction ECE 0.0284 and correctness-confidence ECE 0.0125.

## Walk-forward

The full 5m model's fixed top-1% policy produced:

| Fold | Precision | Signals | Net EV |
| --- | ---: | ---: | ---: |
| 2026-08-12 | 83.24% | 173 | +0.0628% |
| 2026-08-13 | 58.96% | 173 | +0.0302% |
| 2026-08-14 | 65.90% | 173 | -0.0021% |
| 2026-08-15 | 72.25% | 173 | -0.0233% |
| Combined | **67.63%** | 689 | **+0.0183%** |

Combined 95% CI is 64.05–71.02%. Two negative folds fail the predefined
stability gate. The candidate was not frozen and the final holdout remains
locked.

## Feature value

Removing MACD improves the 5m result most:

```text
FULL          Validation 68.18%, Walk-forward 67.63%, WF Net EV +0.0183%
without MACD  Validation 72.01%, Walk-forward 68.21%, WF Net EV +0.0262%
```

The no-MACD variant still has two negative daily folds (-0.0091% and
-0.0244%), so it is not freeze-eligible. Current conclusion: **MACD provides
negative incremental OOS value in this feature/model family**. It must not be
kept for narrative reasons.

Removing regime features collapses Validation to 48.78% and -0.0390%, and
Walk-forward to 57.33% and -0.0201%. Regime is the strongest indispensable
feature family in this run. Spot, Futures, origin, absorption and mean-reversion
ablations have smaller incremental effects.

## Mean reversion

Walk-forward comparison:

| Stage | Signals | Precision | Net EV |
| --- | ---: | ---: | ---: |
| MR-0 naive z-score | 10,857 | 51.42% | -0.0360% |
| MR-1 displacement | 7,009 | 51.68% | -0.0363% |
| MR-2 + exhaustion | 217 | 51.61% | -0.0362% |
| MR-3 + absorption | 12 | 25.00% | -0.0762% |
| MR-4 + full confirmation | 0 | insufficient sample | unavailable |

MR-4 blocks bad countertrend entries by becoming extremely selective, but it
does not yet produce an evaluable or profitable setup class.

## Reaction and cost sensitivity

At the fixed Walk-forward top-1% selection, 0–10 second reaction delays remain
between 67.20% and 67.92% precision. Net EV remains positive in every tested
delay; at 3 seconds it is +0.0183%, and at 10 seconds +0.0198%.

Net EV sensitivity at 3 seconds:

```text
0 bp roundtrip slippage: +0.0283%
1 bp roundtrip slippage: +0.0183%
2 bp roundtrip slippage: +0.0083%
```

## Time and regime diagnostics

These are diagnostics, not optimized rules:

- Best sufficiently sampled UTC hour: 15 UTC, 71.77%, n=294, +0.0114%.
- Corresponding Berlin summer time: 17:00 CEST.
- Best regime: EXPANSION, 75.79%, n=252, +0.0614%, CI 70.14–80.67%.
- The selected events occur almost entirely during the defined US session.
- An elevated-spread subgroup reaches 79.49% at n=78, but is too small and
  counterintuitive to promote; no spread-based rule was created.

Best early-warning lead time and ARMED lead time remain **UNAVAILABLE** because
this build validated point predictions, not a causal WATCH/ARMED transition
policy. A 5m forecast horizon must not be mislabeled as 5m warning lead.

## Final decision

```text
Highest robust combined precision: 68.21% (no-MACD 5m variant)
Combined Walk-forward Net EV:       +0.0262%
Signals:                            689
Daily stability:                    FAILED (two negative folds)
80% class:                          NOT PROVEN
Candidate frozen:                   NO
Final holdout opened:               NO
Execution:                          DISABLED
```

There is a promising selective 5m research pattern, especially in expansion,
but it does not satisfy the stability gate. No live signal, champion registry
entry, WATCH/ARMED rule or production behavior is changed.

## Technical validation

```text
Focused WAVERUN tests: 28 passed
Full pytest:            395 passed
Ruff changed scope:     PASS
Compile:                PASS
git diff --check:       PASS
Secrets pattern scan:   PASS
```
