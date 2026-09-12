"""TAKEOFF soak sampler - passive, read-only, append-only observability.

Replaces the dead TAKEOFF-Soak-Sampler (last ran 2026-09-02). Records one
JSON line every ~10 minutes to samples.jsonl, plus a line to
reconnect_events.jsonl whenever a Binance feed's health state changes.

Read-only: never restarts services, never writes runtime/waverun/*.json,
never touches the collector. Safe to run indefinitely from a scheduled task.
Execution stays DISABLED (this script has no order/broker code path at all).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime" / "waverun"
DB = ROOT / "database" / "waverun_predictions.db"
OUT_DIR = ROOT / "ops" / "soak"
SAMPLES = OUT_DIR / "samples.jsonl"
RECONNECTS = OUT_DIR / "reconnect_events.jsonl"
STATE = OUT_DIR / "sampler_state.json"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _pid_uptime(pattern: str):
    """Read-only process lookup via WMIC-free PowerShell CIM query."""
    import subprocess

    cmd = (
        "Get-CimInstance Win32_Process -Filter \"CommandLine like '%" + pattern + "%'\" "
        "| Where-Object { $_.CommandLine -notlike '*sampler.py*' } "
        "| Select-Object -First 1 ProcessId,CreationDate "
        "| ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        if not out:
            return None, None
        row = json.loads(out)
        pid = row.get("ProcessId")
        created = row.get("CreationDate")
        if pid is None or created is None:
            return None, None
        # .NET JSON date: /Date(1699999999000)/
        if isinstance(created, str) and created.startswith("/Date("):
            epoch_ms = int(created[6:created.index(")")])
            uptime = time.time() - epoch_ms / 1000.0
        else:
            uptime = None
        return pid, uptime
    except Exception:  # noqa: BLE001 - the sampler must never crash the box
        return None, None


def _disk_free_gb():
    import shutil as _shutil

    try:
        return round(_shutil.disk_usage("C:\\").free / 1e9, 2)
    except OSError:
        return None


def _size_gb(path: Path):
    try:
        if path.is_dir():
            return round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e9, 3)
        return round(path.stat().st_size / 1e9, 3)
    except OSError:
        return None


def _feed_freshness():
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from bitcoin_cycle_analyzer.short_term.journal import Journal

        now = datetime.now(UTC).timestamp()
        markers = Journal.progress_at(str(RUNTIME / "journal.db"))
        out = {}
        for key in ("feed_spot", "feed_futures", "feed_l2", "vantage", "decisions", "outcome_scheduler", "storage"):
            m = markers.get(key)
            out[key] = round(now - m["committed_at"], 1) if m else None
        return out
    except Exception:  # noqa: BLE001
        return {}


def _exception_count():
    try:
        sys.path.insert(0, str(ROOT / "src"))
        import sqlite3 as _sqlite3

        db = _sqlite3.connect(f"file:{RUNTIME / 'journal.db'}?mode=ro", uri=True, timeout=2)
        db.execute("PRAGMA query_only=1")
        return db.execute("SELECT COUNT(*) FROM events WHERE kind='incident'").fetchone()[0]
    except Exception:  # noqa: BLE001
        return None


def sample():
    now = datetime.now(UTC).isoformat()
    collector_pid, collector_uptime = _pid_uptime("waverun_live.py")
    api_pid, api_uptime = _pid_uptime("waverun_web_api.py")
    web_pid, web_uptime = _pid_uptime("http.server 8878")

    health = _read_json(RUNTIME / "health.json") or {}
    storage = _read_json(RUNTIME / "storage_health.json") or {}
    sig = _read_json(RUNTIME / "signal.json") or {}

    predictions_gb = _size_gb(DB)
    journal_gb = _size_gb(RUNTIME / "journal.db")
    raw_gb = _size_gb(RUNTIME / "raw")

    row = {
        "timestamp": now,
        "collector": {"pid": collector_pid, "uptime_seconds": round(collector_uptime, 1) if collector_uptime else None},
        "api": {"pid": api_pid, "uptime_seconds": round(api_uptime, 1) if api_uptime else None},
        "web": {"pid": web_pid, "uptime_seconds": round(web_uptime, 1) if web_uptime else None},
        "disk_free_gb": _disk_free_gb(),
        "journal_db_gb": journal_gb,
        "predictions_db_gb": predictions_gb,
        "raw_dir_gb": raw_gb,
        "feed_freshness_seconds": _feed_freshness(),
        "operating_state": health.get("operating_state"),
        "storage_tier": storage.get("tier"),
        "new_signals_allowed": storage.get("new_signals_allowed"),
        "signal_last_setup_state": (sig.get("setup") or {}).get("state") if isinstance(sig.get("setup"), dict) else None,
        "incident_count_cumulative": _exception_count(),
        "execution": "DISABLED",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SAMPLES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")

    # reconnect-event detection: diff feed component state vs last sample
    prev = _read_json(STATE) or {}
    comps = health.get("components", {}) or {}
    cur_states = {k: (comps.get(k) or {}).get("state") for k in ("binance_spot", "binance_futures", "l2", "vantage")}
    for key, state in cur_states.items():
        if prev.get(key) is not None and prev.get(key) != state:
            with RECONNECTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": now, "component": key,
                    "from": prev.get(key), "to": state, "execution": "DISABLED",
                }, sort_keys=True) + "\n")
    STATE.write_text(json.dumps(cur_states))


if __name__ == "__main__":
    sample()
