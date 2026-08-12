from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .ai import BitcoinAIRouter
from .runtime import env_values
from .production8 import Production8Ledger, Production8Orchestrator, load_production8_config
from .telegram.client import TelegramClient
from .telegram.setup import load_allowlist, run_setup

ROOT = Path(__file__).resolve().parents[2]


def _router(force_enabled: bool = False) -> BitcoinAIRouter:
    values = env_values(ROOT / ".env")
    if force_enabled:
        values["OPENAI_ENABLED"] = "true"
    return BitcoinAIRouter(values=values, cache_dir=ROOT / "runtime" / "ai_cache")


def _state() -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import bitcoin_intelligence
    return bitcoin_intelligence.state()[0]


def _ai_models():
    result = _router().discover_models()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "CONNECTED" or not all(result.get("selected_available", {}).values()):
        raise SystemExit(2)


def _ai_test():
    router = _router(force_enabled=True)
    models = router.discover_models()
    if models["status"] != "CONNECTED" or not all(models.get("selected_available", {}).values()):
        print(json.dumps({"api": models, "execution": "DISABLED"}, indent=2, ensure_ascii=False))
        raise SystemExit(2)
    state = _state()
    nano = router.explain("NANO", state, bypass_cache=True)
    analysis = router.explain("ANALYSIS", state, deep=True, bypass_cache=True)
    result = {
        "api": {"status": models["status"], "models_found": models["count"]},
        "nano": nano.to_dict(),
        "analysis": analysis.to_dict(),
        "totals": {
            "input_tokens": nano.input_tokens + analysis.input_tokens,
            "output_tokens": nano.output_tokens + analysis.output_tokens,
            "estimated_cost_usd": round(sum(x.estimated_cost_usd or 0 for x in (nano, analysis)), 8),
            "cache_hits": int(nano.cached) + int(analysis.cached),
        },
        "execution": "DISABLED",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if nano.status != "AVAILABLE" or analysis.status != "AVAILABLE":
        raise SystemExit(3)


def _production_state():
    return Production8Orchestrator.attach_engine_hashes(Production8Orchestrator.build(_state()),ROOT)


def _health():
    import requests
    state = _production_state(); live = state["live"]; confirmed = live["confirmed"]
    router = _router(); ai = router.health()
    heartbeat = ROOT / "runtime" / "production8" / "heartbeat.json"
    watcher = "OFFLINE"
    if heartbeat.exists():
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromtimestamp(heartbeat.stat().st_mtime, timezone.utc)).total_seconds()
        watcher = "ONLINE" if age <= 180 else "DEGRADED"
    try: dashboard = "ONLINE" if requests.get("http://localhost:8501/_stcore/health", timeout=3).ok else "DEGRADED"
    except Exception: dashboard = "OFFLINE"
    ledger = Production8Ledger(ROOT / "database" / "production8_forward.db", load_production8_config(ROOT)["forward_start"]).health()
    rows = {
        "MT5": live.get("status") or "OFFLINE", "BTC PRICE": live.get("price_status") or "OFFLINE",
        "H4": "FRESH" if confirmed.get("H4") else "UNAVAILABLE", "D1": "FRESH" if confirmed.get("D1") else "UNAVAILABLE",
        "W1": "FRESH" if confirmed.get("W1") else "UNAVAILABLE", "WATCHER": watcher,
        "OPENAI NANO": ai["discovery"], "OPENAI ANALYSIS": ai["discovery"], "EVENT DB": "ONLINE" if (ROOT / "database" / "historical_event_evidence.db").exists() else "OFFLINE",
        "FORWARD LEDGER": ledger["status"], "DASHBOARD": dashboard, "EXECUTION": "DISABLED",
    }
    healthy = all(rows[key] in {"ONLINE", "LIVE", "FRESH", "CONNECTED"} for key in ("MT5", "BTC PRICE", "H4", "D1", "W1", "WATCHER", "OPENAI NANO", "OPENAI ANALYSIS", "EVENT DB", "FORWARD LEDGER", "DASHBOARD"))
    print("BITCOIN INTELLIGENCE LIVE\n")
    for key, value in rows.items(): print(f"{key:<18}{value}")
    print(f"\nSYSTEM STATUS: {'HEALTHY' if healthy else 'DEGRADED'}")
    return 0 if healthy else 2


