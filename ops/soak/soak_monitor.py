"""WAVERUN independent soak safety monitor (Phase 24).

Runs as its own OS-level process (scheduled task), completely independent of the
market-event pipeline and even of the in-process HealthSupervisor. Every cycle it
checks:

  * TAKEOFF-Collector / TAKEOFF-API services alive
  * API /api/health reachable
  * the in-process supervisor is alive (runtime/waverun/health.json fresh)
  * Vantage / Spot / Futures / decision-pipeline / prediction-persistence freshness
  * disk space

On a critical condition it (1) records an incident, (2) raises a deduplicated
alert, (3) if the in-process supervisor itself looks dead it writes
runtime/waverun/restart_request.json so the collector is restarted in a
controlled way, (4) re-checks and persists the verification result. It never
waits days: a critical state is acted on within one cycle.

No secrets are logged. Execution stays DISABLED.

Usage:  python ops/soak/soak_monitor.py --once
        python ops/soak/soak_monitor.py            (loop, interval from config)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.alerting import (  # noqa: E402
    CRITICAL,
    CRITICAL_ALERT,
    DEGRADED,
    HIGH,
    WARNING,
    AlertManager,
    telegram_config_state,
)
from bitcoin_cycle_analyzer.short_term.incident_log import IncidentLog  # noqa: E402
from bitcoin_cycle_analyzer.short_term.resilience import CONFIG, age_seconds  # noqa: E402

RUNTIME = ROOT / "runtime" / "waverun"
DB = ROOT / "database" / "waverun_predictions.db"
API_HEALTH = "http://127.0.0.1:8877/api/health"
MONITOR_LOG = ROOT / "ops" / "soak" / "monitor.jsonl"


def _svc_running(name: str) -> bool | None:
    try:
        out = subprocess.run(["sc", "query", name], capture_output=True, text=True, timeout=10)
        return "RUNNING" in out.stdout
    except Exception:  # noqa: BLE001
        return None


def _http_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=6) as r:  # noqa: S310 - fixed localhost URL
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _last_jsonl_ts(path: Path) -> str | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if not size:
        return None
    with path.open("rb") as h:
        h.seek(max(0, size - 65536))
        chunk = h.read()
    for line in reversed(chunk.split(b"\n")):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        return str(row.get("received_timestamp") or row.get("timestamp") or "")
    return None


def check() -> dict:
    now = datetime.now(UTC)
    health = {}
    try:
        health = json.loads((RUNTIME / "health.json").read_text())
    except Exception:  # noqa: BLE001
        health = {}
    supervisor_age = age_seconds(health.get("server_time"), now)
    supervisor_alive = supervisor_age is not None and supervisor_age <= max(30.0, CONFIG.supervisor_interval * 6)

    market_age = age_seconds(_last_jsonl_ts(RUNTIME / "market_events.jsonl"), now)
    decision_age = age_seconds(_last_jsonl_ts(RUNTIME / "decision_records.jsonl"), now)
    candidate_age = age_seconds(_last_jsonl_ts(RUNTIME / "pre_gate_candidates.jsonl"), now)
    vantage_age = age_seconds(_last_jsonl_ts(RUNTIME / "vantage_ticks.jsonl"), now)
    try:
        pred_age = max(0.0, time.time() - DB.stat().st_mtime)
    except OSError:
        pred_age = None
    try:
        disk_free_gb = shutil.disk_usage(str(RUNTIME)).free / 1e9
    except OSError:
        disk_free_gb = None

    report = {
        "timestamp": now.isoformat(),
        "collector_service": _svc_running("TAKEOFF-Collector"),
        "api_service": _svc_running("TAKEOFF-API"),
        "api_health_ok": _http_ok(API_HEALTH),
        "supervisor_alive": supervisor_alive,
        "supervisor_report_age_s": supervisor_age,
        "operating_state": health.get("operating_state"),
        "vantage_age_s": vantage_age,
        "market_event_age_s": market_age,
        "decision_age_s": decision_age,
        "candidate_age_s": candidate_age,
        "prediction_age_s": pred_age,
        "disk_free_gb": None if disk_free_gb is None else round(disk_free_gb, 1),
        "execution": "DISABLED",
    }

    # Distinguish "quiet market" (feeds fresh, pipeline advancing) from a real
    # unnoticed pipeline freeze: only a stall while market events are fresh counts.
    market_fresh = market_age is not None and market_age <= CONFIG.feed_offline_after
    pipeline_frozen = (
        market_fresh
        and decision_age is not None
        and decision_age > CONFIG.decision_offline_after
    )
    critical = (
        report["api_health_ok"] is False
        or report["collector_service"] is False
        or (vantage_age is not None and vantage_age > CONFIG.feed_offline_after and market_age is not None and market_age > CONFIG.feed_offline_after)
        or pipeline_frozen
        or (disk_free_gb is not None and disk_free_gb < CONFIG.disk_min_free_gb)
        or not supervisor_alive
    )
    report["critical"] = bool(critical)
    report["pipeline_frozen"] = bool(pipeline_frozen)
    return report


def act(report: dict, incidents: IncidentLog, alerts: AlertManager) -> None:
    if not report["critical"]:
        alerts.resolve(component="soak_monitor", kind=DEGRADED,
                       message="Soak monitor: all critical checks healthy again.",
                       detail={"operating_state": report.get("operating_state")})
        return

    reasons = []
    if report["api_health_ok"] is False:
        reasons.append("api_health_unreachable")
    if report["collector_service"] is False:
        reasons.append("collector_service_not_running")
    if report["pipeline_frozen"]:
        reasons.append(f"decision_pipeline_frozen_{report['decision_age_s']:.0f}s_while_market_fresh")
    if not report["supervisor_alive"]:
        reasons.append("in_process_supervisor_stale")
    if report["disk_free_gb"] is not None and report["disk_free_gb"] < CONFIG.disk_min_free_gb:
        reasons.append(f"disk_low_{report['disk_free_gb']}gb")

    incidents.record(
        component="soak_monitor", previous_state="OK", new_state="CRITICAL",
        reason="; ".join(reasons) or "critical", last_event_age=report.get("decision_age_s"),
        recovery_action="alert + (restart_request if supervisor stale)",
        operating_state=report.get("operating_state"),
    )
    alerts.notify(
        component="soak_monitor", kind=CRITICAL_ALERT, severity=CRITICAL,
        message="WAVERUN soak monitor detected a critical condition.",
        detail={"reasons": reasons, "operating_state": report.get("operating_state"),
                "decision_age_s": report.get("decision_age_s"),
                "recovery_action": "controlled restart request" if not report["supervisor_alive"] or report["pipeline_frozen"] else "monitoring"},
    )
    # If the in-process supervisor is stale OR the pipeline is frozen with a live
    # supervisor that failed to fix it, request a controlled collector restart.
    if (not report["supervisor_alive"]) or report["pipeline_frozen"]:
        payload = {"timestamp": report["timestamp"], "reason": "soak_monitor: " + "; ".join(reasons),
                   "source": "soak_monitor", "execution": "DISABLED"}
        try:
            (RUNTIME / "restart_request.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=float, default=30.0)
    args = p.parse_args()

    MONITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    incidents = IncidentLog(RUNTIME / "incidents.jsonl")
    alerts = AlertManager(RUNTIME / "alerts.jsonl", incident_log=incidents)
    print(f"soak_monitor telegram={telegram_config_state()} interval={args.interval}s", flush=True)

    while True:
        report = check()
        try:
            with MONITOR_LOG.open("a", encoding="utf-8") as h:
                h.write(json.dumps(report, default=str) + "\n")
        except OSError:
            pass
        try:
            act(report, incidents, alerts)
        except Exception as exc:  # noqa: BLE001
            print(f"soak_monitor act() error: {type(exc).__name__}", flush=True)
        if args.once:
            print(json.dumps(report, indent=2, default=str))
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
