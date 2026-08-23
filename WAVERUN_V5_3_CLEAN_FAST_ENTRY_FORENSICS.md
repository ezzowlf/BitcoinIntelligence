# WAVERUN V5.3 CLEAN FAST ENTRY FORENSICS

Discovery-only causal pre-T0 comparison of the exact frozen 47 SHORT candidates.

- Frozen definition: `cbeb17ec5e2bc819fc54e01da0ed8a70bc319cb248d4aa6b225147b56a946f60`
- Immediate continuation: **19**
- Pullback then continuation: **10**
- Wrong direction: **13**
- Primary $100/5m discovery rate: **29/47 = 61.70%**
- OOS verified: **NO**

## Core difference table

| Feature | Immediate median | Pullback median | Wrong median | Effect | Direction | Separation | Data quality | Interpretation |
|---|---:|---:|---:|---:|---|---|---|---|
| spot_pressure_acceleration | 0.081852 | -0.345335 | 0.786635 | -0.538 | LOWER_IN_IMMEDIATE | STRONG | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| short_favorable_move_180s | 510.01 | 405.85 | 362.52 | 0.514 | HIGHER_IN_IMMEDIATE | STRONG | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was higher; descriptive single-feature separation only. |
| distance_from_recent_high_300s | 789.45 | 616.995 | 535.81 | 0.506 | HIGHER_IN_IMMEDIATE | STRONG | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was higher; descriptive single-feature separation only. |
| range_usd_300s | 882.2 | 682.225 | 535.81 | 0.482 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate cases had higher pre-entry volatility/range; possible chaos veto only if retention is acceptable. |
| macd_300s_histogram_acceleration | 21.9527 | 9.2169 | 3.53762 | 0.457 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was higher; descriptive single-feature separation only. |
| range_usd_60s | 468.3 | 418.375 | 357.11 | 0.457 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate cases had higher pre-entry volatility/range; possible chaos veto only if retention is acceptable. |
| range_usd_180s | 746.6 | 608.755 | 535.81 | 0.457 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate cases had higher pre-entry volatility/range; possible chaos veto only if retention is acceptable. |
| macd_30s_histogram_slope | -28.1547 | -26.8683 | -23.6155 | -0.449 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| spot_lead_1s | -2.28623e-05 | -0.000132871 | -0.000211398 | 0.449 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was higher; descriptive single-feature separation only. |
| price_return_180s | -0.00554319 | -0.00462862 | -0.0041117 | -0.441 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| structure_break | -1 | 0 | 0 | -0.425 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| short_favorable_move_300s | 421.16 | 499.095 | 281.09 | 0.417 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was higher; descriptive single-feature separation only. |
| realized_volatility_300s | 59.16 | 50.2742 | 40.0369 | 0.417 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate cases had higher pre-entry volatility/range; possible chaos veto only if retention is acceptable. |
| spot_pressure_10s | -0.279559 | -0.387155 | -0.141502 | -0.360 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| price_acceleration_180s | -0.00698093 | -0.00525655 | -0.00627242 | -0.360 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| range_position_180s | 0 | 0 | 0.0297661 | -0.352 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| price_acceleration_60s | -0.0033812 | -0.00458767 | -0.00183159 | -0.344 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| price_return_300s | -0.00410587 | -0.00606024 | -0.00306513 | -0.344 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |
| realized_volatility_180s | 61.2758 | 55.9646 | 40.0282 | 0.336 | HIGHER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate cases had higher pre-entry volatility/range; possible chaos veto only if retention is acceptable. |
| range_position_300s | 0 | 0 | 0.0297661 | -0.336 | LOWER_IN_IMMEDIATE | MODERATE | A=19, B=10, C=13; causal T0/pre-T0 proxy | Immediate median was lower; descriptive single-feature separation only. |

## Single-factor findings

- Best veto: **block when `spot_pressure_10s > 0.15022509`**
- Best booster: **block when `range_usd_60s < 464.055`**
- These are discovery hypotheses selected on the same 47 cases and are not validated.

## Matched-pair residual differences

Pairs match approximately on volatility, recent return, MACD histogram/cross age, and session. Reuse of wrong-direction controls is allowed; this is confounder reduction, not independent validation.

| Feature | Median immediate - wrong | Positive pairs | Negative pairs |
|---|---:|---:|---:|
| spot_pressure_acceleration | -1.24241 | 4/19 | 15/19 |
| short_favorable_move_180s | 168.55 | 15/19 | 4/19 |
| distance_from_recent_high_300s | 247.93 | 13/19 | 6/19 |
| range_usd_300s | 258.11 | 13/19 | 6/19 |
| macd_300s_histogram_acceleration | 38.0719 | 15/19 | 4/19 |
| range_usd_60s | 118.23 | 13/19 | 6/19 |
| range_usd_180s | 157.34 | 13/19 | 6/19 |
| macd_30s_histogram_slope | -3.18894 | 6/19 | 13/19 |
| spot_lead_1s | 0.000361467 | 15/19 | 4/19 |
| price_return_180s | -0.00103032 | 5/19 | 14/19 |

## Requested evidence domains

- Momentum age: immediate `35`, pullback `50`, wrong `35`, effect `-0.028` (WEAK).
- MACD cross age: immediate `12`, pullback `15`, wrong `11`, effect `0.332` (MODERATE).
- Price response: immediate `0.00485928`, pullback `0.00495459`, wrong `0.00266357`, effect `0.320` (MODERATE).
- Move already consumed: immediate `510.01`, pullback `405.85`, wrong `362.52`, effect `0.514` (STRONG).
- Volatility: immediate `69.1146`, pullback `86.3779`, wrong `61.48`, effect `0.069` (WEAK).
- VWAP: immediate `-35.1181`, pullback `-173.471`, wrong `-6.7726`, effect `0.004` (WEAK).
- Range position: immediate `0.306694`, pullback `0`, wrong `0.183873`, effect `-0.109` (WEAK).
- Spot/Futures: immediate `1`, pullback `1`, wrong `1`, effect `0.097` (WEAK).
- Flow-price efficiency: immediate `0.00485928`, pullback `0.00495459`, wrong `0.00266357`, effect `0.320` (MODERATE).
- Absorption: immediate `-47.5491`, pullback `-36.6983`, wrong `0`, effect `-0.215` (WEAK).
- Expansion phase: immediate `94.8606`, pullback `97.5701`, wrong `77.3818`, effect `0.150` (WEAK).
- Structural FVG / supply-demand / liquidity-pool / sweep-reclaim: **UNKNOWN**; no deterministic historical fields exist in this layer.

## Data limits

- No historical Vantage Bid/Ask; outcome remains EXCHANGE RESEARCH PROXY.
- No historical L2 path; absorption is a derived proxy, not order-book evidence.
- FVG, supply/demand, liquidity-pool, and sweep/reclaim fields are unavailable and remain UNKNOWN.
- All veto and booster effects are in-sample discovery on the same 47 cases.

HOLDOUT: CLOSED
EXECUTION: DISABLED
