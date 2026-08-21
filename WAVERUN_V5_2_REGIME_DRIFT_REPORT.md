# WAVERUN V5.2 Regime Drift Report

The adaptive-ranking research used 3,663,360 existing rows: Q1-2025 training, Apr-Jun-2025 unseen, and Jul-2026 unseen. The locked 2026-08-16/17 dates were excluded.

Observed Q1 → Jul shifts:

| Feature | Q1 mean | Jul mean | Q1 std | Jul std |
|---|---:|---:|---:|---:|
| price_return_30s | -0.00000034 | 0.00000082 | 0.000562 | 0.000329 |
| price_acceleration_30s | 0.000000010 | 0.000000007 | 0.000791 | 0.000463 |
| flow_pressure | -0.0199 | -0.0098 | 0.5083 | 0.5397 |
| spot_futures_agreement | 0.3549 | 0.3235 | 0.9349 | 0.9462 |
| expansion_score | 4.67 | 5.95 | 43.15 | 43.73 |
| volatility_score | 2.12 | 4.20 | 43.71 | 44.10 |
| macd_alignment | -0.0450 | -0.0371 | 2.662 | 2.576 |

The material change is lower short-horizon price-return/acceleration dispersion together with higher volatility/expansion score means and slightly weaker Spot/Futures agreement. This is consistent with a changed opportunity landscape, but it is not proof of causality. A causal drift warning could have flagged the distribution shift; the tested ranker did not recover performance in Jul.

Historical Vantage Bid/Ask, L2, OI/liquidation and Coinbase data were not available in this tier and were not imputed.
