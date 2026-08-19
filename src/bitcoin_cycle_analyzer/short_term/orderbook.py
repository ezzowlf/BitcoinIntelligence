from __future__ import annotations

from dataclasses import dataclass, field

from .events import EventType, MarketEvent


@dataclass
class OrderBookState:
    last_update_id: int | None = None
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    synchronized: bool = False
    gap_count: int = 0

    def apply(self, event: MarketEvent) -> str:
        if event.event_type != EventType.DEPTH:
            return "IGNORED"
        first = event.payload["first_update_id"]
        final = event.payload["final_update_id"]
        if self.last_update_id is None:
            return "NEEDS_SNAPSHOT"
        if final <= self.last_update_id:
            return "STALE"
        if first > self.last_update_id + 1:
            self.synchronized = False
            self.gap_count += 1
            return "GAP"
        for price, quantity in event.payload["bids"]:
            (self.bids.pop(price, None) if quantity == 0 else self.bids.__setitem__(price, quantity))
        for price, quantity in event.payload["asks"]:
            (self.asks.pop(price, None) if quantity == 0 else self.asks.__setitem__(price, quantity))
        self.last_update_id = final
        self.synchronized = True
        return "APPLIED"

    def seed_snapshot(self, last_update_id: int, bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> None:
        self.last_update_id = last_update_id
        self.bids = {p: q for p, q in bids if q > 0}
        self.asks = {p: q for p, q in asks if q > 0}
        self.synchronized = True

    def imbalance(self, levels: int = 10) -> float | None:
        if not self.synchronized:
            return None
        bid = sum(q for _, q in sorted(self.bids.items(), reverse=True)[:levels])
        ask = sum(q for _, q in sorted(self.asks.items())[:levels])
        return (bid - ask) / max(bid + ask, 1e-12)
