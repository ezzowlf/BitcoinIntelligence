from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    TRADE = "TRADE"
    BOOK_TICKER = "BOOK_TICKER"
    DEPTH = "DEPTH"
    DERIVATIVE = "DERIVATIVE"


def timestamp_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)


@dataclass(frozen=True)
class MarketEvent:
    event_type: EventType
    exchange: str
    symbol: str
    exchange_timestamp: datetime | None
    received_timestamp: datetime
    payload: dict[str, Any]
    timestamp_source: str = "exchange"

    @property
    def has_exchange_timestamp(self) -> bool:
        return self.exchange_timestamp is not None and self.timestamp_source == "exchange"


def normalize_binance_message(message: dict[str, Any], received_timestamp: datetime | None = None, market: str = "spot") -> MarketEvent | None:
    """Normalize public Binance stream payloads; never exposes exchange JSON downstream."""
    received = received_timestamp or datetime.now(UTC)
    data = message.get("data", message)
    event = data.get("e")
    symbol = str(data.get("s", "")).upper()
    if event in {"trade", "aggTrade"}:
        return MarketEvent(EventType.TRADE, f"BINANCE_{market.upper()}", symbol, timestamp_ms(data.get("T") or data.get("E")), received, {"price": float(data["p"]), "quantity": float(data["q"]), "buyer_is_maker": bool(data.get("m", False)), "market": market})
    if event == "bookTicker" or ("b" in data and "a" in data and "u" in data and not event):
        return MarketEvent(EventType.BOOK_TICKER, f"BINANCE_{market.upper()}", symbol, timestamp_ms(data.get("E")), received, {"bid": float(data["b"]), "bid_quantity": float(data.get("B", 0)), "ask": float(data["a"]), "ask_quantity": float(data.get("A", 0)), "update_id": int(data["u"]), "market": market})
    if event == "depthUpdate":
        return MarketEvent(EventType.DEPTH, f"BINANCE_{market.upper()}", symbol, timestamp_ms(data.get("E")), received, {"first_update_id": int(data["U"]), "final_update_id": int(data["u"]), "bids": [(float(p), float(q)) for p, q in data.get("b", [])], "asks": [(float(p), float(q)) for p, q in data.get("a", [])], "market": market})
    if event in {"markPriceUpdate", "forceOrder", "bookTicker"} and market == "futures":
        return MarketEvent(EventType.DERIVATIVE, "BINANCE_FUTURES", symbol, timestamp_ms(data.get("E") or data.get("T")), received, {"event": event, "mark_price": float(data["p"]) if data.get("p") else None, "funding_rate": float(data["r"]) if data.get("r") else None, "payload": data})
    return None
