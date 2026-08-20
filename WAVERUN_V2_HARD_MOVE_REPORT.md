# WAVERUN V2 Hard Move Report

Primary metric: **target hit before adverse barrier**. Endpoint direction is diagnostic only.

This is a historical V1-baseline reconstruction for V2 design, not a trained or frozen V2 model. Prices and 3 bp costs are Binance research proxies; execution is disabled and the August holdout is untouched.

Primary displayed adverse barrier: **$100**. The complete predefined $50/$75/$100/$150/$200 grid is in `hard_move_result.json`.

Cell format: `precision [Wilson 95% CI]; wins/N; successful opportunities/day; lead; MFE/MAE; proxy EV; UP/DOWN precision`.

| Target | 30s | 60s | 90s | 180s | 300s | 600s |
|---:|---:|---:|---:|---:|---:|---:|
| $200 | 15.1% [10.4%,21.5%]; 24/159; 0.11/d; 18s; $285/$195; $-80; 13.6%/16.1% | 29.6% [23.0%,37.1%]; 47/159; 0.22/d; 30s; $285/$195; $-36; 21.2%/35.5% | 31.4% [24.7%,39.0%]; 50/159; 0.24/d; 35s; $285/$195; $-31; 24.2%/36.6% | 37.1% [30.0%,44.8%]; 59/159; 0.28/d; 45s; $285/$195; $-14; 33.3%/39.8% | 39.6% [32.4%,47.4%]; 63/159; 0.30/d; 45s; $285/$195; $-6; 34.8%/43.0% | 41.5% [34.1%,49.3%]; 66/159; 0.32/d; 45s; $285/$195; $-1; 36.4%/45.2% |
| $300 | 6.3% [3.5%,11.2%]; 10/159; 0.05/d; 22s; $285/$195; $-100; 4.5%/7.5% | 12.6% [8.3%,18.6%]; 20/159; 0.10/d; 32s; $285/$195; $-75; 9.1%/15.1% | 17.0% [11.9%,23.6%]; 27/159; 0.13/d; 40s; $285/$195; $-57; 12.1%/20.4% | 24.5% [18.5%,31.8%]; 39/159; 0.19/d; 60s; $285/$195; $-27; 19.7%/28.0% | 28.3% [21.9%,35.8%]; 45/159; 0.22/d; 65s; $285/$195; $-12; 25.8%/30.1% | 29.6% [23.0%,37.1%]; 47/159; 0.22/d; 70s; $285/$195; $-7; 27.3%/31.2% |
| $400 | 3.8% [1.7%,8.0%]; 6/159; 0.03/d; 22s; $285/$195; $-106; 1.5%/5.4% | 6.9% [3.9%,12.0%]; 11/159; 0.05/d; 30s; $285/$195; $-91; 6.1%/7.5% | 9.4% [5.8%,15.0%]; 15/159; 0.07/d; 35s; $285/$195; $-78; 7.6%/10.8% | 15.1% [10.4%,21.5%]; 24/159; 0.11/d; 68s; $285/$195; $-50; 13.6%/16.1% | 20.1% [14.6%,27.0%]; 32/159; 0.15/d; 98s; $285/$195; $-25; 19.7%/20.4% | 25.2% [19.1%,32.4%]; 40/159; 0.19/d; 120s; $285/$195; $+1; 24.2%/25.8% |
| $500 | 1.3% [0.3%,4.5%]; 2/159; 0.01/d; 22s; $285/$195; $-118; 0.0%/2.2% | 4.4% [2.1%,8.8%]; 7/159; 0.03/d; 40s; $285/$195; $-99; 4.5%/4.3% | 5.7% [3.0%,10.4%]; 9/159; 0.04/d; 45s; $285/$195; $-91; 4.5%/6.5% | 10.1% [6.3%,15.7%]; 16/159; 0.08/d; 72s; $285/$195; $-65; 9.1%/10.8% | 14.5% [9.8%,20.8%]; 23/159; 0.11/d; 100s; $285/$195; $-38; 15.2%/14.0% | 19.5% [14.1%,26.3%]; 31/159; 0.15/d; 180s; $285/$195; $-8; 22.7%/17.2% |
| $600 | 0.6% [0.1%,3.5%]; 1/159; 0.00/d; 15s; $285/$195; $-121; 0.0%/1.1% | 2.5% [1.0%,6.3%]; 4/159; 0.02/d; 40s; $285/$195; $-108; 3.0%/2.2% | 3.1% [1.4%,7.1%]; 5/159; 0.02/d; 40s; $285/$195; $-103; 3.0%/3.2% | 5.7% [3.0%,10.4%]; 9/159; 0.04/d; 70s; $285/$195; $-86; 4.5%/6.5% | 7.5% [4.4%,12.7%]; 12/159; 0.06/d; 105s; $285/$195; $-72; 7.6%/7.5% | 11.9% [7.8%,17.9%]; 19/159; 0.09/d; 200s; $285/$195; $-42; 13.6%/10.8% |
| $800 | 0.0% [0.0%,2.4%]; 0/159; 0.00/d; n/a; $285/$195; $-125; 0.0%/0.0% | 0.6% [0.1%,3.5%]; 1/159; 0.00/d; 40s; $285/$195; $-120; 1.5%/0.0% | 1.9% [0.6%,5.4%]; 3/159; 0.01/d; 80s; $285/$195; $-108; 1.5%/2.2% | 3.1% [1.4%,7.1%]; 5/159; 0.02/d; 85s; $285/$195; $-97; 4.5%/2.2% | 3.1% [1.4%,7.1%]; 5/159; 0.02/d; 85s; $285/$195; $-97; 4.5%/2.2% | 6.9% [3.9%,12.0%]; 11/159; 0.05/d; 365s; $285/$195; $-63; 10.6%/4.3% |

