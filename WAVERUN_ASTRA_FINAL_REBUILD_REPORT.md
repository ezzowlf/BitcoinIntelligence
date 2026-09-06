# WAVERUN ASTRA FINAL REBUILD REPORT

**WORK IN PROGRESS — NOT A FINAL ACCEPTANCE REPORT**

Updated UTC: 2026-09-06T21:11:29.446312+00:00

Branch: `codex/waverun-final-rebuild`. Base: `fd0319e07189ca04108d3b253372271f571d62ed`.
Latest completed implementation commit: `6052c28d682cdeac489cf089d3711ced6764b038` (journal/archive foundation only).

**LOCAL GATE NOT REACHED — VPS DEPLOYMENT NOT AUTHORIZED. EXECUTION: DISABLED.**
No VPS access, changes, deployment, orders or production restart in this rebuild run. VPS current state is NOT VERIFIED. No rollback needed yet.

## Binding scope and evidence

The 70-section master request is in local attachment `9b87401a-5743-40e5-bba6-4980cbe948a6/pasted-text.txt`; handover addendum is in conversation. Immutable binding audit: WAVERUN_CODEX_FULL_PRODUCTION_ANALYSIS.md and WAVERUN_CODEX_FINDINGS.json. Their original evidence remains in ignored audit/. Do not regenerate audit/build_report.py. Audit confirms the pipeline freeze; exact historical transport trigger remains INCONCLUSIVE and old prediction quality NOT REPRODUCIBLE. Do not re-run the already completed transfer/ZIP/SQLite entrance checks.

The rejected 696a57a diff was copied as implementation input onto the audited parent, then repaired locally. It is not an accepted release. Frozen V5.3 math/holdout remains outside this rebuild. The new shadow-flow-l2-v1 policy was declared before new replay; no outcome tuning has occurred. No statistical edge or live lead-time claim has been established.

## Completed phases and tests

- Original failure reproduction on immutable candidate: 11 FAIL / 19 PASS (`audit/rebuild-before.xml`).
- Journal/verified raw archive primitives: committed; 4 archive tests PASS (`docs/rebuild/archive-commit.xml`). Covers exact roundtrip, corrupt archive/manifest rejection, retention pins, interrupted-segment salvage and bounded queue overflow.
- Local resilience/signal/outcome iteration: 54 PASS, 0 FAIL, 0 skipped in 42.847s (`docs/rebuild/rebuild-04.xml`). All 11 originally failing probes pass. This was before splitting four archive cases into tests/test_waverun_archive.py; the split archive tests were separately rerun and passed.
- Prior run rebuild-03: 53 PASS / 1 FAIL. Real defect: recovery source age used 180s pipeline budget. Fixed to 5s source age and rerun green. Other historical failed iterations remain in ignored rebuild_artifacts/.
- Crash after outcome commit: durable outbox test PASS, replay delivery idempotent. Forecast mirroring uses persistent cursor; complete process-level restart tests remain open.
- Synthetic CANDIDATE/PREWARNING/ARMED/LIVE reachability and OUTCOME terminal transition PASS. Independent expiry without Spot callbacks PASS. These prove state reachability, not prediction quality.
- Independent move tracking rejects quote-gap paths as incomplete instead of missed trades. Full production move analysis still pending.
- Real 100,000-event storage benchmark: JSONL 39,099,705 bytes; gzip 1,803,173; Parquet/ZSTD 1,677,899 (23.30x). Byte-exact roundtrip PASS. Parquet sample write ~40,475 rows/s and range query ~0.051s. Local warm-cache measurements, NOT VPS guarantees. Complete metrics: docs/rebuild/storage-benchmark.json. Raw benchmark sample is ignored and must never be committed.

## 22-findings live matrix

No finding is declared finally closed before full integration/acceptance. Local probe closure is distinguished from acceptance closure.

