# Bitcoin Intelligence 2.4 VPS Shadow Deployment Report

Date: 2026-08-09

## Release and frozen model

- 2.4 baseline commit: `7ad58e2`
- Branch: `codex/decision-telegram-forward`
- Champion: `2.3-FROZEN`
- Frozen semantic config hash: `db4b6ed6e40fd9f6ce7efe4b0748c61dee83ddcf0603962eb836eeafa8e3ee5f` (verified)
- Research cutoff: `2026-08-07T00:00:00Z`
- Forward start: `2026-08-10T00:00:00Z`
- Execution: `DISABLED`

No frozen analysis rule, threshold, weight, evidence rule or zone rule was changed by the deployment layer. No new market observation was downloaded during deployment preparation, so the conservative forward start remains unchanged.

## Runtime layout and dependencies

Prepared Windows VPS root: `C:\BitcoinIntelligence` with `app`, `data`, `logs`, `snapshots`, `forward`, `config` and `backups`. All runtime locations can be overridden through environment variables. The installer excludes `.env`, Git metadata, local virtual environments, databases and local runtime output.

- Verified development runtime: Python 3.13.15
- VPS environment: isolated `.venv`
- Dependency lock: `requirements-vps.lock`
- Installer: `deploy/install_vps.ps1`

## Scheduled operation

The installer prepares SYSTEM Task Scheduler jobs for:

- startup after reboot;
- Telegram command polling every minute;
- price refresh hourly;
- external-provider refresh every six hours;
- confirmed H4 analysis every four hours;
- confirmed Daily analysis at 00:15;
- backup at 01:00.

The task definitions were prepared and locally inspected, but were not registered on an actual VPS because no VPS connection is available in this environment. Reboot survival is therefore not remotely verified.

## Telegram

Commands implemented: `/btc`, `/decision`, `/value`, `/timing`, `/risk`, `/cycle`, `/zones`, `/why`, `/health`.

Security controls:

- only the configured chat ID is accepted;
- absent credentials force dry-run automatically;
- limited delivery retry (three attempts);
- persistent cross-restart event deduplication;
- no token, key, path or exception detail is included in messages;
- every confirmed alert is recorded with ID, time, type, message hash, market state, BTC price, decision, model and delivery status;
- `EXECUTION=DISABLED` is a runtime invariant.

Dry-run matrix passed for ACCUMULATE, BUY, STRONG_BUY, WAIT, REDUCE, SELL, BUY ZONE, INVALIDATION, REGIME, CAPITULATION and DATA WARNING. Invalidation explicitly does not imply SELL.

Exactly one logical Telegram connection test was attempted. It was not delivered after the bounded retry sequence. Non-sending `getMe`/`getChat` diagnostics returned HTTP 404, proving the configured bot token is invalid or no longer recognized. Live alerts remain disabled; no market-decision message was sent.

## Alert types

Implemented state detection covers decision, timing, risk, confirmed regime, capitulation, critical data quality, first buy-zone entry and invalidation. Initial state produces no market alert. Preview candles are labelled `PREVIEW` and are not persisted as confirmed decision alerts.

## Forward ledger and outcomes

Frozen snapshots and alerts remain append-only. Database triggers reject update/delete. Snapshot timestamps before the forward start are rejected. Alert deduplication reads the ledger, so restart does not resend the same event.

Current source close remains 2026-08-07 and is not forward-eligible. Consequently no first forward snapshot was created. Outcome tables remain separate from immutable source snapshots. Automated outcome maturation and forward-performance dashboard aggregation remain future work; they cannot produce evidence before horizons mature.

## Current real analysis

| Field | Result |
|---|---:|
| BTC | $64,877.77 |
| Long-Term | ACCUMULATE |
| Swing | WAIT |
| Risk | CAUTION |
| Confidence | MODERATE |
| Buy zone 1 | $63,176.58-$64,752.82 |
| Buy zone 2 | $61,243.72-$62,493.90 |
| Invalidation | below $61,243.72 |

## Health, backup and logging

Local shadow smoke verified health-file generation, H4 execution, frozen-hash startup protection, SQLite access, audit logging, 5 MB audit rotation and a backup containing ledger, config and frozen registration. Daily backup retention is seven copies. No secrets are copied into backups.

Current providers: price, on-chain, derivatives and seasonality available; macro, ETF and news unavailable. Optional missing providers reduce confidence and do not get simulated.

## Validation and deployment status

- Full suite before infrastructure work: 73 passed
- Full suite after infrastructure work: 80 passed
- Python compile: passed
- Git diff check: passed
- Dashboard HTTP smoke: 200
- Frozen hash: exact match
- Secrets scan: clean
- Telegram dry-run matrix: passed
- Telegram real connection test: **failed, not delivered (HTTP 404 token endpoint)**
- Actual VPS install: **not performed; no verified VPS connection**
- Task registration/reboot proof: **blocked by missing VPS access**
- Push: not performed

The code is production-shadow ready, but production is not live until a valid Telegram token and actual VPS access are supplied and the installed scheduler, logs, backup and reboot behavior are verified on that host.
