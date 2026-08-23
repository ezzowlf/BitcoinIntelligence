# WAVERUN V5.3 FAST V2 INDEPENDENT VALIDATION

## Result

**INSUFFICIENT_DATA — no independent validation population is currently available.**

- Hypothesis SHA-256: `49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea`
- Base definition SHA-256: `cbeb17ec5e2bc819fc54e01da0ed8a70bc319cb248d4aa6b225147b56a946f60`
- Frozen veto: `spot_pressure_10s <= 0.1502250887673838`
- Booster: `NONE`
- Primary outcome: SHORT MFE >= $100 within 300 seconds

## Independent-data gate

- Existing derived dates: **212**
- Existing range: **2025-01-01 through 2026-07-31**
- Dates available after the discovery cutoff: **0**
- Reserved 2026-08-16/17 holdout accessed: **NO**
- Protocol minimum: **100 independent candidates**

All existing derived days through 2026-07-31 were searchable inputs to the discovery process that produced the 47 candidates and the veto. Reusing them would be in-sample, not independent validation.

## Required metrics

- TOTAL V2 SIGNALS: **0 independent observations available**
- SIGNALS/DAY: **NOT ESTIMABLE**
- $25/$50/$75/$100/$150/$200/$300/$500 within 300s: **NOT ESTIMABLE**
- COMPARABLE SHORT BASE RATE: **NOT ESTIMABLE**
- ABSOLUTE / RELATIVE LIFT: **NOT ESTIMABLE**
- MAE BEFORE $100: **NOT ESTIMABLE**
- TIME TO FIRST POSITIVE / $100: **NOT ESTIMABLE**
- PATH CLASSES: **NOT ESTIMABLE**
- VETO BLOCK AUDIT: **NOT ESTIMABLE**
- WILSON 95% CI: **NOT ESTIMABLE**

## Decision

- DISCOVERY RATE: **29/42 = 69.05%**
- OOS RATE: **NOT ESTIMABLE**
- 3 SIGNALS/DAY: **NOT EVALUABLE / INSUFFICIENT**
- >=65% OOS: **NOT EVALUABLE / INSUFFICIENT**
- >=70% OOS: **NOT EVALUABLE / INSUFFICIENT**
- VETO REPLICATED: **INSUFFICIENT**
- V5.3 FAST V2: **INSUFFICIENT**

Next action: derive a genuinely post-2026-07-31, non-holdout period under the unchanged pipeline and accumulate at least 100 independent V2 signals. Do not modify the veto after seeing future results.

HOLDOUT: CLOSED
EXECUTION: DISABLED
