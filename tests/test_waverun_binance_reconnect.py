"""Regression tests for B-1: a routine Binance websocket disconnect must not
kill the collector via ``asyncio.gather``."""

from __future__ import annotations

import asyncio

import pytest

from bitcoin_cycle_analyzer.short_term.binance import (
    BinancePublicFeed,
    _recoverable_feed_errors,
)

websockets_exceptions = pytest.importorskip("websockets.exceptions")
ConnectionClosedError = websockets_exceptions.ConnectionClosedError
ConnectionClosedOK = websockets_exceptions.ConnectionClosedOK
ConnectionClosed = websockets_exceptions.ConnectionClosed


def test_recoverable_errors_cover_all_connection_closed_variants():
    recoverable = _recoverable_feed_errors()
    assert issubclass(ConnectionClosed, recoverable)
    assert issubclass(ConnectionClosedOK, recoverable)
    assert issubclass(ConnectionClosedError, recoverable)


class _FlakyFeed(BinancePublicFeed):
    def __init__(self, exc_factory, fail_times: int, **kwargs):
        super().__init__(**kwargs)
        self._exc_factory = exc_factory
        self._fail_times = fail_times
        self.attempts: dict[str, int] = {"spot": 0, "futures": 0}
        self.healthy: set[str] = set()
        self.max_reconnect_delay = 0.05  # keep the test fast

    async def _run_connection(self, url, market, callback):  # type: ignore[override]
        self.attempts[market] += 1
        if self.attempts[market] <= self._fail_times:
            raise self._exc_factory()
        # Healthy connection: emit one event; stop only once every stream recovered.
        from datetime import UTC, datetime

        self.health[market].event(datetime.now(UTC))
        self.healthy.add(market)
        expected = {"spot", "futures"} if self.include_futures else {"spot"}
        if self.healthy >= expected:
            self._stop = True
        else:
            await asyncio.sleep(0)


@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: ConnectionClosedError(None, None),
        lambda: ConnectionClosedOK(None, None),
        lambda: OSError("connection reset by peer"),
    ],
)
def test_collector_survives_repeated_disconnects(exc_factory):
    feed = _FlakyFeed(exc_factory, fail_times=5, include_futures=True)

    async def _callback(event):
        return None

    # Must complete without propagating the disconnect exception.
    asyncio.run(asyncio.wait_for(feed.run(_callback), timeout=5.0))

    # Every stream reconnected past its failures and is not left DEGRADED-dead.
    assert feed.attempts["spot"] >= 6
    assert feed.attempts["futures"] >= 6
    assert feed.health["spot"].reconnects == 5
    assert feed.health["futures"].reconnects == 5


def test_backoff_is_bounded_and_does_not_spin(monkeypatch):
    """A permanently failing stream must back off (capped) rather than busy-loop."""
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    feed = _FlakyFeed(lambda: ConnectionClosedError(None, None), fail_times=10_000)
    feed.max_reconnect_delay = 4.0

    async def _tracking_sleep(delay, *a, **k):
        sleeps.append(delay)
        if len(sleeps) >= 8:
            feed._stop = True
        return await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", _tracking_sleep)

    async def _callback(event):
        return None

    asyncio.run(feed.run(_callback))

    assert sleeps, "expected the collector to back off between reconnects"
    assert max(sleeps) <= feed.max_reconnect_delay
    # Exponential growth: not a fixed-zero busy loop.
    assert sleeps[1] > sleeps[0]


class TestLedgerErrorRecovery:
    """Root cause fixed 2026-09-14: a transient lifecycle_sink (journal) write
    failure used to set feed.ledger_error permanently, forcing storage=OFFLINE
    (via health_supervisor.py) for the rest of the process's life since nothing
    ever cleared it and Level-1 recovery reuses the same feed object. The fix:
    the next SUCCESSFUL lifecycle write clears the latch. Failures are never
    swallowed silently - last_error is still set at the moment of failure."""

    def test_normal_operation_never_sets_ledger_error(self):
        feed = BinancePublicFeed()
        feed.lifecycle_sink = lambda payload: None
        feed._log("spot", "CONNECT_ATTEMPT")
        feed._log("spot", "CONNECTED")
        assert feed.ledger_error is None

    def test_transient_sink_failure_sets_ledger_error(self):
        feed = BinancePublicFeed()
        feed.lifecycle_sink = lambda payload: (_ for _ in ()).throw(OSError("db locked"))
        feed._log("spot", "CONNECT_ATTEMPT")
        assert feed.ledger_error == "LIFECYCLE_LEDGER_OSError"
        assert feed.health["spot"].last_error == "LIFECYCLE_LEDGER_OSError"

    def test_later_successful_write_clears_ledger_error(self):
        feed = BinancePublicFeed()
        calls = {"n": 0}

        def flaky_sink(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("db locked")

        feed.lifecycle_sink = flaky_sink
        feed._log("spot", "CONNECT_ATTEMPT")  # fails -> latches
        assert feed.ledger_error is not None
        feed._log("spot", "CONNECTED")  # succeeds -> recovery
        assert feed.ledger_error is None

    def test_health_supervisor_reads_recovered_state(self):
        """health_supervisor.py checks getattr(feed,'ledger_error',None) live on
        every poll - once _log clears it, the very next health snapshot must
        stop reporting storage=OFFLINE for this reason, with no separate reset
        call needed anywhere else."""
        feed = BinancePublicFeed()
        calls = {"n": 0}

        def flaky_sink(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("db locked")

        feed.lifecycle_sink = flaky_sink
        feed._log("spot", "CONNECT_ATTEMPT")
        assert getattr(feed, "ledger_error", None) is not None
        feed._log("spot", "CONNECTED")
        assert getattr(feed, "ledger_error", None) is None

    def test_repeated_failures_keep_latching_until_a_success(self):
        feed = BinancePublicFeed()
        feed.lifecycle_sink = lambda payload: (_ for _ in ()).throw(OSError("still locked"))
        for _ in range(5):
            feed._log("spot", "CONNECT_ATTEMPT")
        assert feed.ledger_error == "LIFECYCLE_LEDGER_OSError"

    def test_reconnect_with_transient_ledger_failure_still_completes(self):
        """A ledger write failure during a reconnect cycle must not prevent the
        feed itself from reconnecting and delivering events - the two concerns
        (ledger bookkeeping vs. market data flow) are independent."""

        class _LedgerFlakyFeed(_FlakyFeed):
            def __init__(self, **kwargs):
                super().__init__(lambda: OSError("connection reset"), fail_times=2, **kwargs)
                self._sink_calls = 0

            def _log(self, market, state, reason=None):
                self._sink_calls += 1
                if self.lifecycle_sink is None:
                    self.lifecycle_sink = self._flaky_sink
                super()._log(market, state, reason)

            def _flaky_sink(self, payload):
                if self._sink_calls <= 2:
                    raise OSError("db locked during reconnect")

        feed = _LedgerFlakyFeed()

        async def _callback(event):
            return None

        asyncio.run(asyncio.wait_for(feed.run(_callback), timeout=5.0))

        assert feed.attempts["spot"] >= 3
        assert feed.ledger_error is None  # cleared by a later successful lifecycle write
