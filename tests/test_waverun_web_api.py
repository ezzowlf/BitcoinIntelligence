"""Contract tests for the read-only WAVERUN web API."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.resilience import ComponentHealth,REQUIRED_FOR_FULL_LIVE

from bitcoin_cycle_analyzer.short_term.web_api import (
    TIMEFRAMES,
    assessment_text,
    build_candles,
    create_app,
    proximity_score,
    why_no_signal,
)


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.fixture
def root(tmp_path):
    now = datetime.now(UTC)
    runtime = tmp_path / "runtime"
    ticks = []
    for index in range(600):
        stamp = now - timedelta(seconds=600 - index)
        ticks.append({
            "time_msc": int(stamp.timestamp() * 1000),
            "timestamp": stamp.isoformat(),
            "bid": 77000.0 + index,
            "ask": 77017.0 + index,
            "spread": 17.0,
            "symbol": "BTCUSD",
            "source": "MT5_VANTAGE",
            "execution": "DISABLED",
        })
    _write(runtime / "waverun/vantage_ticks.jsonl", ticks)
    _write(runtime / "waverun/pre_gate_candidates.jsonl", [{
        "timestamp": now.isoformat(),
        "direction_bias": "SHORT",
        "final_decision": "BLOCKED",
        "long_pressure_score": 0.0,
        "short_pressure_score": 60.0,
        "contradictions": [],
        "availability": {"l2": "AVAILABLE"},
        "momentum_pressure_state": {"l2_imbalance": -0.4, "returns": {"60": -0.0005}, "range_expansion": 1.9},
        "signals": [
            {"name": "spot_flow_10s", "direction": "BEARISH", "group": "FLOW", "available": True},
            {"name": "futures_flow_10s", "direction": "BEARISH", "group": "FLOW", "available": True},
        ],
        "execution": "DISABLED",
    }])
    (runtime / "waverun/latest.json").write_text(
        json.dumps({"mode": "LIVE", "state": "ARMED", "forecasts": []}), encoding="utf-8"
    )
    status = runtime / "waverun_v5_3_fast_v2_forward"
    status.mkdir(parents=True, exist_ok=True)
    (status / "status.json").write_text(json.dumps({
        "status": "PROVISIONAL", "accepted_signals": 3, "veto_blocked_signals": 1,
        "resolved_signals": 2, "progress_to_100": "2/100", "successes_100_5m": 1,
        "recorder_health": "RUNNING",
        "source_health": {"vantage": "AVAILABLE", "feeds": {
            "spot": {"state": "CONNECTED"}, "futures": {"state": "DEGRADED"}}},
        "execution": "DISABLED",
    }), encoding="utf-8")
    journal=Journal(runtime/'waverun/journal.db')
    for stage in ('features','candidates','decisions','predictions','outcome_scheduler','storage','feed_spot','feed_futures','feed_l2','vantage'):
        journal.mark(stage,'fixture-chain',now,committed_at=now)
    _write(runtime/'waverun/decision_records.jsonl',[{'timestamp':now.isoformat()}])
    components={k:ComponentHealth(k,'HEALTHY').to_dict() for k in REQUIRED_FOR_FULL_LIVE}
    components['binance_futures']=ComponentHealth('binance_futures','DEGRADED').to_dict()
    components['l2']=ComponentHealth('l2','HEALTHY').to_dict()
    (runtime/'waverun/health.json').write_text(json.dumps({'server_time':now.isoformat(),'components':components}))
    return tmp_path


@pytest.fixture
def client(root):
    return TestClient(create_app(root))


def test_health_reports_execution_disabled(client):
    payload = client.get("/api/health").json()
    assert payload["status"] == "OK"
    assert payload["execution"] == "DISABLED"


def test_state_exposes_real_engine_fields(client):
    payload = client.get("/api/state").json()
    assert payload["execution"] == "DISABLED"
    # `connection` is now the rolled-up operating state. Vantage + the decision
    # pipeline are fresh in the fixture, but futures is DEGRADED -> DEGRADED_LIVE.
    assert payload["connection"] == "DEGRADED"
    assert payload["vantage_connection"] == "LIVE"
    assert payload["health"]["components"]["decision_pipeline"]["state"] == "HEALTHY"
    assert payload["health"]["components"]["binance_futures"]["state"] == "DEGRADED"
    assert payload["market_state"]["setup_state"] == "ARMED"
    assert payload["market_state"]["direction_bias"] == "SHORT"
    assert payload["market_state"]["flow_agreement"] == "CONFIRMED"
    assert payload["price"]["bid"] == pytest.approx(77599.0)


def test_connection_is_live_when_everything_fresh(client, root):
    """All feeds CONNECTED and a fresh decision pipeline -> global LIVE."""
    status = root / "runtime" / "waverun_v5_3_fast_v2_forward" / "status.json"
    data = json.loads(status.read_text())
    data["source_health"]["feeds"]["futures"] = {"state": "CONNECTED"}
    status.write_text(json.dumps(data), encoding="utf-8")
    report=root/'runtime/waverun/health.json'
    health=json.loads(report.read_text());health['components']['binance_futures']['state']='HEALTHY'
    report.write_text(json.dumps(health))
    payload = client.get("/api/state").json()
    assert payload["connection"] == "LIVE"
    assert payload["health"]["components"]["decision_pipeline"]["state"] == "HEALTHY"


def test_stale_decision_pipeline_is_never_live(client, root):
    """Core B-2 contract: fresh vantage + frozen decision pipeline is not LIVE."""
    stale = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
    _write(root/'runtime/waverun/decision_records.jsonl',[{'timestamp':stale}])
    journal=Journal(root/'runtime/waverun/journal.db')
    for stage in ('decisions','candidates','predictions'):
        journal.mark(stage,'frozen-pipeline',stale,committed_at=stale)
    _write(root / "runtime" / "waverun" / "pre_gate_candidates.jsonl", [{
        "timestamp": stale, "direction_bias": "NEUTRAL", "final_decision": "BLOCKED",
        "contradictions": [], "availability": {}, "execution": "DISABLED",
    }])
    (root / "runtime" / "waverun" / "latest.json").write_text(
        json.dumps({"mode": "LIVE", "state": "NEUTRAL", "generated_at": stale, "forecasts": []}),
        encoding="utf-8",
    )
    payload = client.get("/api/state").json()
    assert payload["connection"] != "LIVE"
    assert payload["connection"] in {"DEGRADED", "CRITICAL"}
    assert payload["vantage_connection"] == "LIVE"
    assert payload["health"]["components"]["decision_pipeline"]["state"] in {"STALE", "OFFLINE"}


def test_v5_3_separates_discovery_from_live_validation(client):
    v53 = client.get("/api/state").json()["v5_3"]
    assert v53["discovery_win_rate"] == 69.05
    assert v53["discovery_label"] == "Discovery"
    assert v53["forward_resolved"] == 2
    assert v53["forward_target"] == 100
    assert v53["verified"] is False


def test_proximity_is_never_presented_as_probability(client):
    proximity = client.get("/api/state").json()["proximity"]
    assert proximity["label"] == "SIGNALNÄHE-SCORE"
    assert proximity["is_probability"] is False
    assert 0 <= proximity["score"] <= 100


def test_proximity_is_bounded_and_monotonic_in_state():
    common = dict(direction="SHORT", pressure=100.0, flow_agreement="CONFIRMED",
                  l2_aligned=True, sources_online=5, sources_total=5)
    neutral = proximity_score(setup_state="NEUTRAL", **common)["score"]
    armed = proximity_score(setup_state="ARMED", **common)["score"]
    signal = proximity_score(setup_state="SIGNAL", **common)["score"]
    assert neutral < armed < signal <= 100


def test_checklist_marks_offline_sources_and_blocked_decision(client):
    rows = {row["label"]: row for row in client.get("/api/state").json()["checklist"]}
    assert rows["Datenquellen vollständig online"]["status"] == "MISSING"
    assert "Binance Futures" in rows["Datenquellen vollständig online"]["detail"]
    assert rows["Endgültige Engine-Freigabe"]["status"] == "MISSING"
    assert rows["Marktzustand mindestens ARMED"]["status"] == "MET"


def test_checklist_statuses_are_from_the_known_set(client):
    for row in client.get("/api/state").json()["checklist"]:
        assert row["status"] in {"MET", "MISSING", "RISK"}


def test_assessment_is_german_and_deterministic():
    kwargs = dict(setup_state="ARMED", direction="SHORT", pressure=60.0,
                  momentum={"returns": {"60": -0.0005}}, flow_agreement="CONFIRMED",
                  spot_direction="BEARISH", futures_direction="BEARISH", live_state="LIVE")
    first, second = assessment_text(**kwargs), assessment_text(**kwargs)
    assert first == second
    assert "Setup" in first and "abwärts" in first
    assert "Ausführung ist deaktiviert" in first


def test_assessment_warns_when_feed_is_not_live():
    text = assessment_text(setup_state="NEUTRAL", direction="NEUTRAL", pressure=0.0,
                           momentum={}, flow_agreement="NEUTRAL", spot_direction="UNAVAILABLE",
                           futures_direction="UNAVAILABLE", live_state="OFFLINE")
    assert "nicht live" in text


def test_why_no_signal_flags_contradictions_as_risk():
    rows = {row["label"]: row for row in why_no_signal(
        setup_state="ARMED", direction="SHORT", final_decision="BLOCKED",
        flow_agreement="CONFIRMED", l2_aligned=True, contradictions=["flow vs. L2"],
        sources=[{"label": "Vantage (MT5)", "online": True}], spread=12.0, live_state="LIVE")}
    assert rows["Keine Widersprüche in den Signalen"]["status"] == "RISK"


def test_candles_available_for_every_advertised_timeframe(client):
    for timeframe in TIMEFRAMES:
        payload = client.get(f"/api/candles?timeframe={timeframe}&limit=100").json()
        assert payload["timeframe"] == timeframe
        assert payload["has_volume"] is False
        assert payload["execution"] == "DISABLED"
        for candle in payload["candles"]:
            assert candle["low"] <= candle["open"] <= candle["high"]
            assert candle["low"] <= candle["close"] <= candle["high"]


def test_unknown_timeframe_is_rejected(client):
    assert client.get("/api/candles?timeframe=7m").status_code == 400


def test_candles_are_sorted_and_deduplicated_across_restarts():
    base = 1_700_000_000
    ticks = [
        {"time_msc": (base + 120) * 1000, "bid": 100.0, "ask": 102.0},
        {"time_msc": (base + 130) * 1000, "bid": 110.0, "ask": 112.0},
        # a restart appends an older run to the same file
        {"time_msc": (base + 5) * 1000, "bid": 90.0, "ask": 92.0},
        {"time_msc": (base + 125) * 1000, "bid": 95.0, "ask": 97.0},
    ]
    candles = build_candles(ticks, 60, 100)
    assert [candle["time"] for candle in candles] == sorted({candle["time"] for candle in candles})
    assert len(candles) == 2
    assert candles[-1]["high"] == pytest.approx(111.0)
    assert candles[-1]["low"] == pytest.approx(96.0)


def test_candle_endpoint_never_exposes_an_execution_path(client):
    body = client.get("/api/state").text
    assert "DISABLED" in body
    for method in ("post", "put", "delete", "patch"):
        response = getattr(client, method)("/api/state")
        assert response.status_code == 405
