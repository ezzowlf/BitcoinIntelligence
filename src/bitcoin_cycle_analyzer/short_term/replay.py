from __future__ import annotations

from .contracts import MarketTick
from .engine import ShortTermEngine


def replay(ticks: list[MarketTick], engine: ShortTermEngine | None = None) -> list[dict]:
    """Run the exact engine pipeline over ordered historical ticks."""
    if any(ticks[i].exchange_timestamp > ticks[i + 1].exchange_timestamp for i in range(len(ticks) - 1)):
        raise ValueError("replay ticks must be ordered by exchange_timestamp")
    runner = engine or ShortTermEngine()
    return [forecast.to_dict() for tick in ticks for forecast in runner.process(tick, mode="REPLAY", now=tick.received_timestamp)]
