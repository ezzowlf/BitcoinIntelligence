"""B-2 independent health supervisor, pipeline watchdog, degraded operating
state, deduplicated alerting, staged auto-repair and verified recovery
(Phases 2, 4, 7-13, 16). Deterministic - no network, no real sleeps.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bitcoin_cycle_analyzer.short_term import resilience
from bitcoin_cycle_analyzer.short_term.health import FeedHealth
from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.resilience import OperatingState, compute_operating_state, ComponentHealth


@pytest.fixture(autouse=True)
def fast_config(monkeypatch):
    c = resilience.CONFIG
    for name, value in {
        "startup_grace": 0.0,
        "supervisor_interval": 0.01,
        "feed_stale_after": 5.0,
        "feed_offline_after": 30.0,
        "decision_stale_after": 10.0,
        "decision_offline_after": 30.0,
        "prediction_stale_after": 10.0,
        "prediction_offline_after": 30.0,
        "alert_degraded_after": 0.0,
        "alert_reminder_interval": 3600.0,
        "alert_recovery_warning_failures": 3,
        "repair_cooldown": 0.0,
        "repair_level1_max": 2,
        "repair_level2_max": 1,
        "repair_level3_max": 1,
        "restart_budget": 2,
        "restart_budget_window": 3600.0,
    }.items():
        monkeypatch.setattr(c, name, value)
    return c


class _FakeFeed:
    def __init__(self):
        self.symbol = "btcusdt"
        self.health = {"spot": FeedHealth("BINANCE_SPOT"), "futures": FeedHealth("BINANCE_FUTURES")}
        self._stopped = False

    def refresh_states(self, now=None):
        return {k: v.refresh(now) for k, v in self.health.items()}

    def stop(self):
        self._stopped = True


def _write_line(path: Path, ts: datetime, extra: dict | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": ts.isoformat(), "received_timestamp": ts.isoformat(), "execution": "DISABLED"}
    row.update(extra or {})
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(row) + "\n")


def _make(tmp_path, feed, vantage_age):
    rt = tmp_path / "runtime" / "waverun"
    rt.mkdir(parents=True, exist_ok=True)
    (tmp_path / "database").mkdir(parents=True, exist_ok=True)
    (tmp_path / "database" / "waverun_predictions.db").write_bytes(b"")  # exists; mtime = now
    sup = HealthSupervisor(runtime_dir=rt, feed=feed, vantage_age=lambda: vantage_age())
    return sup, rt


def _touch_predictions(tmp_path):
    (tmp_path / "database" / "waverun_predictions.db").write_bytes(b"x")

def _commit_stages(rt,now):
    journal=Journal(rt/'journal.db')
    for stage in ('features','candidates','decisions','predictions','outcome_scheduler','storage','feed_spot','vantage'):
        journal.mark(stage,now.isoformat(),now,committed_at=now)


# --------------------------------------------------------- operating-state model


def test_operating_state_spot_offline_is_critical():
    comps = {
        "binance_spot": ComponentHealth("binance_spot", "OFFLINE"),
        "binance_futures": ComponentHealth("binance_futures", "HEALTHY"),
        "vantage": ComponentHealth("vantage", "HEALTHY"),
        "decision_pipeline": ComponentHealth("decision_pipeline", "DEGRADED"),
        "prediction_persistence": ComponentHealth("prediction_persistence", "IDLE_FEED_DOWN"),
    }
    state, reasons = compute_operating_state(comps)
    assert state is OperatingState.CRITICAL


def test_operating_state_futures_only_loss_is_degraded():
    comps = {
        "binance_spot": ComponentHealth("binance_spot", "HEALTHY"),
        "binance_futures": ComponentHealth("binance_futures", "OFFLINE"),
        "vantage": ComponentHealth("vantage", "HEALTHY"),
        "decision_pipeline": ComponentHealth("decision_pipeline", "HEALTHY"),
        "prediction_persistence": ComponentHealth("prediction_persistence", "HEALTHY"),
    }
    state, _ = compute_operating_state(comps)
    assert state is OperatingState.DEGRADED_LIVE


def test_operating_state_all_binance_dead_vantage_ok_is_critical():
    comps = {
        "binance_spot": ComponentHealth("binance_spot", "OFFLINE"),
        "binance_futures": ComponentHealth("binance_futures", "OFFLINE"),
        "vantage": ComponentHealth("vantage", "HEALTHY"),
        "decision_pipeline": ComponentHealth("decision_pipeline", "OFFLINE"),
        "prediction_persistence": ComponentHealth("prediction_persistence", "OFFLINE"),
    }
    state, _ = compute_operating_state(comps)
    assert state is OperatingState.CRITICAL


def test_operating_state_vantage_stale_is_degraded():
    comps = {
        "binance_spot": ComponentHealth("binance_spot", "HEALTHY"),
        "binance_futures": ComponentHealth("binance_futures", "HEALTHY"),
        "vantage": ComponentHealth("vantage", "STALE"),
        "decision_pipeline": ComponentHealth("decision_pipeline", "HEALTHY"),
        "prediction_persistence": ComponentHealth("prediction_persistence", "HEALTHY"),
    }
    state, _ = compute_operating_state(comps)
    assert state in {OperatingState.DEGRADED_LIVE, OperatingState.RECOVERING}


# ---------------------------------------------------------------- supervisor tick


def test_spot_dead_but_vantage_futures_alive_is_not_live(tmp_path):
    """Test 8 / Phase 4: spot OFFLINE, vantage+futures fresh -> CRITICAL, health.json
    written, decision pipeline flagged - never a healthy global LIVE."""
    feed = _FakeFeed()
    now = datetime.now(UTC)
    feed.health["spot"].event(now)
    feed.health["futures"].event(now)
    sup, rt = _make(tmp_path, feed, lambda: 1.0)
    _write_line(rt / "market_events.jsonl", now)
    _write_line(rt / "pre_gate_candidates.jsonl", now)
    _write_line(rt / "decision_records.jsonl", now)
    sup.tick()  # baseline: everything healthy

    # spot dies
    feed.health["spot"].last_event_at = datetime.now(UTC) - timedelta(seconds=120)  # -> refresh -> OFFLINE
    feed.health["futures"].event(datetime.now(UTC))
    _write_line(rt / "market_events.jsonl", datetime.now(UTC) - timedelta(seconds=1))  # futures still writing market events
    report = sup.tick()
    assert report["operating_state"] == "CRITICAL"
    assert report["overall"] == "CRITICAL"
    assert (rt / "health.json").exists()
    hj = json.loads((rt / "health.json").read_text())
    assert hj["components"]["binance_spot"]["state"] == "OFFLINE"
    assert hj["components"]["vantage"]["state"] == "HEALTHY"
    # incident + alert recorded
    incidents = [json.loads(x) for x in (rt / "incidents.jsonl").read_text().splitlines() if x.strip()]
    assert any(i["component"] == "binance_spot" for i in incidents)
    alerts = [json.loads(x) for x in (rt / "alerts.jsonl").read_text().splitlines() if x.strip()]
    assert any(a["kind"] in {"CRITICAL", "DEGRADED"} for a in alerts)


def test_pipeline_watchdog_detects_stall_with_healthy_feeds(tmp_path):
    """Test 12 / Phase 8: feeds fresh, but decision writes stopped -> incident on
    decision_pipeline, and a quiet market (fresh writes) is NOT flagged."""
    feed = _FakeFeed()
    now = datetime.now(UTC)
    for m in ("spot", "futures"):
        feed.health[m].event(now)
    sup, rt = _make(tmp_path, feed, lambda: 1.0)
    # quiet market: everything fresh
    _write_line(rt / "market_events.jsonl", now)
    _write_line(rt / "pre_gate_candidates.jsonl", now)
    _write_line(rt / "decision_records.jsonl", now)
    _commit_stages(rt,now)
    r1 = sup.tick()
    assert r1["components"]["decision_pipeline"]["state"] == "HEALTHY"
    assert r1["operating_state"] in {"FULL_LIVE", "RECOVERING"}

    # feeds stay fresh, but the decision pipeline froze 60s ago
    feed.health["spot"].event(datetime.now(UTC))
    feed.health["futures"].event(datetime.now(UTC))
    # (no new decision / candidate writes; existing ones age past decision_offline_after)
    old = datetime.now(UTC) - timedelta(seconds=60)
    _commit_stages(rt,old)
    (rt / "pre_gate_candidates.jsonl").write_text(json.dumps({"timestamp": old.isoformat()}) + "\n")
    (rt / "decision_records.jsonl").write_text(json.dumps({"timestamp": old.isoformat()}) + "\n")
    _write_line(rt / "market_events.jsonl", datetime.now(UTC))
    r2 = sup.tick()
    assert r2["components"]["decision_pipeline"]["state"] in {"STALE", "OFFLINE"}
    incidents = [json.loads(x) for x in (rt / "incidents.jsonl").read_text().splitlines() if x.strip()]
    assert any(i["component"] == "decision_pipeline" and i["new_state"] in {"STALE", "OFFLINE"} for i in incidents)


def test_recovery_requires_real_data_flow(tmp_path):
    """Tests 13+14 / Phase 10: socket back CONNECTED but no new events -> NOT
    RECOVERED; only once market + decision writes advance is RECOVERED emitted."""
    feed = _FakeFeed()
    now = datetime.now(UTC)
    feed.health["spot"].event(now - timedelta(seconds=120))  # OFFLINE
    feed.health["futures"].event(now)
    sup, rt = _make(tmp_path, feed, lambda: 1.0)
    _write_line(rt / "market_events.jsonl", now - timedelta(seconds=120))
    _write_line(rt / "pre_gate_candidates.jsonl", now - timedelta(seconds=120))
    _write_line(rt / "decision_records.jsonl", now - timedelta(seconds=120))
    sup.tick()  # register the outage

    # socket reconnects, but the downstream data flow has NOT resumed yet
    feed.health["spot"].event(datetime.now(UTC))
    sup.tick()
    alerts = [json.loads(x) for x in (rt / "alerts.jsonl").read_text().splitlines() if x.strip()]
    assert not any(a["kind"] == "RECOVERED" for a in alerts), "RECOVERED must wait for real data flow"

    # now the entire causal chain, including predictions and source markers, resumes
    _commit_stages(rt,datetime.now(UTC))
    _write_line(rt / "market_events.jsonl", datetime.now(UTC))
    _write_line(rt / "decision_records.jsonl", datetime.now(UTC))
    _write_line(rt / "pre_gate_candidates.jsonl", datetime.now(UTC))
    feed.health["spot"].event(datetime.now(UTC))
    sup.tick()
    sup.tick()
    alerts = [json.loads(x) for x in (rt / "alerts.jsonl").read_text().splitlines() if x.strip()]
    assert any(a["kind"] == "RECOVERED" for a in alerts)
    incidents = [json.loads(x) for x in (rt / "incidents.jsonl").read_text().splitlines() if x.strip()]
    assert any(i["recovery_result"] == "DATA_FLOW_RECOVERED" for i in incidents)


def test_alert_deduplication(tmp_path, monkeypatch):
    """Test 15 / Phase 12: identical state repeated -> exactly one alert until the
    reminder interval elapses."""
    feed = _FakeFeed()
    now = datetime.now(UTC)
    feed.health["spot"].event(now - timedelta(seconds=120))
    feed.health["futures"].event(now)
    sup, rt = _make(tmp_path, feed, lambda: 1.0)
    _write_line(rt / "market_events.jsonl", now - timedelta(seconds=120))
    _write_line(rt / "pre_gate_candidates.jsonl", now - timedelta(seconds=120))

    # freeze auto-repair so this test isolates alert dedup only
    monkeypatch.setattr(resilience.CONFIG, "repair_cooldown", 10_000.0)
    for _ in range(6):
        sup.tick()
    alerts = [json.loads(x) for x in (rt / "alerts.jsonl").read_text().splitlines() if x.strip()]
    spot_alerts = [a for a in alerts if a["component"] == "binance_spot" and not a.get("reminder")]
    # dedup is per (component, kind): the same STALE/DEGRADED state must not
    # re-alert every tick.
    from collections import Counter
    by_kind = Counter(a["kind"] for a in spot_alerts)
    assert by_kind and all(v == 1 for v in by_kind.values()), by_kind


def test_restart_request_and_loop_protection(tmp_path):
    """Tests 18+19 / Phase 9: after repeated failed recovery a bounded number of
    Level-4 restart requests is written, then further requests are suppressed."""
    feed = _FakeFeed()
    now = datetime.now(UTC)
    feed.health["spot"].event(now - timedelta(seconds=300))
    feed.health["futures"].event(now)
    sup, rt = _make(tmp_path, feed, lambda: 1.0)
    _write_line(rt / "market_events.jsonl", now - timedelta(seconds=300))
    _write_line(rt / "pre_gate_candidates.jsonl", now - timedelta(seconds=300))

    for _ in range(40):
        feed.health["spot"].last_event_at = datetime.now(UTC) - timedelta(seconds=300)
        sup.tick()

    assert sup._repair.level >= 3
    incidents = [json.loads(x) for x in (rt / "incidents.jsonl").read_text().splitlines() if x.strip()]
    l4 = [i for i in incidents if i["new_state"] == "LEVEL_4"]
    suppressed = [i for i in incidents if i["new_state"] == "LEVEL_4_SUPPRESSED"]
    assert len(l4) <= resilience.CONFIG.restart_budget
    assert suppressed, "restart-loop protection must eventually suppress further restarts"
    if l4:
        assert (rt / "restart_request.json").exists()
