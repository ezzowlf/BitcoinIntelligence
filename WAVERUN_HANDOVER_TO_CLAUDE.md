# WAVERUN handover to Claude

Updated UTC: 2026-09-06T21:30:55.359944+00:00
Branch: `codex/waverun-final-rebuild`
HEAD at refresh: `5f32403` (run `git rev-parse HEAD` for any subsequent documentation commit).
Base: `fd0319e07189ca04108d3b253372271f571d62ed`
Workspace: `C:\Users\djaez\.codex\worktrees\9b72\Bitcoin`

**EXECUTION DISABLED. LOCAL GATE NOT REACHED. VPS UNCHANGED. DO NOT DEPLOY.**
Target 207.180.245.205; no VPS connection/inspection during rebuild, current production state NOT VERIFIED; no rollback needed yet.

## Read first

Master: `C:\Users\djaez\.codex\attachments\9b87401a-5743-40e5-bba6-4980cbe948a6\pasted-text.txt` (70 sections). User still requires ENTIRE rebuild and gated deployment plus >=24h observation. Handover requirement does not reduce acceptance criteria.
Binding audit: WAVERUN_CODEX_FULL_PRODUCTION_ANALYSIS.md + WAVERUN_CODEX_FINDINGS.json (immutable, locally untracked); do not rerun completed entrance checks or regenerate audit/build_report.py.
Current phase/history: WAVERUN_ASTRA_FINAL_REBUILD_REPORT.md. Live matrices: docs/rebuild/findings-matrix.json (22) and safety-probe-matrix.json (11). No whole-system finding finally closed; all OPEN_ACCEPTANCE, local evidence listed individually. All11 original safety failures currently pass.

## Commits / completed phases

- 6052c28: durable journal / verified Parquet-ZSTD archive foundation; 4 archive tests PASS, real100k benchmark 23.30x exact roundtrip PASS.
- b8779bd + 82d85e3: report/matrices/handover and honest failure evidence.
- 98afecb: external owned-child watchdog, persistent budget, exclusive OS lock, boot-bound requests, stale-health detection; 5 PASS including real child restart/reaping.
- a539a34: two known baseline Master test assumptions replaced with explicit test inputs. Frozen production code untouched; 42 Master/API PASS.
- 9950628: conservative disk tiers/retention/event pins/pending-outcome floor; 7 PASS.
Last completed validation: integrated archive/storage isolation 13 PASS; main integration 91 PASS. Backend integration foundation is now committed at 5f32403; frontend work remains uncommitted WIP.

## Current process / tests

Full03 COMPLETED: 570 PASS, 0 FAIL/ERROR/SKIP in196.10s. Evidence docs/rebuild/full-03.xml; backend baseline committed5f32403. Do not repeat unchanged full suite. Source hash snapshot: rebuild_artifacts/full-03-source-fingerprint.json.
Full01: 501 PASS/13 FAIL/42 ERROR, missing historic DB fixtures. Four previously audited fixture DBs copied READONLY via SQLite backup into ignored database/; old locally generated DBs backed up in rebuild_artifacts/full_suite_fixture_backup, provenance full-suite-fixture-provenance.json.
Full02: 558 PASS/3 FAIL: two audited baseline Master fixture defects and one candidate-only stale fixture; corrected. Focused rerun42 PASS. Integration02 collection IndentationError fixed; integration03 all91 PASS. Archive slow-compression/failure isolation +storage policy all13 PASS. No hidden skipped probes.

## Implemented working architecture

Stable independent Spot/Futures/L2 owners; bounded connect/read/valid-event/callback/retry budgets; source-specific committed progress; true recovery matches feature/candidate/decision/prediction causes and fresh advancing Spot/Vantage. Journal and outcome outbox with forecast cursor; independent expiry/outcome scheduler; versioned uncalibrated shadow signal states and executable-side outcomes; move-first labels reject quote gaps. Raw ingestion and compression have separate bounded threads; verified manifests, storage readiness/disk gate and event-window pins wired. Supervisor I/O off event loop; external watchdog boot wiring added. Old696a57a diff was copied as implementation input, not accepted release.

## Still open (do not claim accepted)

1. End-to-end watchdog/service recovery, worker hangs/task exits/MT5 recovery, boot revision metadata, persistent ledger-error gating across restarts.
2. Alert outbox/delivery independence/reminders and P0 rotation/compaction; archive retention capacity long-run. All compressed raw archives currently retained, P0 never auto deleted.
3. Legacy prediction backlog and candidate registration crash gaps; causal quote/source timestamps, feature completeness/derivatives/windows, move definition and event pin timestamps. New policy uncalibrated, no edge claim.
4. Dashboard full signal/stage contract, true health, opt-in PREWARNING/LIVE sounds with durable dedup; frontend build/E2E.
5. All >=38 specified chaos cases, 5 negative controls, complete production chronological replay, gate/missed-move/lead/outcome metrics, no winner tuning. Frozen V5.3/holdout untouched.
6. Complete report/matrices and local acceptance. Only then VPS inventory/backups/accepted commit deployment/live verification/24h observation.

## Exact continuation

```powershell
Set-Location 'C:\Users\djaez\.codex\worktrees\9b72\Bitcoin'
git branch --show-current
git rev-parse HEAD
git status --short
Get-Content rebuild_artifacts/full-03.log -Tail 35
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TELEGRAM_ENABLED='false'
$env:MT5_ENABLED='false'
# Only after prior run completes and new changes justify rerun:
& 'C:\Users\djaez\Documents\ChatGPT\Bitcoin\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp=rebuild_artifacts/resume_tmp --junitxml=rebuild_artifacts/resume.xml --tb=short
```

Next: finish frontend shadow contract and opt-in audio; npm ci --ignore-scripts completed locally, frontend not yet built/tested. Then continue unfinished acceptance work above. Update reports/matrices/handover after every phase, explicit source staging only (Git metadata outside sandbox may require escalation). Do not commit secrets, runtime, databases, raw benchmark data, production snapshot or audit code clones.
Replay source READONLY: `C:\Users\djaez\Documents\TAKEOFF\Exports\exports\WAVERUN_FULL_TRANSFER_20260906_132904` (04_market_events_full,05_vantage,08_candidates_decisions,03_databases). Original27,812,107 market rows already verified. Historical quality NOT REPRODUCIBLE, exact transport trigger INCONCLUSIVE. No deployment before local gate.
