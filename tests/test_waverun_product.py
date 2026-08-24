from pathlib import Path

from bitcoin_cycle_analyzer.short_term.product import (
    EXECUTION,
    HYPOTHESIS_SHA256,
    PaperLedger,
    alert_transition,
    price_frame,
)


def state():
    return {"latest_tick": {"timestamp": "2026-08-24T00:00:00+00:00", "bid": 100.0, "ask": 101.0},
            "latest_decision": {"final_decision": "BLOCKED", "execution": "DISABLED"}}


def test_paper_long_short_and_manual_exit_never_execute(tmp_path):
    ledger = PaperLedger(tmp_path / "paper.db")
    long_id = ledger.open("LONG", "manual", state())
    short_id = ledger.open("SHORT", "manual", state())
    rows = ledger.rows()
    assert {row["direction"] for row in rows} == {"LONG", "SHORT"}
    assert all(row["execution"] == "DISABLED" for row in rows)
    ledger.close(long_id, state()["latest_tick"])
    assert next(row for row in ledger.rows() if row["id"] == long_id)["status"] == "CLOSED"
    assert next(row for row in ledger.rows() if row["id"] == short_id)["status"] == "OPEN"


def test_mixed_iso_ticks_make_candles():
    ticks = [{"timestamp": "2026-08-24T00:00:00+00:00", "time_msc": 1, "bid": 99, "ask": 101},
             {"timestamp": "2026-08-24T00:00:30.100000+00:00", "time_msc": 2, "bid": 101, "ask": 103}]
    frame = price_frame(ticks, "1m")
    assert frame.iloc[0].open == 100 and frame.iloc[0].close == 102


def test_hard_execution_invariant_and_hash():
    assert EXECUTION == "DISABLED"
    assert HYPOTHESIS_SHA256 == "49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea"
    source = Path("src/bitcoin_cycle_analyzer/short_term/product.py").read_text(encoding="utf-8")
    assert "order_send" not in source and "order_create" not in source


def test_audio_alerts_are_transition_only_and_off_by_default():
    assert not alert_transition(None, "WATCH", False)
    assert alert_transition(None, "WATCH", True)
    assert not alert_transition("WATCH", "WATCH", True)
    assert alert_transition("WATCH", "ARMED", True)
    assert not alert_transition("BLOCKED", "BLOCKED", True)
