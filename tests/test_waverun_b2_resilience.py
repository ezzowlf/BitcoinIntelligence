"""B-2 resilience: connect timeout, idle-socket watchdog, independent per-feed
recovery, and feed-freshness state machine (Phases 5, 6). Deterministic; uses a
fake websockets transport so no network is touched.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from bitcoin_cycle_analyzer.short_term.binance import (
    BinancePublicFeed,
    FeedConnectTimeout,
    FeedIdleTimeout,
    _recoverable_feed_errors,
)
from bitcoin_cycle_analyzer.short_term.health import FeedHealth

pytest.importorskip("websockets.exceptions")
from websockets.exceptions import ConnectionClosedError  # noqa: E402


# --------------------------------------------------------------- fake transport


class _FakeConn:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0
        self.closed = False

    async def recv(self):
        self.calls += 1
        mode = self.behaviour(self.calls)
        if mode == "frame":
            await asyncio.sleep(0.02)  # simulate real frame cadence, keep the loop cooperative
            return (
                '{"stream":"btcusdt@trade","data":{"e":"trade","s":"BTCUSDT",'
                '"p":"77000.0","q":"0.1","m":false,"T":%d}}'
                % int(datetime.now(UTC).timestamp() * 1000)
            )
        if mode == "hang":
            await asyncio.sleep(3600)
        if mode == "closed":
            raise ConnectionClosedError(None, None)
        raise AssertionError(mode)

    async def close(self):
        self.closed = True


class _FakeWebsockets:
    """Stand-in for the ``websockets`` module used inside ``_run_connection``.

    ``connect_mode`` is a global default; ``plan`` maps a URL substring
    ("spot"/"stream" or "futures"/"fstream") to ``fn(attempt) -> mode`` where
    mode is "ok" | "hang" | "raise". ``recv_behaviour`` maps the same key to a
    per-connection recv plan ``fn(recv_call) -> "frame" | "hang" | "closed"``.
    """

    def __init__(self, *, connect_mode="ok", recv_behaviour=None):
        self.connect_mode = connect_mode
        self.recv_behaviour = recv_behaviour or (lambda n: "frame")
        self.connect_calls = 0
        self.attempts: dict[str, int] = {"spot": 0, "futures": 0}
        self.plan: dict[str, object] = {}
        self.recv_plan: dict[str, object] = {}
        self.conns: list[_FakeConn] = []

    def _key(self, url: str) -> str:
        return "futures" if ("fstream" in url or "futures" in url) else "spot"

    def connect(self, url, **kwargs):
        self.connect_calls += 1
        key = self._key(url)
        self.attempts[key] += 1
        attempt = self.attempts[key]
        mode_fn = self.plan.get(key)
        mode = mode_fn(attempt) if callable(mode_fn) else self.connect_mode
        recv_fn = self.recv_plan.get(key, self.recv_behaviour)
        outer = self

        class _Awaitable:
            def __await__(self_inner):
                async def _go():
                    if mode == "hang":
                        await asyncio.sleep(3600)
                    if mode == "raise":
                        raise OSError("connection refused")
                    conn = _FakeConn(recv_fn)
                    outer.conns.append(conn)
                    return conn

                return _go().__await__()

        return _Awaitable()


@pytest.fixture
def fake_ws(monkeypatch):
    fw = _FakeWebsockets()
    import sys

    monkeypatch.setitem(sys.modules, "websockets", fw)
    return fw


def _feed(**kw):
    kw.setdefault("include_futures", False)
    kw.setdefault("connect_timeout", 0.15)
    kw.setdefault("idle_timeout", 0.15)
    kw.setdefault("open_timeout", 0.15)
    kw.setdefault("max_reconnect_delay", 0.05)
    kw.setdefault("reconnect_base_delay", 0.02)
    return BinancePublicFeed("btcusdt", **kw)


async def _noop(_event):
    return None


# --------------------------------------------------------------------- tests


def test_recoverable_errors_include_b2_timeouts():
    rec = _recoverable_feed_errors()
    assert issubclass(FeedConnectTimeout, rec)
    assert issubclass(FeedIdleTimeout, rec)
    assert issubclass(ConnectionClosedError, rec)


def test_connect_timeout_is_bounded_and_retries(fake_ws):
    """Test A/2: a hanging connect() must time out, back off, and retry - never hang."""
    fake_ws.connect_mode = "hang"

    async def scenario():
        feed = _feed()
        task = asyncio.create_task(feed.run(_noop))
        await asyncio.sleep(1.0)  # several connect_timeout windows
        feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(asyncio.wait_for(scenario(), timeout=5.0))
    assert fake_ws.connect_calls >= 2  # retried, did not hang on the first attempt
    assert feed.health["spot"].reconnects >= 1
    assert feed.health["spot"].state in {"RECONNECTING", "DEGRADED", "CONNECTING", "OFFLINE"}


def test_idle_socket_is_detected_and_recovered(fake_ws):
    """Test 3/C+D: socket opens but yields no frame -> idle timeout -> reconnect;
    once frames resume the feed is CONNECTED again."""
    fake_ws.attempts["spot"] = 0

    def recv_plan_for_spot(recv_call):
        # connections 1-2 are silent (attempt tracked via closure of outer state)
        return "hang" if fake_ws.attempts["spot"] <= 2 else "frame"

    fake_ws.recv_plan["spot"] = recv_plan_for_spot

    async def scenario():
        feed = _feed()
        task = asyncio.create_task(feed.run(_noop))
        await asyncio.sleep(1.2)
        feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(asyncio.wait_for(scenario(), timeout=6.0))
    assert feed.health["spot"].reconnects >= 1
    assert feed.health["spot"].last_error in {"FeedIdleTimeout", "FeedConnectTimeout"}
    assert feed.health["spot"].state == "CONNECTED"
    assert feed.health["spot"].total_events >= 1


def test_multiple_connect_failures_survive(fake_ws):
    """Test 6: many consecutive failures, process (run coroutine) stays alive."""
    fake_ws.connect_mode = "raise"

    async def scenario():
        feed = _feed()
        task = asyncio.create_task(feed.run(_noop))
        await asyncio.sleep(1.0)
        alive = not task.done()
        feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return alive, feed

    alive, feed = asyncio.run(asyncio.wait_for(scenario(), timeout=5.0))
    assert alive
    assert feed.health["spot"].reconnects >= 3
    # after feed_offline_after_failures consecutive failures the feed self-marks OFFLINE
    assert feed.health["spot"].consecutive_failures >= 3


def test_spot_and_futures_recover_independently(fake_ws):
    """Test 7/G: futures failing must not stop spot and vice versa; both recover."""
    fake_ws.plan["spot"] = lambda attempt: "ok"
    fake_ws.plan["futures"] = lambda attempt: "raise" if attempt <= 3 else "ok"

    async def scenario():
        feed = _feed(include_futures=True)
        task = asyncio.create_task(feed.run(_noop))
        await asyncio.sleep(1.5)
        feed.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return feed

    feed = asyncio.run(asyncio.wait_for(scenario(), timeout=8.0))
    assert feed.health["spot"].total_events >= 1
    assert feed.health["spot"].state == "CONNECTED"
    assert feed.health["futures"].reconnects >= 1          # futures did fail
    assert feed.health["futures"].total_events >= 1        # ...and recovered independently


# --------------------------------------------------- FeedHealth freshness machine


def test_feedhealth_refresh_ages_connected_to_stale_then_offline():
    fh = FeedHealth("BINANCE_SPOT")
    fh.event(datetime.now(UTC) - timedelta(seconds=5))
    assert fh.refresh(stale_after_seconds=10, offline_after_seconds=60) == "CONNECTED"
    fh.last_event_at = datetime.now(UTC) - timedelta(seconds=20)
    assert fh.refresh(stale_after_seconds=10, offline_after_seconds=60) == "STALE"
    fh.last_event_at = datetime.now(UTC) - timedelta(seconds=120)
    assert fh.refresh(stale_after_seconds=10, offline_after_seconds=60) == "OFFLINE"


def test_feedhealth_state_transitions_have_timestamps():
    fh = FeedHealth("BINANCE_SPOT")
    fh.connecting()
    assert fh.state == "CONNECTING"
    fh.event(datetime.now(UTC))
    assert fh.state == "CONNECTED" and fh.total_events == 1
    fh.disconnect("ConnectionClosedError")
    assert fh.state == "DEGRADED" and fh.reconnects == 1 and fh.last_error == "ConnectionClosedError"
    fh.reconnecting(2)
    assert fh.state == "RECONNECTING"
    d = fh.to_dict()
    assert {"state", "age_seconds", "reconnect_count", "last_error", "recovery_level"} <= d.keys()
