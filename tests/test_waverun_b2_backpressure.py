"""HOTFIX regression on 85bc61e: the Binance Spot EVENT_QUEUE_FULL reconnect storm.

A saturated CONSUMER queue must NOT be treated as a transport disconnect and must
NOT trigger a feed reconnect. Replaceable high-rate depth/book events are
coalesced (drop-oldest, counted); causally required trade events are only shed
under genuine severe stall, counted, and used to degrade data quality (which
suppresses NEW live signals) - never a reconnect storm, never FALSE-LIVE.
Memory stays bounded by the fixed queue size.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import waverun_live  # noqa: E402
from bitcoin_cycle_analyzer.short_term import resilience  # noqa: E402
from bitcoin_cycle_analyzer.short_term.events import EventType, MarketEvent  # noqa: E402
from bitcoin_cycle_analyzer.short_term.health import FeedHealth  # noqa: E402
from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor  # noqa: E402
from bitcoin_cycle_analyzer.short_term.journal import Journal  # noqa: E402
from bitcoin_cycle_analyzer.short_term.resilience import (  # noqa: E402
    ComponentHealth,
    OperatingState,
    REQUIRED_FOR_FULL_LIVE,
    compute_operating_state,
)


class _ExplodingFeed:
    """Any transport-health call here means the dispatch path wrongly treated a
    full consumer queue as a disconnect."""

    def __getattr__(self, name):  # noqa: D401
        raise AssertionError(f"dispatch path must not touch feed.{name} on a full consumer queue")


def _session(tmp_path):
    ls = waverun_live.LiveSession.__new__(waverun_live.LiveSession)
    ls.output = tmp_path / "latest.json"
    ls.output.parent.mkdir(parents=True, exist_ok=True)
    ls.backpressure_path = tmp_path / "backpressure.json"
    ls._bp = {"coalesced": {}, "dropped": {}}
    ls._bp_severe_until = 0.0
    ls._bp_last_write = 0.0
    ls.feed = _ExplodingFeed()
    return ls


def _ev(kind: EventType, market: str = "spot") -> MarketEvent:
    now = datetime.now(UTC)
    return MarketEvent(kind, "BINANCE_SPOT", "BTCUSDT", now, now,
                       {"market": market, "price": 79000.0, "quantity": 0.05, "buyer_is_maker": False})


def test_depth_flood_coalesces_and_never_disconnects(tmp_path):
    ls = _session(tmp_path)
    ls._event_queues = {"l2": asyncio.Queue(maxsize=4), "spot": asyncio.Queue(maxsize=4), "futures": asyncio.Queue(maxsize=4)}

    async def scenario():
        for _ in range(200):
            await ls._dispatch_event(_ev(EventType.DEPTH))
            assert ls._event_queues["l2"].qsize() <= 4  # memory stays bounded

    asyncio.run(scenario())
    assert ls._bp["coalesced"].get("l2", 0) >= 190  # nearly all excess was coalesced
    assert ls._bp["dropped"] == {}  # no causal event lost
    assert ls._bp_severe_until == 0.0  # not severe
    bp = json.loads(ls.backpressure_path.read_text())
    assert bp["severe"] is False
    assert bp["queues"]["l2"]["capacity"] == 4 and bp["queues"]["l2"]["size"] <= 4
    assert bp["execution"] == "DISABLED"


def test_book_ticker_has_its_own_coalescing_lane(tmp_path):
    """bookTicker must not share the spot TRADE queue (that starved trades)."""
    ls = _session(tmp_path)
    ls._event_queues = {"spot": asyncio.Queue(maxsize=3), "book": asyncio.Queue(maxsize=3),
                        "l2": asyncio.Queue(maxsize=3), "futures": asyncio.Queue(maxsize=3)}
    assert ls._queue_key(_ev(EventType.BOOK_TICKER)) == "book"
    assert ls._queue_key(_ev(EventType.DEPTH)) == "l2"
    assert ls._queue_key(_ev(EventType.TRADE, "spot")) == "spot"
    assert ls._queue_key(_ev(EventType.TRADE, "futures")) == "futures"
    asyncio.run(_run(ls, [_ev(EventType.BOOK_TICKER) for _ in range(50)]))
    assert ls._bp["coalesced"].get("book", 0) >= 45
    assert ls._bp["dropped"] == {}
    assert ls._bp_severe_until == 0.0
    assert ls._event_queues["spot"].qsize() == 0  # spot trade lane untouched


def test_trade_shed_under_severe_stall_is_counted_and_degrades(tmp_path):
    """A full queue of TRADEs (consumer genuinely stalled): the newest trade
    still enters, the oldest trade is shed - counted, and marked severe so new
    LIVE signals get suppressed. Still no reconnect."""
    ls = _session(tmp_path)
    q = asyncio.Queue(maxsize=3)
    ls._event_queues = {"spot": q, "l2": asyncio.Queue(maxsize=3), "futures": asyncio.Queue(maxsize=3)}

    async def scenario():
        for _ in range(3):
            await ls._dispatch_event(_ev(EventType.TRADE))
        assert q.full()
        await ls._dispatch_event(_ev(EventType.TRADE))  # overflow with a trade
        assert q.qsize() == 3  # bounded

    asyncio.run(scenario())
    assert ls._bp["dropped"].get("spot", 0) == 1
    assert ls._bp_severe_until > 0.0
    ls._bp_flush(force=True)
    bp = json.loads(ls.backpressure_path.read_text())
    assert bp["severe"] is True
    assert bp["dropped"]["spot"] == 1


def test_severe_backpressure_marks_spot_unavailable_for_signal_gate(tmp_path):
    """When _bp_severe_until is in the future, _evaluate_event downgrades spot/l2
    so SignalEngine.evaluate()'s existing data-quality gate suppresses new LIVE."""
    import inspect
    src = inspect.getsource(waverun_live.LiveSession._evaluate_event)
    assert "self._bp_severe_until" in src
    assert "source_states['spot']='UNAVAILABLE'" in src and "source_states['l2']='UNAVAILABLE'" in src


