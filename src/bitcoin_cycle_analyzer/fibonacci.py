from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

RETRACEMENTS = (0.236, 0.382, 0.5, 0.618, 0.705, 0.786)
EXTENSIONS = (1.272, 1.618, 2.0, 2.618)


@dataclass(frozen=True)
class FibLevel:
    ratio: float
    price: float
    anchor_low: float
    anchor_high: float
    kind: str


def levels(low: float, high: float, direction: str = "up") -> list[FibLevel]:
    if high <= low:
        raise ValueError("high must exceed low")
    distance = high - low
    retr = [FibLevel(r, high - r * distance if direction == "up" else low + r * distance, low, high, "retracement") for r in RETRACEMENTS]
    ext = [FibLevel(r, low + r * distance if direction == "up" else high - r * distance, low, high, "extension") for r in EXTENSIONS]
    return retr + ext


def from_swings(swings: pd.DataFrame, max_legs: int = 5) -> list[FibLevel]:
    output = []
    for left, right in zip(swings.iloc[-max_legs - 1:-1].itertuples(), swings.iloc[-max_legs:].itertuples()):
        if left.kind == right.kind:
            continue
        low, high = sorted((left.price, right.price))
        output.extend(levels(low, high, "up" if left.kind == "low" else "down"))
    return output


def confluence_zones(all_levels: list[FibLevel], tolerance_pct: float = 0.015, minimum: int = 2) -> list[dict]:
    prices = sorted(x.price for x in all_levels if x.kind == "retracement" and x.price > 0)
    zones, cluster = [], []
    for price in prices:
        if not cluster or abs(price / np.mean(cluster) - 1) <= tolerance_pct:
            cluster.append(price)
        else:
            if len(cluster) >= minimum:
                zones.append({"low": min(cluster), "high": max(cluster), "center": float(np.mean(cluster)), "count": len(cluster)})
            cluster = [price]
    if len(cluster) >= minimum:
        zones.append({"low": min(cluster), "high": max(cluster), "center": float(np.mean(cluster)), "count": len(cluster)})
    return sorted(zones, key=lambda z: z["count"], reverse=True)
