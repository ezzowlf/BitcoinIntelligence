from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


def state_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


class Production8Orchestrator:
    """Domain router over frozen engines; never averages or overrides them."""

    VERSION = "BITCOIN_INTELLIGENCE_PRODUCTION_8_0"

    @staticmethod
    def build(engine_state: dict[str, Any]) -> dict[str, Any]:
        master = engine_state["master"]
        macro7 = engine_state["macro7"]
        specialist = engine_state["master5_challenger"]
        fusion = engine_state["fusion6"]
        historical = engine_state["historical_entry_quality"]
        live = engine_state["live_market"]
        tick = live.get("tick") or {}
        decision = master["decision"]
        actions = macro7["actions"]
        payload = {
            "version": Production8Orchestrator.VERSION,
            "as_of": str(engine_state.get("timestamp")),
            "live": {
                "status": live.get("status"), "price_status": tick.get("freshness", "OFFLINE"),
                "bid": tick.get("bid"), "ask": tick.get("ask"), "mid": tick.get("mid"), "spread": tick.get("spread"),
                "tick_timestamp": tick.get("timestamp"), "tick_age_seconds": tick.get("age_seconds"),
                "symbol": tick.get("symbol"), "health": live.get("health"), "provenance": live.get("provenance"),
                "confirmed": {"H4": live.get("last_confirmed_h4"), "D1": live.get("last_confirmed_d1"), "W1": live.get("last_confirmed_w1"), "1M": live.get("last_confirmed_1m")},
            },
            "decision": {
                "macro": actions.get("macro"), "long_swing": actions.get("long_swing"), "medium_swing": actions.get("medium_swing"),
                "timing": actions.get("tactical_timing"), "existing_position": decision.get("existing_position_action"), "risk": actions.get("risk"),
                "production_signal": decision.get("production_signal"), "headline": Production8Orchestrator._headline(actions),
            },
            "cycle": macro7.get("cycle"),
            "elliott": macro7.get("elliott"),
            "price_map": {"zones": macro7.get("zones"), "scenarios": macro7.get("scenarios"), "ladder": macro7.get("drawdown_ladder")},
            "historical": historical,
            "specialist": {"buy": specialist.get("buy"), "risk": specialist.get("risk")},
            "pattern_research": {key: fusion.get(key) for key in ("regime", "decision", "active_historical_patterns", "status")},
            "waiting_for": macro7.get("waiting_for"), "why": macro7.get("why"),
            "data_status": engine_state.get("data_status"),
            "domain_owners": {"macro_cycle": "MACRO_SWING_7", "baseline": "CONTROL_3", "rare_distribution": "SPECIALIST_5", "patterns": "FUSION_6", "historical_entry": "HISTORICAL_ENTRY", "live_market": "MT5", "explanation": "OPENAI_GROUNDED"},
            "execution": "DISABLED",
        }
        payload["ai_state_hash"] = Production8Orchestrator.ai_state_hash(engine_state)
        payload["config_hash"] = (engine_state.get("precision") or {}).get("config_hash")
        payload["state_hash"] = Production8Orchestrator.rehash(payload)
        return payload

    @staticmethod
    def ai_state_hash(engine_state: dict[str, Any]) -> str:
        from bitcoin_cycle_analyzer.ai import BitcoinAIRouter
        grounded=BitcoinAIRouter.grounded_state(engine_state);grounded.get("live_market",{}).pop("tick",None)
        return state_hash(grounded)

    @staticmethod
    def rehash(payload: dict[str, Any]) -> str:
        hash_payload = deepcopy({key: value for key, value in payload.items() if key not in {"as_of", "state_hash"}})
        for key in ("bid", "ask", "mid", "spread", "tick_timestamp", "tick_age_seconds"): hash_payload["live"].pop(key, None)
        return state_hash(hash_payload)

    @staticmethod
    def attach_engine_hashes(payload: dict[str, Any], root: Path) -> dict[str, Any]:
        frozen=Path(root)/"frozen";payload["engine_hashes"]={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in {
            "MASTER3":frozen/"master_3_0_frozen.json","MASTER5":frozen/"master_5_0_challenger_frozen.json","FUSION6":frozen/"fusion_6_research_frozen.json","MACRO7":frozen/"macro_swing_7_0_research_frozen.json"}.items()}
        payload["state_hash"]=Production8Orchestrator.rehash(payload);return payload

    @staticmethod
    def _headline(actions: dict[str, Any]) -> str:
        if actions.get("macro") == "ACCUMULATE" and actions.get("long_swing") == "WAIT":
            return "Langfristig interessant, aber noch kein bestätigter Swing-Einstieg."
        if actions.get("risk") in {"HIGH", "REDUCE", "EXIT"}:
            return "Risiko erhöht; bestätigte Struktur und Invalidationen beachten."
        return "Bitcoin wird beobachtet; bestätigte Signale stehen aus."