async def _run(ls, events):
    for e in events:
        await ls._dispatch_event(e)


def test_causal_features_snapshot_survives_zero_price_trade():
    """A malformed 0-price trade frame previously crashed the spot consumer with
    ZeroDivisionError at causal_features.snapshot (return = prices[-1]/prices[0])
    and permanently froze feed_spot->features->candidates->decisions->predictions."""
    from bitcoin_cycle_analyzer.short_term.causal_features import CausalFeatures
    cf = CausalFeatures()
    now = datetime.now(UTC)
    cf.trade("spot", now, 0.0, 0.1, False)          # poison frame
    cf.trade("spot", now, 79000.0, 0.2, False)
    cf.trade("spot", now, 79010.0, 0.2, True)
    snap = cf.snapshot(now, {"bid": 79000.0, "ask": 79010.0})  # must not raise
    assert snap["feature_version"] == "causal-windows-v1"
    # the zero frame is ignored; a real return is still computed
    assert snap["windows"]["15"]["spot"]["return"] is not None


def test_consume_events_skips_a_poison_event_and_keeps_running():
    """One event that raises must not permanently kill the consumer (was: return)."""
    import inspect
    src = inspect.getsource(waverun_live.LiveSession._consume_events)
    assert "continue  # one poison event" in src
    assert "recent>=12" in src  # only a sustained failure hands off to the watchdog
    assert "traceback" in src   # the crash location is now recorded


# --------------------------------------------------------- supervisor / health


@pytest.fixture(autouse=True)
def fast_cfg(monkeypatch):
    for k, v in {"startup_grace": 0.0, "feed_stale_after": 5.0, "feed_offline_after": 30.0,
                 "decision_stale_after": 10.0, "decision_offline_after": 30.0,
                 "prediction_stale_after": 10.0, "prediction_offline_after": 30.0}.items():
        monkeypatch.setattr(resilience.CONFIG, k, v)


class _FakeFeed:
    symbol = "btcusdt"

    def __init__(self):
        self.health = {"spot": FeedHealth("BINANCE_SPOT"), "futures": FeedHealth("BINANCE_FUTURES"), "l2": FeedHealth("BINANCE_SPOT_L2")}

    def refresh_states(self, now=None):
        return {k: v.refresh(now) for k, v in self.health.items()}

    def stop(self):
        pass


def _sup(tmp_path):
    rt = tmp_path / "runtime" / "waverun"
    rt.mkdir(parents=True, exist_ok=True)
    (tmp_path / "database").mkdir(parents=True, exist_ok=True)
    (tmp_path / "database" / "waverun_predictions.db").write_bytes(b"")
    return HealthSupervisor(runtime_dir=rt, feed=_FakeFeed(), vantage_age=lambda: 1.0), rt


def test_market_event_pipeline_uses_journal_not_retired_file(tmp_path):
    sup, rt = _sup(tmp_path)
    now = datetime.now(UTC)
    j = Journal(rt / "journal.db")
    for stage in ("feed_spot", "feed_futures", "feed_l2"):
        j.mark(stage, f"c-{stage}", now, committed_at=now)
    # NO market_events.jsonl exists on purpose
    assert not (rt / "market_events.jsonl").exists()
    comp = sup.collect()["market_event_pipeline"]
    assert comp.state == "HEALTHY"
    assert "retired" in (comp.detail or "")


def test_consumer_backpressure_component_and_operating_state(tmp_path):
    sup, rt = _sup(tmp_path)
    now = datetime.now(UTC)
    # healthy telemetry -> HEALTHY
    (rt / "backpressure.json").write_text(json.dumps({
        "updated_at": now.isoformat(), "severe": False, "queues": {}, "coalesced": {"l2": 12}, "dropped": {},
    }))
    assert sup.collect()["consumer_backpressure"].state == "HEALTHY"

    # severe -> CRITICAL, and it keeps the roll-up off FULL_LIVE
    (rt / "backpressure.json").write_text(json.dumps({
        "updated_at": now.isoformat(), "severe": True, "queues": {}, "coalesced": {"l2": 40}, "dropped": {"spot": 3},
    }))
    comp = sup.collect()["consumer_backpressure"]
    assert comp.state == "CRITICAL"
    assert "consumer_backpressure" in REQUIRED_FOR_FULL_LIVE
    healthy = {k: ComponentHealth(k, "HEALTHY") for k in REQUIRED_FOR_FULL_LIVE}
    healthy["consumer_backpressure"] = comp
    state, _ = compute_operating_state(healthy)
    assert state is not OperatingState.FULL_LIVE
