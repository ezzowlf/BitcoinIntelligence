# WAVERUN remediation design — acceptance contract

Status: IN PROGRESS. Deployment gate CLOSED. Execution DISABLED.

Base: fd0319e07189ca04108d3b253372271f571d62ed.
Branch: codex/waverun-final-rebuild.
Audit input: immutable WAVERUN_CODEX_FULL_PRODUCTION_ANALYSIS.md and
WAVERUN_CODEX_FINDINGS.json; audit had no commit. Their original hashes are in
audit/report-verification.json. 696a57a is an audited, rejected input, not a release.
Unrelated WAVERUN-migration/c051 changes are not imported.

## Design decisions before implementation

1. Preserve the frozen V5.3 module and legacy forecast/decision contracts. Add a
   separately versioned research signal engine with an explicit source contract.
   It does not claim calibrated probability or a demonstrated trading edge.
   LIVE names a timestamped shadow signal, never a broker order or healthy socket.
2. Each Binance market has a supervised task; L2 receives its own connection and
   progress. Recreate requests cancel child connections, not their stable owner.
   Connect, read, valid-data and callback budgets are distinct. Failure state is
   visible immediately; backoff has bounded jitter and a rolling retry budget.
3. Durable SQLite journal transactions contain stage identity, event time,
   receive time, stage completion time, sequence and boot identity. API health
   validates all required stages independently. A file mtime, handshake, or
   unrelated Futures event is never sufficient evidence for FULL_LIVE/RECOVERED.
4. Use bounded queues and isolated workers for synchronous storage. Raw writes
   rotate; P0 decisions/signals/outcomes/incidents are durable and never removed
   by retention. Queue overflow and failed commits close the signal/health gate.
   External process supervision detects a blocked collector loop and owns durable
   restart budgets; no fictional restart-request consumer.
5. Store Vantage Bid/Ask and their actual timestamps. Resolve each registered
   observation at 30/60/120/180/300/600/900/1800/3600 seconds. A committed outcome
   or an explicit terminal data status is required. Restart resumes pending work.
   Gaps do not become losses; no interpolation across missing execution evidence.
6. Signal engine: causal rolling features → persistent setup identity → Candidate
   → PREWARNING → ARMED → LIVE or cancellation/rejection/expiry. Required data:
   Vantage quote and Spot trade flow; L2 required for the L2 entry contract;
   Futures confirmation optional and never silently substituted. OI/funding/
   liquidation fields are unavailable unless their actual provider supplies them.
   Feature contract and fixed pre-replay parameters are versioned before replay.
7. New move-first labels are offline/forward measurement only. Detect declustered
   moves independently of signals, then associate earlier transitions. Persist
   missed moves, false warnings and all data exclusions. Lead-time buckets and
   train/validation/holdout chronology are fixed before replay, with no tuning
   against the audit incident or frozen research holdouts.
8. Benchmark lossless Parquet/ZSTD against JSONL and compressed alternatives using
   real transferred records. Retention derives from measured rates and disk;
   deletion requires verified checksum/count/schema/range/round-trip manifest and
   no pending outcome/event-window dependency. P0 has no automatic deletion.
9. UI shows separate system health and signal states, evidence, missing sources,
   entry-side/zone, window, invalidation and uncalibrated confidence as unavailable.
   Sound is user-enabled, per-setup/state deduplicated; simulated data stays marked.

## Acceptance sequence

Reproduce eleven red audit probes → implement → exact regression with bounded
test harness → adversarial negative controls → all existing backend tests →
signal/outcome/storage/resilience E2E → chronological replay and storage benchmark
→ frontend type/build/UI tests → security and release matrix. Only then evaluate
LOCAL ACCEPTED. A failed gate does not authorize a VPS read/write workaround.

After LOCAL ACCEPTED: read-only VPS inventory, verify execution disabled, consistent
backup and practical rollback, deploy the accepted commit, smoke/recovery checks,
24-hour shadow observation with immutable release and actual telemetry. No
production acceptance is claimed before that window completes.

## Evidence limitations

Historical socket trigger and process module hash cannot be recovered from missing
logs. They remain historical accepted limitations, while new observability must
be implemented and tested. Old production precision starts as NOT REPRODUCIBLE.
Synthetic reachability and replay are explicitly not new production performance.