## Independent hard-move availability

- $200: 14616 independent nested opportunities, 69.93/day; median time from earliest qualifying anchor 415s
- $300: 3802 independent nested opportunities, 18.19/day; median time from earliest qualifying anchor 305s
- $400: 2033 independent nested opportunities, 9.73/day; median time from earliest qualifying anchor 335s
- $500: 1149 independent nested opportunities, 5.50/day; median time from earliest qualifying anchor 350s
- $600: 687 independent nested opportunities, 3.29/day; median time from earliest qualifying anchor 360s
- $800: 311 independent nested opportunities, 1.49/day; median time from earliest qualifying anchor 375s

## Required conclusions

- Best diagnostic precision/frequency cell: $200/600s/$200 adverse = 54.72%, 0.42 successes/day, N=159.
- Most predictable tested magnitude in the baseline: $200 in the post-hoc V1 baseline; no V2 OOS proof.
- Best predefined adverse barrier by proxy EV: $50 for $400/600s, proxy EV $+21.06 (post-hoc diagnostic, not a V2 rule).
- DOWN versus UP at $200/600s/$100: UP 36.36%, DOWN 45.16%.
- Mechanism diagnostic: SPOT_FUTURES_CONFIRMATION highest at 50.00%, N=14 (post-hoc).
- False-positive mechanism diagnostic: SPOT_LED_BREAKOUT lowest at 29.41%, 12 false cases of N=17 (post-hoc).
- Extreme MACD diagnostic: 40.52%, N=153 (post-hoc).
- Spot/Futures confirmation diagnostic: 46.59%, N=88 (post-hoc).
- Early Expansion diagnostic: 42.50%, N=120 (post-hoc).
- Elite 80–90% class: NONE PROVEN.
- Product target 3–10/day at >=70% OOS: NOT ACHIEVED.
- Any setup family >=70% OOS: NO; V2 has not yet been trained and chronologically validated.
- Mechanism, MACD, Spot/Futures, expansion, true-precursor and false-precursor diagnostics are persisted machine-readably; no subgroup is promoted without fresh chronological OOS validation.

V1 remains immutable and `FAILED`. V2 status: `RESEARCH_BASELINE_ONLY`. Execution: `DISABLED`.
