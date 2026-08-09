# Frozen Forward Validation Policy

## Frozen champion

Bitcoin Intelligence `2.3-FROZEN` is commit `0c55061` with config hash `db4b6ed6e40fd9f6ce7efe4b0748c61dee83ddcf0603962eb836eeafa8e3ee5f`. Its thresholds, weights and decision inputs are stored in `frozen/bitcoin_intelligence_2_3_frozen.json`. Forward outcomes may evaluate this champion but may not silently modify it.

## Cutoffs

- `RESEARCH_CUTOFF = 2026-08-07T00:00:00Z`
- Funding and OI through 8/9 August 2026 were inspected during development.
- `FORWARD_START = 2026-08-10T00:00:00Z`

The first eligible daily snapshot is produced only after the first complete UTC daily candle at or after `FORWARD_START`. Data already inspected during research is never relabelled as holdout.

## Append-only rules

Frozen snapshots and decision alerts are inserted once under immutable primary keys. Existing rows cannot be updated or deleted through the application API. Outcomes are appended only after their horizon has matured. Failed BUY/ACCUMULATE alerts remain permanently visible.

Every snapshot records the frozen model ID, commit, config hash, raw intelligence state, decision state, provider health and `available_at`. Only inputs with `available_at <= snapshot timestamp` are permitted.

## Change control

Any threshold, rule or weight change creates a new challenger version. `2.3-FROZEN` remains unchanged. Forward evidence may be reported but is not used to rewrite prior snapshots or optimize the frozen champion.
