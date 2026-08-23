from datetime import UTC, datetime, timedelta

from bitcoin_cycle_analyzer.short_term.v5_3_forward import (
    HYPOTHESIS_SHA256,
    ForwardV2Collector,
    is_original_signal,
    resolve_short_path,
)

FEATURES = {"macd_30s_cross_direction": -1, "macd_30s_histogram": -20,
            "macd_30s_histogram_slope": -1, "macd_30s_histogram_acceleration": -4}


def test_frozen_signal_and_veto_persistence(tmp_path):
    assert is_original_signal(FEATURES)
    collector = ForwardV2Collector(tmp_path)
    stamp = datetime(2026, 8, 24, tzinfo=UTC)
    assert collector.observe(stamp, FEATURES, 0.1, {"bid": 1000, "ask": 1001, "spread": 1}, {})
    assert HYPOTHESIS_SHA256 in (tmp_path / "candidates.jsonl").read_text()


def test_short_path_uses_bid_to_future_ask():
    stamp = datetime(2026, 8, 24, tzinfo=UTC)
    candidate = {"candidate_id": "x", "timestamp": stamp.isoformat(), "accepted": True, "vantage_bid": 1000}
    ticks = [{"timestamp": (stamp + timedelta(seconds=i)).isoformat(), "ask": 1000 - i} for i in range(1, 301)]
    result = resolve_short_path(candidate, ticks)
    assert result is not None
    assert result["target_hits"]["100"]
    assert result["target_times_s"]["100"] == 100
