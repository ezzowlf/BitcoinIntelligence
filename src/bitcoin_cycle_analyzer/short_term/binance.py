from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from .events import MarketEvent, normalize_binance_message
from .health import FeedHealth


def _recoverable_feed_errors() -> tuple[type[BaseException], ...]:
    """Errors that must trigger a reconnect instead of killing the collector.

    ``websockets`` raises ``ConnectionClosed`` / ``ConnectionClosedOK`` /
    ``ConnectionClosedError`` on a normal network drop. None of these inherit from
    ``OSError`` or ``RuntimeError``, so without listing them here a routine
    disconnect would propagate through ``asyncio.gather`` and stop the feed (B-1).
    """

    errors: tuple[type[BaseException], ...] = (OSError, RuntimeError)
    try:  # optional dependency, mirrors _run_connection
        from websockets.exceptions import ConnectionClosed, WebSocketException

        errors = (*errors, ConnectionClosed, WebSocketException)
    except ImportError:
        pass
    return errors


class BinancePublicFeed:
    """Optional-dependency WebSocket feed. It has no private/trading endpoints."""

    def __init__(self, symbol: str = "btcusdt", include_futures: bool = False, max_reconnect_delay: float = 30.0):
        symbol = symbol.lower()
        self.symbol = symbol
        self.include_futures = include_futures
        self.max_reconnect_delay = max_reconnect_delay
        streams = [f"{symbol}@trade", f"{symbol}@bookTicker", f"{symbol}@depth@100ms"]
        self.spot_url = "wss://stream.binance.com:9443/stream?streams=" + "/".join(streams)
        self.futures_url = "wss://fstream.binance.com/stream?streams=" + "/".join(
            [f"{symbol}@trade", f"{symbol}@markPrice@1s", f"{symbol}@forceOrder"]
        )
        self.health = {"spot": FeedHealth("BINANCE_SPOT"), "futures": FeedHealth("BINANCE_FUTURES")}
        self._stop = False

    async def run(self, callback: Callable[[MarketEvent], Awaitable[None] | None], duration_seconds: float | None = None) -> None:
        started = asyncio.get_running_loop().time()
        self._stop = False
        tasks = [self._run_market(self.spot_url, "spot", callback, started, duration_seconds)]
        if self.include_futures:
            tasks.append(self._run_market(self.futures_url, "futures", callback, started, duration_seconds))
        await asyncio.gather(*tasks)

    async def _run_market(self, url, market, callback, started, duration_seconds):
        delay = 1.0
        recoverable = _recoverable_feed_errors()
        while not self._stop and (duration_seconds is None or asyncio.get_running_loop().time() - started < duration_seconds):
            try:
                remaining = None if duration_seconds is None else max(0.1, duration_seconds - (asyncio.get_running_loop().time() - started))
                if remaining is None:
                    await self._run_connection(url, market, callback)
                else:
                    await asyncio.wait_for(self._run_connection(url, market, callback), timeout=remaining)
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                return
            except recoverable as exc:
                self.health[market].disconnect(type(exc).__name__)
                await asyncio.sleep(delay)
                delay = min(self.max_reconnect_delay, delay * 2)

    async def _run_connection(self, url: str, market: str, callback) -> None:
        try:
            import websockets  # type: ignore
        except ImportError as exc:
            raise RuntimeError("websockets dependency is required for Binance live mode") from exc
        async with websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=5) as socket:
            self.health[market].event(datetime.now(UTC))
            async for raw in socket:
                event = normalize_binance_message(json.loads(raw), datetime.now(UTC), market)
                if event is None:
                    continue
                self.health[market].event(event.received_timestamp)
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result

    def stop(self) -> None:
        self._stop = True

    def status(self) -> dict:
        return {key: value.to_dict() for key, value in self.health.items()}
