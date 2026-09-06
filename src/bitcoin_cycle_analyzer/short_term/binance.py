from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from .events import MarketEvent, normalize_binance_message
from .health import FeedHealth
from .resilience import CONFIG


class FeedRecoverableError(Exception):
    """Base for feed failures that must trigger backoff + retry, never process death."""


class FeedConnectTimeout(FeedRecoverableError):
    """`websockets.connect()` (handshake / DNS / TCP / TLS) exceeded the hard cap."""


class FeedIdleTimeout(FeedRecoverableError):
    """The socket stayed technically open but delivered no valid frame in time.

    This is the B-2 case: a half-open connection that neither closes nor raises.
    Treated as a controlled disconnect so the reconnect loop keeps running.
    """


def _recoverable_feed_errors() -> tuple[type[BaseException], ...]:
    """Errors that must trigger a reconnect instead of killing the collector.

    ``websockets`` raises ``ConnectionClosed`` / ``ConnectionClosedOK`` /
    ``ConnectionClosedError`` on a normal network drop. None of these inherit from
    ``OSError`` or ``RuntimeError``, so without listing them here a routine
    disconnect would propagate through ``asyncio.gather`` and stop the feed (B-1).

    ``FeedRecoverableError`` covers the B-2 connect-hang / idle-socket cases.
    """

    errors: tuple[type[BaseException], ...] = (OSError, RuntimeError, FeedRecoverableError)
    try:  # optional dependency, mirrors _run_connection
        from websockets.exceptions import ConnectionClosed, WebSocketException

        errors = (*errors, ConnectionClosed, WebSocketException)
    except ImportError:
        pass
    return errors


