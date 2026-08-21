"""Holdout-safe WAVERUN V5 contracts.

This module deliberately contains no trading or execution code.  It provides
the small, immutable vocabulary needed to record new information before any
model is allowed to claim an edge.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

EXECUTION = "DISABLED"
MAGNITUDES_USD = (100, 150, 200, 300, 400, 500, 600, 800)
ADVERSE_USD = (25, 50, 75, 100, 150, 200)
HORIZONS_SECONDS = (30, 60, 90, 120, 180, 300, 600)
FINAL_HOLDOUT = frozenset({date(2026, 8, 16), date(2026, 8, 17)})


class HoldoutLockedError(RuntimeError):
    """Raised when exploratory code attempts to read the final holdout."""


@dataclass(frozen=True)
class EventClock:
    event_time: str
    receive_time: str
    processing_time: str
    source: str


@dataclass(frozen=True)
class BarrierTarget:
    magnitude_usd: int
    adverse_usd: int
    horizon_seconds: int

    def __post_init__(self) -> None:
        if self.magnitude_usd not in MAGNITUDES_USD or self.adverse_usd not in ADVERSE_USD:
            raise ValueError("target/adverse value is outside the V5 research grid")
        if self.horizon_seconds not in HORIZONS_SECONDS:
            raise ValueError("horizon is outside the V5 research grid")


@dataclass(frozen=True)
class Evidence:
    group: str
    name: str
    value: float | str | bool
    source: str
    clock: EventClock


@dataclass(frozen=True)
class MarketState:
    timestamp: str
    symbol: str
    price: float
    evidence: tuple[Evidence, ...] = ()
    contradictions: tuple[str, ...] = ()
    execution: str = EXECUTION


@dataclass(frozen=True)
class BarrierOutcome:
    target: BarrierTarget
    direction: str
    target_first: bool | None
    time_to_target_seconds: float | None
    time_to_adverse_seconds: float | None
    status: str


def assert_holdout_locked(days: Iterable[date], *, candidate_frozen: bool = False) -> None:
    requested = FINAL_HOLDOUT.intersection(days)
    if requested and not candidate_frozen:
        raise HoldoutLockedError(f"final holdout is locked: {sorted(requested)}")


def fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def gate(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "three_opportunities_at_70": metrics.get("signals_per_day", 0) >= 3 and metrics.get("precision", 0) >= .70,
        "positive_net_ev": metrics.get("net_ev", 0) > 0,
        "adequate_n": metrics.get("N", 0) >= 100,
        "majority_positive_folds": metrics.get("positive_folds", 0) > metrics.get("folds", 0) / 2,
        "calibrated": metrics.get("calibrated", False) is True,
        "stable_parameters": metrics.get("parameter_cliff", True) is False,
    }
    return {"passed": all(checks.values()), "checks": checks, "execution": EXECUTION}


def append_jsonl(path: str, payload: dict[str, Any]) -> str:
    """Append an immutable, content-addressed research record."""
    record = {"recorded_at": datetime.now(UTC).isoformat(), "execution": EXECUTION, **payload}
    record["record_id"] = fingerprint(record)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record["record_id"]
