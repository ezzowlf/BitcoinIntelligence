from datetime import UTC, datetime, timedelta

from bitcoin_cycle_analyzer.short_term.audio import TransitionAlert
from bitcoin_cycle_analyzer.short_term.contracts import SetupState
from bitcoin_cycle_analyzer.short_term.events import (
    EventType,
    normalize_binance_message,
)
from bitcoin_cycle_analyzer.short_term.health import FeedHealth
from bitcoin_cycle_analyzer.short_term.orderbook import OrderBookState


def test_binance_trade_and_bookticker_are_normalized():
    received = datetime(2026, 1, 1, tzinfo=UTC)
    trade = normalize_binance_message({"e": "trade", "s": "BTCUSDT", "T": 1000, "p": "100", "q": "2", "m": False}, received)
    book = normalize_binance_message({"e": "bookTicker", "s": "BTCUSDT", "u": 7, "b": "99", "B": "3", "a": "101", "A": "4"}, received)
    assert trade.event_type == EventType.TRADE and trade.payload["price"] == 100
    assert book.event_type == EventType.BOOK_TICKER and book.payload["update_id"] == 7
    assert trade.has_exchange_timestamp


def test_orderbook_gap_fails_closed_until_resync():
    book = OrderBookState()
    book.seed_snapshot(10, [(100, 2)], [(101, 2)])
    event = normalize_binance_message({"e": "depthUpdate", "s": "BTCUSDT", "E": 1000, "U": 12, "u": 12, "b": [], "a": []})
    assert book.apply(event) == "GAP"
    assert not book.synchronized


def test_feed_health_becomes_stale():
    health = FeedHealth("TEST")
    at = datetime(2026, 1, 1, tzinfo=UTC)
    health.event(at)
    assert health.refresh(at + timedelta(seconds=16), 15) == "STALE"


def test_audio_only_fires_on_transition():
    calls = []
    alert = TransitionAlert(backend=lambda state, volume: calls.append(state))
    assert alert.transition(SetupState.WATCH)
    assert not alert.transition(SetupState.WATCH)
    assert alert.transition(SetupState.ARMED)
    assert calls == [SetupState.WATCH, SetupState.ARMED]
