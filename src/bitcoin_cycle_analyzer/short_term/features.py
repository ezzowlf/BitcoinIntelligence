from __future__ import annotations

from collections import deque
from math import log, sqrt
from statistics import mean, pstdev

from .contracts import MarketTick


class FeatureEngine:
    """Small incremental feature set; every value uses current/past ticks only."""

    def __init__(self, maxlen: int = 240):
        self.ticks: deque[MarketTick] = deque(maxlen=maxlen)

    def update(self, tick: MarketTick) -> dict[str, float | str | bool | None]:
        if tick.price <= 0:
            raise ValueError("price must be positive")
        self.ticks.append(tick)
        prices = [x.price for x in self.ticks]
        returns = [log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        short = returns[-20:]
        avg_volume = mean([x.volume for x in self.ticks]) if self.ticks else 0.0
        buy = sum(x.buy_volume or 0.0 for x in self.ticks)
        sell = sum(x.sell_volume or 0.0 for x in self.ticks)
        spread = None if tick.bid is None or tick.ask is None else max(0.0, tick.ask - tick.bid) / tick.price
        return {
            "price": tick.price,
            "return": returns[-1] if returns else 0.0,
            "momentum": (prices[-1] / prices[max(0, len(prices) - 6)] - 1.0) if prices else 0.0,
            "volatility": pstdev(short) * sqrt(len(short)) if len(short) > 1 else 0.0,
            "ema_fast": _ema(prices, min(12, len(prices))),
            "range": (max(prices[-20:]) - min(prices[-20:])) / tick.price,
            "relative_volume": (tick.volume / avg_volume) if avg_volume else 0.0,
            "volume_imbalance": (buy - sell) / max(buy + sell, 1e-12) if buy + sell else 0.0,
            "orderbook_imbalance": tick.orderbook_imbalance,
            "spread": spread,
            "sample_size": len(prices),
            "source": tick.source,
            "synthetic": tick.is_synthetic,
        }


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result
