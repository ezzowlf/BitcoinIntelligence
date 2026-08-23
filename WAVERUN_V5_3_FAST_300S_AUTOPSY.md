# WAVERUN V5.3 FAST 300S AUTOPSY

**DISCOVERY FAST-PATH RATE — NOT OOS VERIFIED.** Historical Vantage Bid/Ask was unavailable; paths are EXCHANGE RESEARCH PROXY.

## Cumulative target reach within 300 seconds

| Target | Count | Rate |
|---:|---:|---:|
| >= $25 | 37/47 | 78.72% |
| >= $50 | 34/47 | 72.34% |
| >= $75 | 33/47 | 70.21% |
| >= $100 | 29/47 | 61.70% |
| >= $150 | 27/47 | 57.45% |
| >= $200 | 23/47 | 48.94% |
| >= $300 | 17/47 | 36.17% |
| >= $400 | 13/47 | 27.66% |
| >= $500 | 10/47 | 21.28% |

## Comparable SHORT base rate

Candidate: **61.70%**. Base: **798048/3663240 = 21.79%**. Absolute lift: **39.92 pp**. Relative lift: **2.83x / 183.23%**.

## Entry quality

MAE before $100, adverse magnitude: P50 **$8.50**, P75 **$90.30**, P90 **$135.26**, max **$196.41**.
Time to first positive: P50 **5.0s**, P75 **20.0s**, P90 **27.0s**.
Time to $100: P50 **25.0s**, P75 **75.0s**, P90 **107.0s**.
First-300s MFE: P50 **$189.50**, P75 **$417.13**, P90 **$797.44**.
First-300s MAE adverse magnitude: P50 **$280.66**, P75 **$466.69**, P90 **$605.35**.

### Time to target among cases reaching that target by 300s

| Target | P50 | P75 | P90 |
|---:|---:|---:|---:|
| $25 | 15.0s | 25.0s | 125.0s |
| $50 | 22.5s | 62.5s | 181.5s |
| $75 | 25.0s | 55.0s | 141.0s |
| $100 | 25.0s | 75.0s | 107.0s |
| $150 | 40.0s | 92.5s | 155.0s |
| $200 | 45.0s | 112.5s | 165.0s |

## Path order

- $25: ADVERSE_FIRST 26, FAVORABLE_FIRST 21
- $50: ADVERSE_FIRST 25, FAVORABLE_FIRST 22
- $75: ADVERSE_FIRST 23, FAVORABLE_FIRST 24
- $100: ADVERSE_FIRST 24, FAVORABLE_FIRST 22, NO_RELEVANT_MOVE 1

## Path classes

Deterministic rules: NO_MOVE means both MFE and adverse magnitude < $25; a $100 hit is IMMEDIATE_CONTINUATION when MAE-before-target <= $50 and PULLBACK_THEN_CONTINUATION otherwise; SPIKE_THEN_REVERSAL reaches $50 without $100 and finishes non-positive; WRONG_DIRECTION has MFE < $50 and adverse magnitude >= $100; all remaining paths are CHOP.

- IMMEDIATE_CONTINUATION: **19**
- PULLBACK_THEN_CONTINUATION: **10**
- SPIKE_THEN_REVERSAL: **4**
- CHOP: **1**
- WRONG_DIRECTION: **13**
- NO_MOVE: **0**

## Interpretation

The 60-minute window did **not** create most of the old 87.2% result: 29/41 (70.73%) old winners reached $100 within five minutes; 12/41 (29.27%) depended on more than five minutes. This remains discovery evidence, not verified OOS precision or execution evidence.

Frozen definition SHA-256: `cbeb17ec5e2bc819fc54e01da0ed8a70bc319cb248d4aa6b225147b56a946f60`

HOLDOUT: CLOSED
EXECUTION: DISABLED
