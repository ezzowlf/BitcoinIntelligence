# WAVERUN Decision latency

P50/P95/P99: NOT MEASURED.

The current runner exposes feed status and forecast latency for the pre-existing ShortTermEngine, but it does not timestamp the required stages separately (`event received`, `features ready`, `decision created`, `persisted`, `dashboard updated`, `audio`). No latency percentile is inferred from wall-clock duration.