| Finding | Acceptance | Implementation / evidence / next work |
|---|---|---|
| WR-001 | OPEN | Independent outcome timer, bounded consumers and journal added; external worker recovery and independent feature scheduling open. |
| WR-002 | OPEN | Application-data timeout passes original and negative-control probes; production soak open. |
| WR-003 | OPEN | Bare TimeoutError retry probe passes; original audit test unchanged, local harness stops after repeated callback failures. |
| WR-004 | OPEN | Durable pipeline-based API gating added; complete feed/source revalidation and UI integration open. |
| WR-005 | OPEN | Separate uncalibrated shadow state machine reaches LIVE in synthetic causal test; full production replay and entry contract open. |
| WR-006 | OPEN | Executable outcomes, terminal statuses, outbox and scheduler added; legacy backlog catchup and full restart integration open. |
| WR-007 | OPEN | Feed lifecycle journal added; process revision metadata and sink-failure isolation open. |
| WR-008 | OPEN | Stable per-market owners expose child crash while sibling runs; local probe PASS. |
| WR-009 | OPEN | Callback timeout separated from read/idle timeout; local hang and socket-to-prediction recovery PASS. |
| WR-010 | OPEN | Handshake no longer advances valid event; local probe PASS. |
| WR-011 | OPEN | Child reconnect no longer cancels session owner; local probe PASS; full restart escalation open. |
| WR-012 | OPEN | Prediction progress uses committed sequence, not DB file mtime; local probe PASS. |
| WR-013 | OPEN | Matching feature/candidate/decision/prediction cause IDs plus advancing scheduler/storage/Spot/Vantage required; original and fresh-source adversarial probe PASS. |
| WR-014 | OPEN | Downstream stalls request repair despite healthy Spot; local probe PASS; actual component-specific restoration open. |
| WR-015 | OPEN | No candidate freshness substitution for decisions or predictions; original probe PASS; full API integration open. |
| WR-016 | OPEN | Missing candidate/storage/disk cannot FULL_LIVE; local probes PASS; percent disk budgets and retention integration open. |
| WR-017 | OPEN | Restart budget and alert dedup persisted; dedup probe PASS; external restart consumer and alert outbox open. |
| WR-018 | OPEN | 54 focused tests PASS, including original 11 failures; full existing suite, negative controls and >=38 chaos inventory not yet accepted. |
| WR-019 | OPEN | New signal transitions carry missing evidence/conflicts; legacy first-failing-gate reporting and full gate analysis open. |
| WR-020 | OPEN | Audit conclusions preserved: old quality NOT REPRODUCIBLE; new causal replay/move coverage analysis open. |
| WR-021 | OPEN | Raw bounded writer and bounded callback consumers added; supervisor synchronous I/O, alert sink and logging lifecycle still open. |
| WR-022 | OPEN | Exchange timestamp recorded and recovery requires source age <=5s; source freshness across feature/API paths still needs adversarial coverage. |

## 11 original safety probes

| Probe | Before | Current local result |
|---|---|---|
| `test_bare_callback_timeout_must_retry` | FAIL | PASS |
| `test_handshake_is_not_event` | FAIL | PASS |
| `test_recovery_requires_prediction_progress` | FAIL | PASS |
| `test_candidate_fresh_decision_stale_api` | FAIL | PASS |
| `test_prediction_mtime_is_not_write_proof` | FAIL | PASS |
| `test_pipeline_stall_triggers_repair` | FAIL | PASS |
| `test_alert_dedupe_survives_manager_restart` | FAIL | PASS |
| `test_level2_does_not_cancel_session` | FAIL | PASS |
| `test_candidate_stall_precludes_full_live` | FAIL | PASS |
| `test_task_crash_visible_while_sibling_runs` | FAIL | PASS |
| `test_callback_hang_is_bounded` | FAIL | PASS |

## Open acceptance work / next phase

1. Finish external process watchdog and durable restart consumer with bounded budget, identity checks and a real restore chain. Health supervisor currently performs sync work on collector event loop; lifecycle log sink exceptions and alert durability need hardening.
2. Finish source-specific freshness for all API/feature paths; attach L2 sequence state, independent stale cancellation and current Vantage timestamp. Reconcile legacy prediction backlog and candidate registration crash gaps; validate restart throughput.
3. Complete hot/warm/cold retention scheduling, percent disk budget 70/80/90/95, event-window pins, P0 compressed rotation and queue/writer-liveness gates. Verified archive primitive exists; automatic retention is NOT integrated.
4. Finish causal feature evidence and move completeness, state monotonicity persistence, actual feed task recovery and complete entry/signal API contract. New features are uncalibrated; derivatives absent must remain unavailable.
5. Integrate dashboard stages, real source/pipeline health and opt-in PREWARNING/LIVE sounds with persistent setup dedup. Copied candidate UI is not final.
6. Run full existing suite, fix legitimate regressions without weakening contracts, add inventory and tests for all requested >=38 chaos/storage/outcome cases and five negative controls. Prior audit had two pre-existing master30 fixture failures; evaluate honestly.
7. Full chronological production replay with causal receive-time availability, executable Vantage Bid/Ask, move-first labels, all horizons and explicit insufficient future data. Retrospective snapshot is not pristine OOS; future shadow production is new OOS. Do not tune thresholds using replay winners or open frozen holdout.
8. Complete matrices/report, commit tested phases, inspect clean release Git state, then determine local gate. Only if fully accepted: read-only VPS inventory, backed-up deploy/rollback plan, accepted revision deployment, service/pipeline verification and >=24h observation.

## Reproducibility and preservation

Only source, tests, documentation and sanitized aggregate/JUnit evidence may be committed. audit/, rebuild_artifacts/, runtime, databases, raw snapshots, environment secrets and credentials stay uncommitted. Current remaining source changes are intentional work in progress, not accepted production code. See WAVERUN_HANDOVER_TO_CLAUDE.md for exact continuation commands.