def _live_smoke():
    import requests
    state = _state(); production = Production8Orchestrator.attach_engine_hashes(Production8Orchestrator.build(state),ROOT); router = _router(force_enabled=True)
    nano = router.explain("NANO", state); analysis = router.explain("ANALYSIS", state, deep=True)
    second = router.explain("ANALYSIS", state, deep=True)
    ledger = Production8Ledger(ROOT / "database" / "production8_forward.db", load_production8_config(ROOT)["forward_start"])
    append = ledger.append(production)
    try: dashboard = requests.get("http://localhost:8501/_stcore/health", timeout=5).ok
    except Exception: dashboard = False
    checks = {
        "mt5": production["live"]["status"] == "ONLINE", "tick": production["live"]["price_status"] == "LIVE",
        "h4": bool(production["live"]["confirmed"]["H4"]), "d1": bool(production["live"]["confirmed"]["D1"]), "w1": bool(production["live"]["confirmed"]["W1"]),
        "engine": bool(production["decision"]), "production8": production["version"] == Production8Orchestrator.VERSION,
        "elliott": bool(production["elliott"]), "historical_entry": bool(production["historical"]),
        "ai_nano": nano.status == "AVAILABLE", "ai_analysis": analysis.status == "AVAILABLE",
        "guards": nano.contradiction_guard == analysis.contradiction_guard == "PASSED" and nano.hallucination_guard == analysis.hallucination_guard == "PASSED",
        "cache": second.cached, "ledger": append["status"] in {"APPENDED", "DEDUPLICATED", "SKIPPED_NO_CONFIRMED_D1", "SKIPPED_BEFORE_FORWARD_START"}, "dashboard": dashboard, "execution_disabled": production["execution"] == "DISABLED",
    }
    result = {"status": "PASS" if all(checks.values()) else "PARTIAL", "checks": checks, "live": production["live"], "decision": production["decision"], "ai": {"nano": nano.to_dict(), "analysis": analysis.to_dict(), "cache_second_call": second.cached}, "ledger": append, "execution": "DISABLED"}
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if all(checks.values()) else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("telegram-setup", "telegram-test", "ai-models", "ai-test", "health", "live-smoke"))
    args = parser.parse_args()
    allow_path = ROOT / "config" / "telegram_allowlist.json"
    if args.command == "ai-models": return _ai_models()
    if args.command == "ai-test": return _ai_test()
    if args.command == "health": raise SystemExit(_health())
    if args.command == "live-smoke": raise SystemExit(_live_smoke())
    if args.command == "telegram-setup":
        result = run_setup(allow_path)
        print(f"Telegram configured for {len(result['allowed_chat_ids'])} allowlisted chat(s). Token was not stored.")
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip(); allowed = sorted(load_allowlist(allow_path))
    if not token or not allowed: raise SystemExit("Run telegram-setup with TELEGRAM_BOT_TOKEN first")
    message = "₿ BITCOIN INTELLIGENCE\n\nTelegram verbunden.\n\nCONTROL 3: ONLINE\nSPECIALIST 5: ONLINE\nFUSION 6: SHADOW LIVE\nMT5: LIVE\n\nExecution: DISABLED"
    results = [TelegramClient(token, chat, enabled=True, dry_run=False).send(message) for chat in allowed]
    print(f"Telegram test delivered to {sum(bool(x.get('delivered')) for x in results)}/{len(results)} allowlisted chat(s).")


if __name__ == "__main__": main()
