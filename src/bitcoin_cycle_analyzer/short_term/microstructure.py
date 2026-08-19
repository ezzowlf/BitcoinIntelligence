from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import median
from typing import Any

from .events import MarketEvent


@dataclass(frozen=True)
class UnifiedEvent:
    """A source-neutral event; exchange and receive time are never conflated."""

    source: str
    market: str
    instrument: str
    event_type: str
    exchange_event_time: datetime | None
    local_receive_time: datetime
    processing_time: datetime
    sequence: int | None
    payload: dict[str, Any]
    quality: str = "UNASSESSED"

    def __post_init__(self) -> None:
        if self.local_receive_time.tzinfo is None or self.processing_time.tzinfo is None:
            raise ValueError("receive and processing timestamps must be timezone-aware")

    @property
    def event_timestamp(self) -> datetime:
        return self.exchange_event_time or self.local_receive_time

    @property
    def receive_latency_ms(self) -> float | None:
        if self.exchange_event_time is None:
            return None
        return max(0.0, (self.local_receive_time - self.exchange_event_time).total_seconds() * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source, "market": self.market, "instrument": self.instrument,
            "event_type": self.event_type,
            "exchange_event_time": self.exchange_event_time.isoformat() if self.exchange_event_time else None,
            "local_receive_time": self.local_receive_time.isoformat(),
            "processing_time": self.processing_time.isoformat(), "sequence": self.sequence,
            "payload": self.payload, "quality": self.quality,
        }


def event_from_market_event(event: MarketEvent, instrument: str | None = None) -> UnifiedEvent:
    received = event.received_timestamp
    return UnifiedEvent(
        source=event.exchange, market=str(event.payload.get("market", "unknown")), instrument=instrument or event.symbol,
        event_type=event.event_type.value, exchange_event_time=event.exchange_timestamp,
        local_receive_time=received, processing_time=datetime.now(UTC),
        sequence=event.payload.get("update_id") or event.payload.get("final_update_id"),
        payload=dict(event.payload), quality="OBSERVED",
    )


def _window(events: deque[tuple[datetime, float]], now: datetime, seconds: float) -> list[tuple[datetime, float]]:
    cutoff = now.timestamp() - seconds
    while events and events[0][0].timestamp() < cutoff:
        events.popleft()
    return list(events)


class MicrostructureFeatures:
    """Incremental, causal features for the 250ms..30s observation windows."""

    WINDOWS = (0.25, 0.5, 1, 2, 5, 10, 30)

    def __init__(self, max_events: int = 20_000):
        self.trades: deque[tuple[datetime, float, float, int]] = deque(maxlen=max_events)
        self.quotes: deque[tuple[datetime, float, float]] = deque(maxlen=max_events)
        self.books: deque[tuple[datetime, float, float, float, float]] = deque(maxlen=max_events)
        self.cvd = 0.0

    def update_trade(self, timestamp: datetime, price: float, quantity: float, aggressor: int) -> dict[str, float]:
        if timestamp.tzinfo is None or price <= 0 or quantity < 0 or aggressor not in (-1, 0, 1):
            raise ValueError("invalid trade event")
        self.trades.append((timestamp, price, quantity, aggressor))
        self.cvd += quantity * aggressor
        return self.snapshot(timestamp, price=price)

    def update_quote(self, timestamp: datetime, bid: float, ask: float, bid_size: float = 0.0, ask_size: float = 0.0) -> dict[str, float | None]:
        if bid <= 0 or ask < bid or bid_size < 0 or ask_size < 0:
            raise ValueError("invalid quote")
        self.quotes.append((timestamp, bid, ask))
        self.books.append((timestamp, bid_size, ask_size, bid, ask))
        return self.snapshot(timestamp)

    def update_book(self, timestamp: datetime, bid_depth: float, ask_depth: float, best_bid: float, best_ask: float) -> dict[str, float | None]:
        if min(bid_depth, ask_depth) < 0 or best_bid <= 0 or best_ask < best_bid:
            raise ValueError("invalid orderbook state")
        self.books.append((timestamp, bid_depth, ask_depth, best_bid, best_ask))
        return self.snapshot(timestamp)

    def snapshot(self, now: datetime, price: float | None = None) -> dict[str, float | None]:
        result: dict[str, float | None] = {"cvd": self.cvd}
        recent = list(self.trades)
        for seconds in self.WINDOWS:
            rows = [row for row in recent if (now - row[0]).total_seconds() <= seconds]
            buy = sum(q for _, _, q, side in rows if side > 0)
            sell = sum(q for _, _, q, side in rows if side < 0)
            prefix = f"{seconds:g}s"
            result[f"trade_count_{prefix}"] = float(len(rows))
            result[f"trade_rate_{prefix}"] = len(rows) / seconds
            result[f"aggressive_buy_volume_{prefix}"] = buy
            result[f"aggressive_sell_volume_{prefix}"] = sell
            result[f"delta_{prefix}"] = buy - sell
            sizes = [q for _, _, q, _ in rows]
            result[f"mean_trade_size_{prefix}"] = sum(sizes) / len(sizes) if sizes else 0.0
            result[f"median_trade_size_{prefix}"] = median(sizes) if sizes else 0.0
        if len(self.trades) >= 2:
            previous = self.trades[-2][2] * self.trades[-2][3]
            result["cvd_velocity"] = (self.cvd - previous) / max((now - self.trades[-2][0]).total_seconds(), 1e-6)
        else:
            result["cvd_velocity"] = 0.0
        if self.books:
            _, bid_depth, ask_depth, bid, ask = self.books[-1]
            total = bid_depth + ask_depth
            mid = (bid + ask) / 2
            result.update({"bid_depth": bid_depth, "ask_depth": ask_depth,
                           "orderbook_imbalance": (bid_depth - ask_depth) / total if total else 0.0,
                           "midprice": mid,
                           "microprice": (ask * bid_depth + bid * ask_depth) / total if total else mid,
                           "microprice_minus_mid": ((ask * bid_depth + bid * ask_depth) / total - mid) if total else 0.0,
                           "spread": ask - bid})
            if len(self.books) >= 2:
                _, old_bid_depth, old_ask_depth, _, _ = self.books[-2]
                result["bid_liquidity_change"] = bid_depth - old_bid_depth
                result["ask_liquidity_change"] = ask_depth - old_ask_depth
                result["bid_pulling"] = max(0.0, old_bid_depth - bid_depth)
                result["ask_pulling"] = max(0.0, old_ask_depth - ask_depth)
                result["bid_stacking"] = max(0.0, bid_depth - old_bid_depth)
                result["ask_stacking"] = max(0.0, ask_depth - old_ask_depth)
        else:
            for key in ("bid_depth", "ask_depth", "orderbook_imbalance", "midprice", "microprice", "microprice_minus_mid", "spread", "bid_liquidity_change", "ask_liquidity_change", "bid_pulling", "ask_pulling", "bid_stacking", "ask_stacking"):
                result[key] = None
        return result