class Production8Ledger:
    def __init__(self, path: Path, forward_start: str):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.forward_start = forward_start; self.initialization_error = None
        try:
            with sqlite3.connect(self.path) as db:
                db.executescript("""
            CREATE TABLE IF NOT EXISTS production8_snapshots(
              id TEXT PRIMARY KEY, confirmed_d1 TEXT NOT NULL UNIQUE, state_hash TEXT NOT NULL,
              marker TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS production8_no_update BEFORE UPDATE ON production8_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS production8_no_delete BEFORE DELETE ON production8_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
            """)
        except sqlite3.DatabaseError as exc: self.initialization_error = type(exc).__name__

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.initialization_error: raise sqlite3.DatabaseError(self.initialization_error)
        confirmed = payload["live"]["confirmed"].get("D1")
        if not confirmed: return {"status": "SKIPPED_NO_CONFIRMED_D1"}
        if str(confirmed) <= str(self.forward_start): return {"status": "SKIPPED_BEFORE_FORWARD_START"}
        body = json.dumps(payload, sort_keys=True, default=str)
        snapshot_id = hashlib.sha256(f"{confirmed}|{payload['state_hash']}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            prior = db.execute("SELECT id,state_hash FROM production8_snapshots WHERE confirmed_d1=?", (str(confirmed),)).fetchone()
            if prior:
                if prior[1] != payload["state_hash"]: raise ValueError("append-only state conflict for confirmed D1")
                return {"status": "DEDUPLICATED", "id": prior[0]}
            first = db.execute("SELECT COUNT(*) FROM production8_snapshots").fetchone()[0] == 0
            marker = "FIRST_TRUE_PRODUCTION8_FORWARD_SNAPSHOT" if first else "PRODUCTION8_FORWARD_SNAPSHOT"
            db.execute("INSERT INTO production8_snapshots VALUES(?,?,?,?,?,?)", (snapshot_id, str(confirmed), payload["state_hash"], marker, body, datetime.now(timezone.utc).isoformat()))
        return {"status": "APPENDED", "id": snapshot_id, "marker": marker}

    def append_safe(self, payload: dict[str, Any]) -> dict[str, Any]:
        try: return self.append(payload)
        except (sqlite3.DatabaseError, OSError) as exc: return {"status": "CRITICAL", "reason": type(exc).__name__, "written": False}

    def health(self) -> dict[str, Any]:
        if self.initialization_error: return {"status":"CRITICAL","reason":self.initialization_error,"append_only":True}
        try:
            with sqlite3.connect(self.path) as db:
                count, latest = db.execute("SELECT COUNT(*),MAX(confirmed_d1) FROM production8_snapshots").fetchone();integrity=db.execute("PRAGMA integrity_check").fetchone()[0];journal=db.execute("PRAGMA journal_mode").fetchone()[0]
            return {"status": "ONLINE" if integrity=="ok" else "CRITICAL", "snapshots": count, "last_confirmed_d1": latest, "append_only": True, "integrity":integrity, "journal_mode":journal}
        except sqlite3.DatabaseError as exc: return {"status":"CRITICAL","reason":type(exc).__name__,"append_only":True}
