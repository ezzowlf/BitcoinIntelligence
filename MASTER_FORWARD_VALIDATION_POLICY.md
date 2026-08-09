# MASTER 3.0 Forward Validation Policy

`MASTER_3_0_FROZEN` uses 2.5 as its primary analysis model and `2.3-FROZEN` as control. Historical MASTER replay is `RESEARCH_ONLY` because the complete history was visible during development.

Research cutoff remains `2026-08-07T00:00:00Z`. Funding/OI through 8/9 August had already been visible before MASTER development. No completed BTC price candle beyond 7 August was used, so the first conservatively unknown eligible timestamp remains `2026-08-10T00:00:00Z`.

Every eligible MASTER snapshot is append-only and stores the MASTER state/decision plus source versions for 2.3 and 2.5. Outcomes live separately. Rejected historical SELL evidence cannot activate a Production SELL. Any change to registry status, hierarchy or decision rules requires a new MASTER version and a later forward start; old snapshots and errors are never rewritten or deleted.
