from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAGNITUDES_USD = (100, 150, 200, 300, 400, 500, 600, 800)
ADVERSE_USD = (25, 50, 75, 100, 150, 200)
HORIZONS_SECONDS = (30, 60, 90, 120, 180, 300, 600)


@dataclass(frozen=True)
class EventClock:
    event_time: str
    receive_time: str
    processing_time: str
    source: str


@dataclass(frozen=True)
class BookSnapshot:
    timestamp: str
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]
    sequence: int
    source: str


def book_features(snapshot: BookSnapshot) -> dict[str, float]:
    bid_depth = sum(size for _, size in snapshot.bids)
    ask_depth = sum(size for _, size in snapshot.asks)
    total = bid_depth + ask_depth
    best_bid, best_ask = snapshot.bids[0][0], snapshot.asks[0][0]
    microprice = (
        (best_ask * bid_depth + best_bid * ask_depth) / total
        if total
        else (best_bid + best_ask) / 2
    )
    return {
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "depth_imbalance": 0 if not total else (bid_depth - ask_depth) / total,
        "spread": best_ask - best_bid,
        "microprice": microprice,
    }


def book_change(previous: BookSnapshot, current: BookSnapshot) -> dict[str, float]:
    if current.sequence <= previous.sequence:
        raise ValueError("order-book sequence is not strictly increasing")
    left, right = book_features(previous), book_features(current)
    return {
        "bid_pull": max(0.0, left["bid_depth"] - right["bid_depth"]),
        "ask_pull": max(0.0, left["ask_depth"] - right["ask_depth"]),
        "bid_stack": max(0.0, right["bid_depth"] - left["bid_depth"]),
        "ask_stack": max(0.0, right["ask_depth"] - left["ask_depth"]),
        "microprice_change": right["microprice"] - left["microprice"],
    }


def source_health(
    rows: int, gaps: int, duplicates: int, backwards: int, missing: int
) -> dict[str, Any]:
    status = (
        "GOOD"
        if rows > 0 and not any((gaps, duplicates, backwards, missing))
        else "UNAVAILABLE"
        if rows == 0
        else "FLAGGED"
    )
    return {
        "rows": rows,
        "gaps": gaps,
        "duplicates": duplicates,
        "backwards": backwards,
        "missing": missing,
        "status": status,
    }


def information_gain(baseline_brier: float, expanded_brier: float) -> float:
    return baseline_brier - expanded_brier


def v4_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "frequency": metrics.get("signals_per_day", 0) >= 3,
        "precision": metrics.get("precision", 0) >= 0.70,
        "positive_ev": metrics.get("net_ev", 0) > 0,
        "support": metrics.get("N", 0) >= 100,
        "folds": metrics.get("positive_folds", 0) > metrics.get("folds", 0) / 2,
        "no_catastrophe": not metrics.get("catastrophic_period", True),
        "calibrated": metrics.get("calibrated", False),
        "stable": not metrics.get("parameter_cliff", True),
    }
    return {"passed": all(checks.values()), "checks": checks}
