# TAKEOFF — CONTROLLED VPS LIVE DEPLOYMENT RUNBOOK

Execute only after `FAST LOCAL GATE ACCEPTED`. Target `207.180.245.205`.
`AUTOMATIC TRADE EXECUTION = DISABLED` throughout. Do not touch the separate WAVERUN Elliott-Wave project.
Run every step in order; stop at the first ABORT / ROLLBACK condition.

Set once:
- `LOCAL_ACCEPTED_HEAD` = output of `git -C <worktree> rev-parse HEAD` on the accepted commit (branch `codex/waverun-final-rebuild`).

---

## 1. PRE-DEPLOY READ-ONLY CHECK  (change nothing)

Record: hostname; every TAKEOFF service state (collector, API, web, watchdog/supervisor, outcome, archiver);
deployed git HEAD + branch + `git status`; configured service paths; API/web ports; env keys present
(names only, NO values); free disk; `tailscale status` (IP, MagicDNS, tailnet); TAKEOFF data/db/archive
paths; latest timestamps + row counts for feeds / candidates / decisions / predictions / outcomes.

Prove execution disabled: `WAVERUN_EXECUTION` / `.env` / service env = DISABLED; no order path in the
deployed code; NSSM/service args carry no execute flag.
- If execution cannot be conclusively proven disabled -> **ABORT DEPLOYMENT.**

## 2. ROLLBACK POINT

- `PRE_DEPLOY_HEAD` = current deployed commit (record it).
- Timestamped backup of: TAKEOFF app dir + config + service definitions (NSSM/scheduled task export)
  + required env (stored securely, not printed).
- Preserve (do NOT overwrite, do NOT duplicate the large market-event archive if an existing verified
  export already protects it): production DBs, market/event data, signal/outcome history.
- Write down the exact rollback commands (service stop -> `git checkout $PRE_DEPLOY_HEAD` -> reinstall
  deps if changed -> service start -> verify).

## 3. VERIFY RELEASE IDENTITY

- Fetch/checkout the exact accepted commit on the VPS: `DEPLOY_TARGET_HEAD`.
- Assert `DEPLOY_TARGET_HEAD == LOCAL_ACCEPTED_HEAD`. If not -> **ABORT.** Do not deploy a dirty tree;
  do not merge unrelated branches.

## 4. CONTROLLED SERVICE STOP

Stop only TAKEOFF's own services. Let the raw writer / archiver flush (SIGTERM, wait for
`writer_health.json` ready + queue drain, up to the writer close timeout). Record final pre-stop
progression timestamps (feeds/candidates/decisions/predictions/outcomes).

## 5. DEPLOY ACCEPTED RELEASE

Move code to `DEPLOY_TARGET_HEAD`. Preserve production data / DBs / archives / env / Tailscale config /
service identity. Recreate the venv only if `pyproject.toml`/lock changed; install from metadata.
Apply any migrations explicitly. **Never** copy local test DBs or fixtures into production paths.

## 6. START IN DEPENDENCY ORDER

`watchdog/process owner` -> `collector` -> `outcome scheduler` (in-process) -> `API` -> `web`.
After each: confirm the process is up AND doing work (not just "Running"):
- collector: new `market_events` raw segment + `journal.db` `progress` rows advancing;
- supervisor: fresh `runtime/waverun/health.json` with current `server_time` and matching `boot_id`;
- API: `/api/state` returns and `health.operating_state` present;
- web: page loads, reads live API.

## 7. PROVE REAL LIVE DATA PROGRESSION  (new post-deploy timestamps only)

Show each stage advanced AFTER the Step-6 start time:
`Vantage + Binance Spot + Binance Futures + L2`
-> Features (`journal` stage `features` seq++)
-> Candidates (`pre_gate_candidates.jsonl` + stage `candidates`)
-> Decisions (`decision_records.jsonl` + stage `decisions`)
-> Predictions (`waverun_predictions.db` new rows + stage `predictions`)
-> PREWARNING / ARMED / LIVE **only if conditions qualify** (`signal.json` / journal `signal_transition`) — zero is acceptable; candidate evaluation MUST be visibly running
-> Outcome Scheduler (stage `outcome_scheduler` committed_at advancing)
-> Outcome Persistence (`observation_outcomes` / journal `outcome` rows; NULL-outcome rate not growing)
-> Storage / Archive (`.parquet` + `.manifest.json` with `verification: VERIFIED_ARCHIVE`; `storage_health.json` tier OK)
-> API / Dashboard reflect the above.
A fresh price alone is NOT proof.

## 8. HEALTH / FALSE-LIVE ACCEPTANCE

Confirm `overall` is NOT `LIVE` unless the required pipeline is fresh AND progressing (not merely
Vantage fresh). If safe, induce one controlled degraded condition (e.g. block the spot L2 stream
briefly) and confirm `FULL_LIVE -> DEGRADED/RECOVERING -> FULL_LIVE`, with RECOVERED only after real
downstream progression resumes. Then restore.

## 9. TAILSCALE  (mandatory)

Verify: tailscale service up; correct tailnet; IP / MagicDNS; Windows Firewall allows the TAKEOFF
listener on the tailnet; API health + web + live dashboard reachable over the tailnet; test from a
second tailnet device if available. Do NOT expose TAKEOFF to the public internet as a workaround.
Required: `TAILSCALE ACCESS VERIFIED`.

## 10. LIVE SIGNAL ENGINE

Confirm production runs the real engine (`signal.json` `mode: LIVE`, `execution: DISABLED`),
state model `OBSERVING -> CANDIDATE -> PREWARNING -> ARMED -> LIVE -> OUTCOME` active, candidates
being evaluated. Do NOT manufacture a LIVE signal for verification.

## 11. EXECUTION SAFETY  (hard)

Re-verify after everything is running: code/config, service env, and any broker/order path all show
automatic execution DISABLED. Signal generation ENABLED, automatic trading DISABLED.

## 12. IMMEDIATE POST-DEPLOY SOAK

Short stabilization window — prove: feeds keep advancing; pipeline keeps advancing; no restart loop
(`watchdog.db` restart rows not climbing); no accumulating fatal errors; storage + archive continue;
API + dashboard responsive; Tailscale reachable; watchdog healthy; disk sane. Then leave TAKEOFF
running continuously. The 24h soak + full 27.8M replay continue afterward and do not block sign-off.

## 13. ROLLBACK CONDITIONS (any -> roll back first, diagnose after)

service crash/restart loop · feed pipeline freeze · candidate/decision/prediction progression stops ·
FALSE-LIVE · outcome persistence failure · corrupt DB/storage · critical archive/storage failure ·
`DEPLOY_TARGET_HEAD` not reproducible on VPS · execution cannot be proven disabled · severe
regression vs pre-deploy. (Tailscale-only failure with TAKEOFF healthy = access-layer fix, not a
code rollback.)

## FINAL REPORT — return exact values

deployed HEAD · service states · uptime/restarts · Vantage/Spot/Futures/L2 freshness ·
latest Candidate / Decision / Prediction ts · Outcome Scheduler state · latest resolved Outcome ·
storage/archive state · disk · API health · dashboard health · Tailscale access · automatic execution
state · rollback point (`PRE_DEPLOY_HEAD`) · unresolved warnings.

Verdict (only if all required pass):
`TAKEOFF PRODUCTION ACCEPTED — LIVE SIGNAL ENGINE RUNNING — TAILSCALE ACCESS VERIFIED — AUTOMATIC EXECUTION DISABLED`
else `TAKEOFF PRODUCTION REJECTED` or `TAKEOFF ROLLED BACK` + the exact failed gate.