class BinancePublicFeed:
    """Optional-dependency WebSocket feed. It has no private/trading endpoints.

    Each market (``spot`` / ``futures``) runs its own independent connect ->
    consume -> backoff loop. A failure or hang on one never stops the other and
    never propagates out of :meth:`run`. Every connection attempt is bounded by
    an explicit connect timeout, and every read is bounded by an idle timeout, so
    a technically-open-but-silent socket can no longer freeze a stream (B-2).
    """

    def __init__(
        self,
        symbol: str = "btcusdt",
        include_futures: bool = False,
        max_reconnect_delay: float | None = None,
        *,
        open_timeout: float | None = None,
        connect_timeout: float | None = None,
        idle_timeout: float | None = None,
        ping_interval: float | None = None,
        ping_timeout: float | None = None,
        reconnect_base_delay: float | None = None,
        callback_timeout: float | None = None,
        separate_l2: bool = False,
        jitter: float = 0.15,
        retry_budget: int = 60,
        retry_window: float = 300.0,
    ):
        symbol = symbol.lower()
        self.symbol = symbol
        self.include_futures = include_futures
        self.max_reconnect_delay = max_reconnect_delay if max_reconnect_delay is not None else CONFIG.reconnect_max_delay
        self.reconnect_base_delay = reconnect_base_delay if reconnect_base_delay is not None else CONFIG.reconnect_base_delay
        self.open_timeout = open_timeout if open_timeout is not None else CONFIG.ws_open_timeout
        self.connect_timeout = connect_timeout if connect_timeout is not None else CONFIG.ws_connect_timeout
        self.idle_timeout = idle_timeout if idle_timeout is not None else CONFIG.ws_idle_timeout
        self.ping_interval = ping_interval if ping_interval is not None else CONFIG.ws_ping_interval
        self.ping_timeout = ping_timeout if ping_timeout is not None else CONFIG.ws_ping_timeout
        self.callback_timeout = callback_timeout if callback_timeout is not None else min(self.idle_timeout, 10.0)
        self.separate_l2 = separate_l2
        self.jitter = max(0.0, min(1.0, jitter))
        self.retry_budget, self.retry_window = max(1, retry_budget), max(.01, retry_window)
        if min(self.open_timeout,self.connect_timeout,self.idle_timeout,self.callback_timeout,self.reconnect_base_delay,self.max_reconnect_delay) <= 0:
            raise ValueError('feed timeouts and backoff must be positive')
        self._connections = {}
        self.lifecycle_sink = None
        self.raw_sink = None
        streams = [f"{symbol}@trade", f"{symbol}@bookTicker", f"{symbol}@depth@100ms"]
        self.spot_url = "wss://stream.binance.com:9443/stream?streams=" + "/".join(streams)
        self.l2_url = "wss://stream.binance.com:9443/stream?streams=" + f"{symbol}@depth@100ms"
        if separate_l2:
            self.spot_url = "wss://stream.binance.com:9443/stream?streams=" + "/".join(streams[:2])
        self.futures_url = "wss://fstream.binance.com/stream?streams=" + "/".join(
            [f"{symbol}@trade", f"{symbol}@markPrice@1s", f"{symbol}@forceOrder"]
        )
        self.health = {"spot": FeedHealth("BINANCE_SPOT"), "futures": FeedHealth("BINANCE_FUTURES")}
        if separate_l2:
            self.health['l2'] = FeedHealth('BINANCE_SPOT_L2')
        self._stop = False

    async def run(self, callback: Callable[[MarketEvent], Awaitable[None] | None], duration_seconds: float | None = None) -> None:
        started = asyncio.get_running_loop().time()
        self._stop = False
        markets = ["spot"] + (["futures"] if self.include_futures else []) + (['l2'] if self.separate_l2 else [])
        async def own(market):
            while not self._stop:
                try:
                    await self._run_market(getattr(self,f'{market}_url'),market,callback,started,duration_seconds)
                    if self._stop or duration_seconds is not None:
                        return
                    self.health[market].disconnect('MARKET_LOOP_RETURNED')
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.health[market].disconnect(f'MARKET_LOOP_CRASHED:{type(exc).__name__}')
                    self._log(market,'TASK_FAILED',type(exc).__name__)
                await asyncio.sleep(self.max_reconnect_delay)
        tasks = [asyncio.create_task(own(m),name=f'feed-owner-{m}') for m in markets]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)

    def _log(self, market, state, reason=None):
        if self.lifecycle_sink:
            try:
                self.lifecycle_sink({'timestamp':datetime.now(UTC).isoformat(),'market':market,'state':state,'reason':reason,'execution':'DISABLED'})
            except Exception as exc:
                self.ledger_error='LIFECYCLE_LEDGER_'+type(exc).__name__
                self.health[market].last_error=self.ledger_error

    def request_reconnect(self, market):
        task=self._connections.get(market)
        if task and not task.done():
            task.cancel('controlled reconnect')

    async def _run_market(self, url, market, callback, started, duration_seconds):
        delay = self.reconnect_base_delay
        recoverable = _recoverable_feed_errors()
        attempt = 0
        attempts = deque()
        while not self._stop and (duration_seconds is None or asyncio.get_running_loop().time() - started < duration_seconds):
            now=time.monotonic()
            while attempts and now-attempts[0]>=self.retry_window:attempts.popleft()
            if len(attempts)>=self.retry_budget:
                self.health[market]._set_state('RECOVERING','RETRY_BUDGET_COOLDOWN')
                await asyncio.sleep(max(.01,self.retry_window-(now-attempts[0])))
                continue
            attempts.append(now)
            attempt += 1
            try:
                self.health[market].connecting()
                self._log(market,'CONNECT_ATTEMPT')
                remaining = None if duration_seconds is None else max(0.1, duration_seconds - (asyncio.get_running_loop().time() - started))
                task=asyncio.create_task(self._run_connection(url,market,callback))
                self._connections[market]=task
                try:
                    if remaining is None: await task
                    else:
                        done,_=await asyncio.wait([task],timeout=remaining)
                        if not done:
                            task.cancel();await asyncio.gather(task,return_exceptions=True)
                            return
                        await task
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():raise
                    raise FeedRecoverableError('controlled task recreation')
                delay = self.reconnect_base_delay
            except asyncio.CancelledError:
                raise
            except (*recoverable, TimeoutError) as exc:
                self.health[market].disconnect(type(exc).__name__)
                self._log(market,'DISCONNECTED',type(exc).__name__)
                self.health[market].reconnecting(attempt)
                await asyncio.sleep(min(self.max_reconnect_delay,delay*(1+random.uniform(0,self.jitter))))
                delay = min(self.max_reconnect_delay, delay * 2)

    async def _run_connection(self, url: str, market: str, callback) -> None:
        try:
            import websockets  # type: ignore
        except ImportError as exc:
            raise RuntimeError("websockets dependency is required for Binance live mode") from exc

        # Hard cap on connection establishment (handshake/DNS/TCP/TLS). websockets
        # provides open_timeout for the handshake; wait_for is the outer belt so a
        # stall anywhere in connect() cannot hang the stream forever.
        try:
            socket = await asyncio.wait_for(
                websockets.connect(
                    url,
                    open_timeout=self.open_timeout,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                    close_timeout=5,
                ),
                timeout=self.connect_timeout,
            )
        except TimeoutError as exc:
            raise FeedConnectTimeout(f"{market} connect exceeded {self.connect_timeout}s") from exc

        try:
            self._log(market,'SOCKET_CONNECTED')
            last_valid=time.monotonic()
            while True:
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=max(.001,self.idle_timeout-(time.monotonic()-last_valid)))
                except TimeoutError as exc:
                    raise FeedIdleTimeout(
                        f"no frame from {market} for {self.idle_timeout}s (socket open but silent)"
                    ) from exc
                received=datetime.now(UTC)
                if self.raw_sink and self.raw_sink(market,raw,received) is False:
                    self.health[market]._set_state('DEGRADED','RAW_STORAGE_UNAVAILABLE')
                event = normalize_binance_message(json.loads(raw), received, 'spot' if market=='l2' else market)
                if event is None:
                    continue
                last_valid=time.monotonic()
                self.health[market].event(event.received_timestamp,exchange_timestamp=event.exchange_timestamp)
                if self.health[market].total_events==1:self._log(market,'FIRST_VALID_EVENT')
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result,timeout=self.callback_timeout)
                # Callback has its own budget. Do not charge it to the next read.
                last_valid=time.monotonic()
        finally:
            try:
                await asyncio.wait_for(socket.close(), timeout=5)
            except BaseException:  # noqa: BLE001 - best-effort cleanup, never mask the real error
                pass

    def refresh_states(self, now: datetime | None = None) -> dict[str, str]:
        """Independent age-based freshness pass (Phase 6/7). Safe to call from a
        supervisor with no market events flowing."""
        return {key: value.refresh(now) for key, value in self.health.items()}

    def stop(self) -> None:
        self._stop = True

    def status(self, now: datetime | None = None) -> dict:
        return {key: value.to_dict(now) for key, value in self.health.items()}
