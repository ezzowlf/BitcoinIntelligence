from datetime import UTC, datetime, timedelta

from bitcoin_cycle_analyzer.short_term.unverified_live import UnverifiedSignalTracker


def test_signal_uses_directional_vantage_entry_and_tracks_complete_horizons(tmp_path):
    tracker = UnverifiedSignalTracker(tmp_path)
    start = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)
    signal = tracker.observe(
        timestamp=start,
        direction="LONG",
        quote={"bid": 100.0, "ask": 117.0, "spread": 17.0},
        mechanism=[{"name": "flow"}],
        quality=.5,
        reasons=["flow aligned"],
        risks=["calibration unavailable"],
    )
    assert signal and signal["entry"] == 117.0 and signal["entry_side"] == "ASK"
    for seconds, bid in ((10, 110.0), (30, 130.0), (60, 170.0), (120, 220.0), (180, 260.0), (300, 330.0)):
        tracker.record_vantage_tick({
            "timestamp": (start + timedelta(seconds=seconds)).isoformat(),
            "bid": bid,
            "ask": bid + 17.0,
        })
    rows = tracker.outcomes_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 5
    assert '"horizon_seconds": 300' in rows[-1]
    assert '"100": true' in rows[-1]


def test_short_uses_bid_and_declusters(tmp_path):
    tracker = UnverifiedSignalTracker(tmp_path)
    start = datetime(2026, 8, 25, 20, 0, tzinfo=UTC)
    kwargs = {
        "direction": "SHORT", "quote": {"bid": 200.0, "ask": 217.0, "spread": 17.0},
        "mechanism": [], "quality": .5, "reasons": [], "risks": [],
    }
    first = tracker.observe(timestamp=start, **kwargs)
    second = tracker.observe(timestamp=start + timedelta(seconds=30), **kwargs)
    assert first and first["entry"] == 200.0 and first["entry_side"] == "BID"
    assert second is None
    assert len(tracker.signals_path.read_text(encoding="utf-8").splitlines()) == 1
