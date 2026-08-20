# WAVERUN 180s Blind Validation Report

FROZEN CANDIDATE: `Q1_2025_180S_CHALLENGER_V1`

FINGERPRINT: `a61a4229635da3e3869b08371e3d7dd38290091951b4488a2bda7df13c2a0f60`

RESEARCH REFERENCE: `BINANCE RESEARCH PROXY`

EXECUTION: `DISABLED`

FINAL AUGUST HOLDOUT: `CLOSED / UNTOUCHED`

| Period | Signals | Wins | Losses | Endpoint directional precision (>0) | 95% CI | Net EV | Signals/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1_WF | 15 | 14 | 1 | 93.33% | 70.18%–98.81% | 0.2773% | 0.94 |
| APR_2025 | 83 | 51 | 32 | 61.45% | 50.69%–71.19% | 0.0643% | 2.77 |
| MAY_2025 | 23 | 13 | 10 | 56.52% | 36.81%–74.37% | 0.0049% | 0.74 |
| JUN_2025 | 13 | 9 | 4 | 69.23% | 42.37%–87.32% | -0.0041% | 0.43 |
| APR_JUN_COMBINED | 119 | 73 | 46 | 61.34% | 52.37%–69.61% | 0.0454% | 1.31 |
| JUL_2026 | 25 | 14 | 11 | 56.00% | 37.07%–73.33% | 0.0370% | 0.81 |

TOTAL NEW OOS: 87/144 = 60.42%

OVERALL OOS INCLUDING ORIGINAL WF: 101/159 = 63.52%

90% STATUS: **90% NOT VERIFIED**

CANDIDATE STATUS: **FAILED**

No retraining, recalibration, threshold adjustment, feature change, or post-period filtering was performed.

## Key answers

1. 180s remained the frozen hypothesis, but it did not survive as a high-precision edge.
2. The original 93.33% endpoint directional precision (>0) did not persist; new OOS endpoint directional precision was 60.42%.
3. Independent new signals: 144.
4. Precision fell as sample size increased; 95% CI is 52.26%–68.03%.
5. Aggregate proxy Net EV remained positive, but June was negative.
6. It did not meet the >=70% product target in any blind month.
7. July 2026 precision was 56.00%; recent-regime persistence failed.
8. Feature-distribution drift is present in the machine-readable drift report; signal behavior also changed materially.
9. UP was 62.30%; DOWN was 59.04%; neither is proven reliable.
10. Extreme/exceptional MACD subgroups are diagnostic only and did not rescue July.
11. Expansion subgroups are diagnostic only; no V1 rule was changed.
12. Spot/Futures confirmation was inconsistent across months and is not promoted.
13. False-positive pre-signal fingerprints are preserved in `signal_autopsies.json`.
14. Missed >=10 bp moves are preserved as `MISSED_MOVE_CASE`; this threshold is diagnostic, not a V1 rule.
15. V1 remains immutable as a failed historical challenger and is not production-worthy.
