from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import bitcoin_intelligence
from bitcoin_cycle_analyzer.production8 import ProcessLock, Production8Ledger, Production8Orchestrator, load_production8_config, verify_underlying_frozen

FORWARD_START = load_production8_config(ROOT)["forward_start"]


def run_once() -> dict:
    verify_underlying_frozen(ROOT)
    state, _ = bitcoin_intelligence.state()
    production = Production8Orchestrator.attach_engine_hashes(Production8Orchestrator.build(state),ROOT)
    ledger = Production8Ledger(ROOT / "database" / "production8_forward.db", FORWARD_START)
    append = ledger.append_safe(production)
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "ONLINE", "append": append, "ledger": ledger.health(), "state_hash": production["state_hash"], "execution": "DISABLED"}
    runtime = ROOT / "runtime" / "production8"; runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "heartbeat.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--watch", action="store_true"); parser.add_argument("--interval", type=int, default=60); args = parser.parse_args()
    runtime = ROOT / "runtime" / "production8"; runtime.mkdir(parents=True, exist_ok=True)
    lock = ProcessLock(runtime / "watcher.lock")
    if not lock.acquire(): print(json.dumps({"status":"ALREADY_RUNNING","execution":"DISABLED"})); return
    try:
        while True:
            try:
                result = run_once()
            except Exception as exc:
                result = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "DEGRADED", "error_class": type(exc).__name__, "execution": "DISABLED"}
                (runtime / "heartbeat.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            with (runtime / "watcher.jsonl").open("a", encoding="utf-8") as handle: handle.write(json.dumps(result, default=str) + "\n")
            print(json.dumps(result, default=str), flush=True)
            if not args.watch: break
            time.sleep(max(30,args.interval))
    finally: lock.release()


if __name__ == "__main__": main()
