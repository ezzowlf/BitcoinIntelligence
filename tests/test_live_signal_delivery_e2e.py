"""LIVE signal delivery: engine -> journal -> API -> dashboard payload -> outcome.

Forensics 2026-09-21 established that the engine does produce real LIVE signals
(6 in 92h) and that every stage of the chain works, but that a LIVE signal was
effectively invisible: it is LIVE for ~305s roughly once every 15h, the general
transition history pages it out within ~2h, and the alert controls had been
dropped from the UI.

These tests pin the delivery contract that makes a LIVE signal reachable:

  * the engine reaches LIVE on a valid scenario and commits it to the journal,
  * /api/state exposes it as the current shadow signal (what the card binds to),
  * /api/signals contains it in the chronological feed,
  * /api/live-signals returns it in a LIVE-only list that cannot be pushed out
    by CANDIDATE/REJECTED noise, carrying duration and outcome,
  * the outcome scheduler registers and resolves it.

Synthetic fixtures are used deliberately and are marked `synthetic=True` by the
engine, so nothing here can be confused with a production signal.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures  # noqa: E402
from bitcoin_cycle_analyzer.short_term.events import normalize_binance_message  # noqa: E402
from bitcoin_cycle_analyzer.short_term.journal import Journal, atomic_json  # noqa: E402
from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine  # noqa: E402
from bitcoin_cycle_analyzer.short_term.signal_engine import SignalEngine  # noqa: E402
from bitcoin_cycle_analyzer.short_term.web_api import create_app  # noqa: E402


def _drive_to_live(root, sign=1):
    """Run the real engine over a scenario that satisfies every gate."""
    runtime = root / "runtime/waverun"
    journal = Journal(runtime / "journal.db")
    outcomes = OutcomeEngine(journal)
    engine = SignalEngine(journal, outcomes)
    features = CausalFeatures()
    start = datetime.now(UTC) - timedelta(seconds=400)
    transitions = []
    for second in range(7):
        now = start + timedelta(seconds=second)
        price = 77000 + sign * second * 2
        for market in ("spot", "futures"):
            for i in range(30):
                stamp = now - timedelta(milliseconds=30 - i)
                event = normalize_binance_message(
                    {"e": "trade", "s": "BTCUSDT", "T": int(stamp.timestamp() * 1000),
                     "p": str(price + sign * i * 0.001), "q": "0.01", "m": sign < 0},
                    stamp, market)
                payload = event.payload
                features.trade(market, stamp, payload["price"], payload["quantity"],
                               payload["buyer_is_maker"])
        outcomes.quote(now, price, price + 1)
        snapshot = features.snapshot(
            now, {"bid": price, "ask": price + 1}, l2=sign * 0.8,
            feed_health={k: "HEALTHY" for k in ("spot", "futures", "l2", "vantage")},
            storage_ready=True, outcomes_ready=True, synthetic=True)
        transition = engine.evaluate(now, snapshot)
        if transition:
            transitions.append(transition)
            atomic_json(runtime / "signal.json", engine.snapshot())
    return journal, outcomes, engine, transitions, start


@pytest.mark.parametrize("sign,direction", [(1, "LONG"), (-1, "SHORT")])
def test_live_signal_is_delivered_through_every_stage(tmp_path, sign, direction):
    journal, outcomes, engine, transitions, start = _drive_to_live(tmp_path, sign)

    # --- stage 1: engine reached LIVE ------------------------------------
    assert [t["state_to"] for t in transitions] == ["CANDIDATE", "PREWARNING", "ARMED", "LIVE"]
    live = transitions[-1]
    assert live["direction"] == direction

    # --- stage 2: committed to the durable journal -----------------------
    committed = journal.rows("signal_transition")
    assert any(r["payload"]["state_to"] == "LIVE" for r in committed)

    with TestClient(create_app(tmp_path)) as client:
        # --- stage 3: /api/state -> what the signal card binds to --------
        state = client.get("/api/state").json()
        signal = state["shadow_signal"]["signal"]
        assert signal["state_to"] == "LIVE"
        assert signal["direction"] == direction
        assert signal["setup_id"] == live["setup_id"]
        assert state["execution"] == "DISABLED"
        # evaluation-time evidence travels with it (see SignalCard)
        assert signal["feed_health"]["vantage"] == "HEALTHY"

        # --- stage 4: chronological history ------------------------------
        feed = client.get("/api/signals?limit=50").json()
        assert any(r["state_to"] == "LIVE" and r["setup_id"] == live["setup_id"]
                   for r in feed["signals"])

        # --- stage 5: LIVE-only list -------------------------------------
        only_live = client.get("/api/live-signals?limit=20").json()
        assert only_live["available"] is True
        assert only_live["execution"] == "DISABLED"
        rows = only_live["signals"]
        assert len(rows) == 1, "exactly the one LIVE signal, no candidate noise"
        row = rows[0]
        assert row["setup_id"] == live["setup_id"]
        assert row["direction"] == direction
        assert row["entry_zone"] == live["entry_zone"]
        assert row["invalidation"] == live["invalidation"]
        # Still LIVE -> duration is unknown, not zero.
        assert row["live_seconds"] is None
        assert row["synthetic"] is True


def test_live_only_list_is_not_pushed_out_by_candidate_noise(tmp_path):
    """The defect this endpoint exists for: a LIVE signal must stay reachable
    however many CANDIDATE/REJECTED rows arrive afterwards."""
    journal, outcomes, engine, transitions, start = _drive_to_live(tmp_path, 1)
    live = transitions[-1]

    # 400 later transitions - far more than the 50-row page of /api/signals.
    later = datetime.now(UTC)
    for i in range(400):
        moment = later + timedelta(seconds=i)
        journal.append(
            "signal_transition", "noise-%d" % i, moment,
            {"setup_id": "noise-%d" % i, "timestamp": moment.isoformat(),
             "state_from": "OBSERVING", "state_to": "REJECTED", "direction": "LONG",
             "reasons": ["REQUIRED_EVIDENCE_UNAVAILABLE"], "missing_evidence": ["vantage"],
             "conflicts": [], "synthetic": True},
            stage="signal_transition")

    with TestClient(create_app(tmp_path)) as client:
        feed = client.get("/api/signals?limit=50").json()
        assert not any(r["state_to"] == "LIVE" for r in feed["signals"]), (
            "precondition: the chronological feed has paged the LIVE signal out")

        rows = client.get("/api/live-signals?limit=20").json()["signals"]
        assert [r["setup_id"] for r in rows] == [live["setup_id"]]


def test_live_signal_reaches_the_outcome_scheduler(tmp_path):
    """Stage 6/7: the LIVE signal is registered as an observation and resolved."""
    journal, outcomes, engine, transitions, start = _drive_to_live(tmp_path, 1)
    live = transitions[-1]

    # A complete future quote path, so resolution is not gap-limited.
    for second in range(7, 320):
        moment = start + timedelta(seconds=second)
        price = 77000 + second * 2
        outcomes.quote(moment, price, price + 1)

    results = outcomes.resolve_due(start + timedelta(seconds=330))
    live_results = [r for r in results if r["kind"] == "LIVE" and r["horizon_seconds"] == 300]
    assert live_results, "the LIVE signal produced no outcome"
    result = live_results[0]
    assert result["status"] == "RESOLVED"
    assert result["observation"]["setup_id"] == live["setup_id"]

    engine.accept_outcome(result)
    assert engine.snapshot()["state"] == "OUTCOME"

    with TestClient(create_app(tmp_path)) as client:
        rows = client.get("/api/live-signals?limit=20").json()["signals"]
        assert len(rows) == 1
        assert rows[0]["outcome_status"] == "RESOLVED"
        # The signal is no longer LIVE, so its duration is now known.
        assert rows[0]["live_seconds"] is not None
        assert rows[0]["ended_state"] == "OUTCOME"


def test_live_signals_endpoint_survives_an_empty_journal(tmp_path):
    (tmp_path / "runtime/waverun").mkdir(parents=True, exist_ok=True)
    Journal(tmp_path / "runtime/waverun/journal.db")
    with TestClient(create_app(tmp_path)) as client:
        payload = client.get("/api/live-signals").json()
        assert payload["signals"] == []
        assert payload["available"] is True
