# WAVERUN V5.3 VETO ANALYSIS

Best single veto: **block when `spot_pressure_10s > 0.15022509`**
Best single booster: **block when `range_usd_60s < 464.055`**

Veto primary-group counts: `{'feature': 'spot_pressure_10s', 'block_operator': '>', 'threshold': 0.1502250887673838, 'immediate_kept': 19, 'immediate_blocked': 0, 'wrong_blocked': 5, 'wrong_kept': 8, 'primary_precision': 0.7037037037037037, 'primary_coverage': 0.84375, 'score': 5}`
Applied to all 47: `{'signals_retained': 42, 'fast_winners_retained': 29, 'discovery_rate': 0.6904761904761905, 'median_mae_before_100': 8.5, 'median_time_to_100_s': 25.0}`
Veto + booster applied to all 47: `{'signals_retained': 16, 'fast_winners_retained': 14, 'discovery_rate': 0.875, 'median_mae_before_100': 0.0, 'median_time_to_100_s': 15.0}`

Thresholds were searched on discovery data and must not be interpreted as OOS precision.

HOLDOUT: CLOSED
EXECUTION: DISABLED
