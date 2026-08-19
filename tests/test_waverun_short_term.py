from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from bitcoin_cycle_analyzer.short_term import MarketTick, ShortTermEngine
from bitcoin_cycle_analyzer.short_term.outcomes import label_horizons
from bitcoin_cycle_analyzer.short_term.replay import replay


def tick(price, seconds=0, age=0, **kwargs):
    exchange = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds - age)
    received = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
    return MarketTick(price, exchange, received, received, **kwargs)


def test_all_horizons_share_one_pipeline_and_execution_is_disabled():
    engine = ShortTermEngine()
    rows = engine.process(tick(100), mode="MOCK")
    assert [row.horizon_seconds for row in rows] == [30, 60, 180, 300, 600, 900, 1800, 3600]
    assert all(row.execution == "DISABLED" and row.mode == "MOCK" for row in rows)


def test_stale_data_fails_closed():
    rows = ShortTermEngine().process(tick(100, age=60))
    assert all(row.quality == "NO_EDGE" for row in rows)
    assert all("DATA_STALE" in row.reasons for row in rows)


def test_probability_boundaries_and_replay_order():
    rows = replay([tick(100), tick(101, seconds=1)])
    assert rows
    assert all(0 <= row["p_up"] <= 1 and 0 <= row["p_down"] <= 1 for row in rows)
    with pytest.raises(ValueError):
        replay([tick(101, seconds=1), tick(100)])


def test_labels_are_timestamped_and_future_values_are_not_features():
    index = pd.date_range("2026-01-01", periods=4, freq="30s", tz="UTC")
    result = label_horizons(pd.DataFrame({"close": [100, 101, 102, 103]}, index=index), horizons=(30,))
    assert "return_30s" in result
    assert result.iloc[0]["return_30s"] > 0
    assert pd.isna(result.iloc[-1]["return_30s"])
