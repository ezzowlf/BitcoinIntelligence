# Bitcoin Intelligence VPS Live Deployment Report

Date: 2026-08-09

## Deployment status

- Local source: `C:\Users\djaez\Documents\ChatGPT\Bitcoin`
- Source commit: `f90e688fa30cf4e3c99d3bf447d82c8d51629eef`
- Branch: `codex/bitcoin-master-3`
- Intended VPS target: `C:\BitcoinIntelligence`
- Code layout: `C:\BitcoinIntelligence\app` because the existing application expects its project root around `config.yaml`, `database`, `frozen`, scripts and dashboard assets
- Transfer method: **UNAVAILABLE / NOT CONFIRMED**
- VPS filesystem inventory: **NOT EXECUTED**
- Deployment status: **DEPLOYMENT_PACKAGE_READY**
- VPS deployment: **NOT EXECUTED**
- GitHub: **NOT CONFIGURED**; no remote added and nothing pushed

No SSH configuration, Remote PowerShell session, mounted VPS filesystem, or VPS-related environment configuration was available on the local machine. Therefore `C:\BitcoinIntelligence` was neither inspected nor created.

## Deployment package

- Package: `deployment_artifacts\bitcoin-intelligence-master-3-f90e688.zip`
- SHA-256: `9E8AC0247700D2F13FAEA894156953A88DB21DD9CBC8B0BD5F2BA7370C4EAD81`
- `DEPLOYED_VERSION.json`: included
- Public canonical databases: `bitcoin.db` and `external_metrics.db` included for initial offline smoke
- Excluded: `.env`, `.git`, `.venv`, `.runtime`, forward ledger, logs, caches and installer EXE
- Credential-pattern scan: clean; reviewed matches were a dataclass assignment and a synthetic test chat ID only

The first package attempts were discarded after extracted-package validation exposed line-ending-sensitive hashes and UTF-8-BOM handling. The final package uses canonical LF hashes and BOM-free deployment metadata.

## Validation of the extracted final package

- Tests: **146 passed**
- MASTER/Reference startup verification: passed
- Shadow startup: passed in `DRY_RUN`
- Health: `ONLINE`, append-only, Execution `DISABLED`
- Dashboard: HTTP **200**
- Forbidden deployment files: none
- Telegram live connection: not attempted because no VPS credentials or confirmed chat were available
- Telegram state: `DRY_RUN`
- First forward snapshot: not created; the package verification does not mutate forward state

## Runtime preparation

- Required VPS runtime: official 64-bit CPython, isolated `C:\BitcoinIntelligence\.venv`
- Pinned dependencies: `requirements-vps.lock`
- Project `.env`: loaded locally by the runtime but never included in the package
- Execution hard lock: `EXECUTION` must equal `DISABLED`; `BITCOIN_EXECUTION_ENABLED=true` raises a hard runtime error; no order adapter exists
- Candidate alerts default: false
- Unauthorized Telegram chat IDs: ignored
- `/history`: allowed by the live poller
- Version fallback: runtime uses `DEPLOYED_VERSION.json`; Git is not required on the VPS

## Scheduler package

Prepared task definitions, not registered:

- `BitcoinIntelligence-H4`: every four hours
- `BitcoinIntelligence-Daily`: 00:15
- `BitcoinIntelligence-Telegram`: every minute
- `BitcoinIntelligence-Price`: hourly
- `BitcoinIntelligence-Providers`: every six hours
- `BitcoinIntelligence-Health`: every 15 minutes
- `BitcoinIntelligence-Backup`: daily 01:00
- `BitcoinIntelligence-Startup`: after boot, dry-run-safe and no startup BUY/SELL event
- `BitcoinIntelligence-Dashboard`: after boot, localhost `127.0.0.1:8501`

The installer refuses to overwrite existing task names and refuses a non-empty target without the Bitcoin Intelligence ownership marker. It no longer uses `robocopy /MIR`.

## Backup, logging and watchdog preparation

- Backup policy: daily 7, weekly 4, monthly 6
- Backup contents: forward ledger, config, deployed version, control/master/reference freezes; no `.env`
- Audit log: JSONL with size rotation
- Health task: prepared every 15 minutes
- Actual VPS task state, restart behavior, CPU/RAM/disk usage and backup filesystem output: **NOT VERIFIED**

## Current local MASTER evidence

- BTC source close: `$64,877.77` at 2026-08-07
- Long-Term / New Entry / Existing Position: `ACCUMULATE / ACCUMULATE / HOLD`
- Risk / Timing: `CAUTION / WAIT`
- Production: `NO_PRODUCTION_SIGNAL`
- Buy / Sell Candidate: `50.0% / 16.7%` completion, not probability
- Historical Entry Quality: `MODERATE`, 49/100
- Archetype: `HISTORICAL_SUPPORT_RETEST`
- Major Support: `$55,244.90-$60,864.85`
- Major Resistance: `$67,696.10-$80,327.60`
- Drawdown / Weekly RSI: `-47.98% / 41.56`
- Production SELL: rejected historical proxy cannot trigger production
- Execution: `DISABLED`

These are local source values, not a VPS smoke result.

## Forward and providers

- Forward start remains `2026-08-10T00:00:00Z`; no deployment research changed it
- Forward snapshot count in clean package runtime: 0
- Alert baseline: not activated on VPS
- Available locally: price, Coin Metrics on-chain, funding and OI
- Unavailable without external configuration/license: FRED macro, ETF PIT feed and MeanPulse news

## Required next step on the actual VPS

Transfer the ZIP through the already established administration channel, verify its SHA-256, extract to a temporary staging folder, run `deploy\preflight_vps.ps1`, review the inventory, and only then run `install_vps.ps1 -InventoryConfirmed`. Telegram must remain dry-run until all command smokes pass; exactly one neutral live status message may then be sent. Do not create `C:\BitcoinIntelligence` until the preflight confirms it is unused.

Working tree at package creation was clean. No remote exists, no push occurred, no VPS files were changed, no scheduled task was registered, and no Telegram message was sent.
