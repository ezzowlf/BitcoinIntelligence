from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.api import ForecastSnapshot
from bitcoin_cycle_analyzer.short_term.binance import BinancePublicFeed
from bitcoin_cycle_analyzer.short_term.contracts import MarketTick
from bitcoin_cycle_analyzer.short_term.engine import ShortTermEngine
from bitcoin_cycle_analyzer.short_term.events import EventType
from bitcoin_cycle_analyzer.short_term.orderbook import OrderBookState
from bitcoin_cycle_analyzer.short_term.storage import ForecastStore


class LiveSession:
    def __init__(self, output: Path, database: Path, symbol: str):
        self.output, self.engine, self.store = output, ShortTermEngine(), ForecastStore(database)
        self.feed = BinancePublicFeed(symbol, include_futures=True)
        self.book = OrderBookState()
        self.last_book = None
        self.last_trade = None
        self.output.parent.mkdir(parents=True, exist_ok=True)

    async def on_event(self, event):
        if event.event_type == EventType.DEPTH:
            result = self.book.apply(event)
            if result == "GAP":
                self.feed.health["spot"].gap()
            return
        if event.event_type == EventType.BOOK_TICKER:
            self.last_book = event
            return
        if event.event_type != EventType.TRADE:
            return
        payload = event.payload
        self.last_trade = event
        bid = self.last_book.payload["bid"] if self.last_book else None
        ask = self.last_book.payload["ask"] if self.last_book else None
        received = event.received_timestamp
        exchange_timestamp = event.exchange_timestamp or received
        tick = MarketTick(payload["price"], exchange_timestamp, received, datetime.now(UTC), event.exchange, payload["quantity"], payload["quantity"] if not payload["buyer_is_maker"] else 0.0, payload["quantity"] if payload["buyer_is_maker"] else 0.0, bid, ask, self.book.imbalance())
        forecasts = self.engine.process(tick, "LIVE", received)
        for forecast in forecasts:
            self.store.append(forecast)
        snapshot = ForecastSnapshot.from_forecasts(forecasts, "LIVE", self.feed.status(), payload["price"], tick.age_seconds(received))
        self.output.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    async def run(self, duration: float | None):
        print("WAVERUN ENGINE STARTING\nDATA FEEDS CONNECTING\nFEATURE ENGINE READY\nPREDICTION ENGINE READY")
        await self.feed.run(self.on_event, duration)


def main():
    parser = argparse.ArgumentParser(description="WAVERUN observation-only Binance live prototype")
    parser.add_argument("--duration", type=float, default=None, help="stop after N seconds; default runs until interrupted")
    parser.add_argument("--symbol", default="btcusdt")
    parser.add_argument("--output", type=Path, default=ROOT / "runtime" / "waverun" / "latest.json")
    parser.add_argument("--database", type=Path, default=ROOT / "database" / "waverun_predictions.db")
    args = parser.parse_args()
    try:
        asyncio.run(LiveSession(args.output, args.database, args.symbol).run(args.duration))
    except KeyboardInterrupt:
        print("WAVERUN ENGINE STOPPED")


if __name__ == "__main__":
    main()
