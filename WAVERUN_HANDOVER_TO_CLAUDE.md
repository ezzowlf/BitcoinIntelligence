# WAVERUN handover to Claude

Updated UTC: 2026-09-06T21:11:29.446312+00:00
Branch: `codex/waverun-final-rebuild`
HEAD at last refresh: `6052c28d682cdeac489cf089d3711ced6764b038`. Always run `git rev-parse HEAD` for current HEAD (documentation commits may follow).
Base: `fd0319e07189ca04108d3b253372271f571d62ed`
Workspace: `C:\Users\djaez\.codex\worktrees\9b72\Bitcoin`
Python: `C:\Users\djaez\Documents\ChatGPT\Bitcoin\.venv\Scripts\python.exe`

**EXECUTION DISABLED. LOCAL GATE NOT REACHED. DO NOT DEPLOY. VPS NOT MODIFIED OR INSPECTED DURING REBUILD.**
Target from user: 207.180.245.205. Current VPS status NOT VERIFIED; rollback not applicable yet.

## Resume without redoing basic audit

Read WAVERUN_ASTRA_FINAL_REBUILD_REPORT.md, WAVERUN_REMEDIATION_DESIGN.md, docs/rebuild/findings-matrix.json and docs/rebuild/safety-probe-matrix.json. Binding full master attachment: C:\Users\djaez\.codex\attachments\9b87401a-5743-40e5-bba6-4980cbe948a6\pasted-text.txt. The user still wants the ENTIRE rebuild and gated deployment, not just this checkpoint.

Completed: immutable production audit; reviewed design; first tested journal/archive commit; 54 focused tests PASS including all original 11 failed probes. Formal findings closed: none at whole-system acceptance level. All 22 remain OPEN_ACCEPTANCE with detailed local implementation evidence in matrix. Last fully completed phase: verified lossless archive foundation (4 standalone cases PASS, real100k benchmark PASS). Current phase: resilience/outcomes/signal integration, incomplete and mostly uncommitted.

Implemented working changes: stable per-market feed owners, separate L2 transport, bounded callback/idle/retry handling, durable causal progress, no handshake event spoof, source-specific recovery, SQLite outcome/outbox and forecast mirror cursor, versioned shadow signal states, independent expiry/outcome scheduler, move-first labels with gap rejection, bounded raw writer and verified Parquet/ZSTD manifests. These still need integration acceptance; full list of defects/open work in report.

Known latest failed test rebuild-03 was source freshness budget misuse (53/1); fixed and rebuild-04 all54 PASS. Earlier tests failed Windows rb fsync and callback idle accounting; fixed. Current remaining known code issues: external restart consumer absent; sync supervisor/alerts; lifecycle sink exceptions; automatic retention/disk tiers absent; legacy outcome backlog/registration crash gaps; feature quote timestamp consistency; UI incomplete; full suite/causal replay/chaos coverage not yet run. Never promote focused PASS to local acceptance.

Evidence: docs/rebuild/ contains sanitized committed summaries/XML; ignored rebuild_artifacts/ has complete intermediate logs/sample benchmark data. Immutable audit originals and code clones in audit/; do NOT edit clones or regenerate audit report.

## Exact next commands (PowerShell)

```powershell
Set-Location 'C:\Users\djaez\.codex\worktrees\9b72\Bitcoin'
git branch --show-current
git rev-parse HEAD
git status --short
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TELEGRAM_ENABLED='false'
$env:MT5_ENABLED='false'
& 'C:\Users\djaez\Documents\ChatGPT\Bitcoin\.venv\Scripts\python.exe' -m pytest tests/test_waverun_archive.py tests/test_waverun_rebuild.py tests/test_independent.py tests/test_extended.py -q -p no:cacheprovider --basetemp=rebuild_artifacts/resume_tmp --junitxml=rebuild_artifacts/resume.xml --tb=short
```

Next implement external watchdog plus actual component restoration and source freshness integration; add adversarial process-level tests. Then full suite using fresh basetemp/JUnit before further release decisions. Preserve original negative controls under audit/parent and audit/candidate. Full replay inputs: `C:\Users\djaez\Documents\TAKEOFF\Exports\exports\WAVERUN_FULL_TRANSFER_20260906_132904`, especially 04_market_events_full/market_events.jsonl, 05_vantage/vantage_ticks.jsonl, 08_candidates_decisions and 03_databases. All read-only. Full raw27,812,107 rows already entrance-verified. Historical quality NOT REPRODUCIBLE. No winner optimization; frozen V5.3 and closed holdout untouched.

Commit only finished tested source units and reports; keep incomplete source on disk. Update report/matrices/handover after each phase. Never stage broad directories containing runtime/data/secrets. The Git common metadata is outside writable root, so approved git add/commit may need require_escalated. No push or VPS until applicable gates and master authorization steps.
