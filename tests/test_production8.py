from copy import deepcopy
import sqlite3
import shutil
from pathlib import Path

import pytest

from bitcoin_cycle_analyzer.production8 import ProcessLock, Production8Ledger, Production8Orchestrator, state_hash, verify_underlying_frozen


def sample_state():
    return {
        "timestamp":"2026-08-10T01:00:00Z",
        "master":{"decision":{"existing_position_action":"HOLD","production_signal":"NO_PRODUCTION_SIGNAL"}},
        "macro7":{"actions":{"macro":"ACCUMULATE","long_swing":"WAIT","medium_swing":"WAIT","tactical_timing":"WAIT","risk":"CAUTION"},"cycle":{"phase":"BEAR"},"elliott":{"status":"RESEARCH_ONLY"},"zones":{},"scenarios":[],"drawdown_ladder":{},"waiting_for":["structure_reclaim"],"why":["BEAR"]},
        "master5_challenger":{"buy":{},"risk":{}},"fusion6":{"regime":"BEAR","status":"RESEARCH_ONLY"},
        "historical_entry_quality":{"state":"MODERATE"},"data_status":{},
        "live_market":{"status":"ONLINE","tick":{"freshness":"LIVE","bid":99,"ask":101,"mid":100,"spread":2,"timestamp":"2026-08-10T00:59:59Z","age_seconds":1},"health":{"status":"ONLINE"},"provenance":{"execution":"DISABLED"},"last_confirmed_h4":"2026-08-10T00:00:00Z","last_confirmed_d1":"2026-08-10T00:00:00Z","last_confirmed_w1":"2026-08-04T00:00:00Z","last_confirmed_1m":"2026-08-01T00:00:00Z"},
    }


def test_domain_router_preserves_authority_and_execution_lock():
    result=Production8Orchestrator.build(sample_state())
    assert result["decision"]["macro"]=="ACCUMULATE" and result["decision"]["long_swing"]=="WAIT"
    assert result["domain_owners"]["macro_cycle"]=="MACRO_SWING_7"
    assert result["execution"]=="DISABLED" and len(result["state_hash"])==64


def test_state_hash_ignores_render_timestamp_but_detects_decision_change():
    a=Production8Orchestrator.build(sample_state());changed=sample_state();changed["timestamp"]="2026-08-10T02:00:00Z"
    b=Production8Orchestrator.build(changed);assert a["state_hash"]==b["state_hash"]
    changed["live_market"]["tick"].update({"bid":102,"ask":104,"mid":103,"timestamp":"2026-08-10T01:59:59Z","age_seconds":.2})
    assert Production8Orchestrator.build(changed)["state_hash"]==a["state_hash"]
    changed["macro7"]["actions"]["risk"]="HIGH";assert Production8Orchestrator.build(changed)["state_hash"]!=a["state_hash"]


def test_production8_ledger_first_marker_dedup_and_append_only(tmp_path):
    payload=Production8Orchestrator.build(sample_state());ledger=Production8Ledger(tmp_path/"p8.db","2026-08-09T00:00:00Z")
    first=ledger.append(payload);assert first["marker"]=="FIRST_TRUE_PRODUCTION8_FORWARD_SNAPSHOT"
    assert ledger.append(payload)["status"]=="DEDUPLICATED"
    conflicting=deepcopy(payload);conflicting["state_hash"]="different"
    with pytest.raises(ValueError,match="append-only"):ledger.append(conflicting)
    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute("DELETE FROM production8_snapshots")


def test_no_order_surface_exists():
    assert not hasattr(Production8Orchestrator,"order_send")


def test_process_lock_prevents_second_watcher_and_releases(tmp_path):
    first=ProcessLock(tmp_path/"watcher.lock");second=ProcessLock(tmp_path/"watcher.lock")
    assert first.acquire() is True and second.acquire() is False
    first.release();assert second.acquire() is True;second.release()


def test_corrupt_database_degrades_without_overwrite(tmp_path):
    path=tmp_path/"corrupt.db";path.write_bytes(b"not a sqlite database")
    ledger=Production8Ledger(path,"2026-08-09T00:00:00Z")
    assert ledger.health()["status"]=="CRITICAL"
    result=ledger.append_safe(Production8Orchestrator.build(sample_state()))
    assert result["status"]=="CRITICAL" and result["written"] is False
    assert path.read_bytes()==b"not a sqlite database"


def test_disk_write_failure_has_no_false_success(tmp_path):
    ledger=Production8Ledger(tmp_path/"p8.db","2026-08-09T00:00:00Z");ledger.initialization_error="OperationalError"
    result=ledger.append_safe(Production8Orchestrator.build(sample_state()))
    assert result=={"status":"CRITICAL","reason":"DatabaseError","written":False}


def test_frozen_hash_mismatch_hard_stops_fixture_only(tmp_path):
    root=Path(__file__).resolve().parents[1]
    for folder in ("frozen","src/bitcoin_cycle_analyzer/master","src/bitcoin_cycle_analyzer/master5","src/bitcoin_cycle_analyzer/fusion6","src/bitcoin_cycle_analyzer/macro7"):
        shutil.copytree(root/folder,tmp_path/folder)
    assert all(verify_underlying_frozen(tmp_path).values())
    target=tmp_path/"src/bitcoin_cycle_analyzer/macro7/engine.py";target.write_text(target.read_text(encoding="utf-8")+"\n# simulated mutation",encoding="utf-8")
    with pytest.raises(RuntimeError,match="FROZEN_HASH_MISMATCH"):verify_underlying_frozen(tmp_path)
