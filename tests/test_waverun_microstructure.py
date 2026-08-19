from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from bitcoin_cycle_analyzer.short_term.data_lake import ParquetDataLake
from bitcoin_cycle_analyzer.short_term.events import normalize_binance_message
from bitcoin_cycle_analyzer.short_term.microstructure import MicrostructureFeatures, event_from_market_event
from bitcoin_cycle_analyzer.short_term.mt5_ticks import MT5TickHistory


def test_unified_event_keeps_event_and_receive_time_separate():
    received = datetime.fromtimestamp(1.25, tz=UTC)
    event = normalize_binance_message({"e": "trade", "s": "BTCUSDT", "T": 1000, "p": "100", "q": "2", "m": False}, received)
    unified = event_from_market_event(event)
    assert unified.exchange_event_time < unified.local_receive_time
    assert unified.receive_latency_ms == pytest.approx(250)


def test_microstructure_is_causal_and_computes_flow_book_and_liquidity():
    at = datetime(2026, 1, 1, tzinfo=UTC)
    features = MicrostructureFeatures()
    features.update_trade(at, 100, 2, 1)
    features.update_trade(at + timedelta(milliseconds=100), 100.1, 1, -1)
    result = features.update_quote(at + timedelta(milliseconds=200), 99.9, 100.2, 8, 2)
    assert result["delta_0.5s"] == 1
    assert result["cvd"] == 1
    assert result["orderbook_imbalance"] == pytest.approx(.6)
    assert result["microprice"] > result["midprice"]
    result = features.update_book(at + timedelta(milliseconds=300), 4, 3, 99.9, 100.2)
    assert result["bid_pulling"] == 4
    assert result["ask_pulling"] == 0


def test_mt5_tick_history_uses_real_tick_fields_and_audits():
    class Backend:
        COPY_TICKS_ALL = 0

        def copy_ticks_range(self, symbol, start, end, flags):
            return [{"time": 1, "time_msc": 1000, "bid": 99, "ask": 101, "last": 100, "volume": 2, "flags": 0, "volume_real": 2.0}]

    history = MT5TickHistory(Backend())
    frame = history.range(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    assert list(frame.columns) == ["time", "time_msc", "bid", "ask", "last", "volume", "flags", "volume_real", "timestamp", "downloaded_at"]
    assert MT5TickHistory.audit(frame)["crossed_quotes"] == 0


def test_parquet_store_refuses_empty_frame_without_touching_raw_data(tmp_path):
    lake = ParquetDataLake(tmp_path)
    with pytest.raises(ValueError):
        lake.write(pd.DataFrame(), "vantage", "BTCUSD", datetime(2026, 1, 1, tzinfo=UTC))
    assert not list(tmp_path.rglob("*"))
