from datetime import UTC, datetime

import pandas as pd

from bitcoin_cycle_analyzer.short_term.outcomes import resolve_vantage_path


def _ticks(rows):
    index = pd.to_datetime([row[0] for row in rows], utc=True)
    return pd.DataFrame({"bid": [row[1] for row in rows], "ask": [row[2] for row in rows]}, index=index)


def test_long_uses_ask_entry_and_bid_exit_target_first():
    start = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    ticks = _ticks([("2026-08-21T10:00:01Z", 1000, 1001), ("2026-08-21T10:00:02Z", 1101, 1102)])
    result = resolve_vantage_path({"timestamp": start.isoformat(), "direction": "LONG", "ask": 1001}, ticks, target=100, adverse=50, horizon=2)
    assert result["target_first"] is True
    assert result["adverse_first"] is False
    assert result["time_to_target"] == 2.0
    assert result["mfe"] == 100.0
    assert result["mae"] == -1.0


def test_short_uses_bid_entry_and_ask_exit_adverse_first():
    start = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    ticks = _ticks([("2026-08-21T10:00:01Z", 1000, 1001), ("2026-08-21T10:00:02Z", 1051, 1052)])
    result = resolve_vantage_path({"timestamp": start.isoformat(), "direction": "SHORT", "bid": 1000}, ticks, target=100, adverse=50, horizon=2)
    assert result["target_first"] is False
    assert result["adverse_first"] is True
    assert result["time_to_adverse"] == 2.0
    assert result["mae"] == -52.0
