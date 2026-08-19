from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

HORIZONS_SECONDS = (30, 60, 180, 300, 600, 900, 1800, 3600)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SetupState(str, Enum):
    NEUTRAL = "NEUTRAL"
    WATCH = "WATCH"
    ARMED = "ARMED"
    SIGNAL = "SIGNAL"
    EXIT = "EXIT"
    WATCH_CANCELLED = "WATCH_CANCELLED"
    SIGNAL_INVALIDATED = "SIGNAL_INVALIDATED"


@dataclass(frozen=True)
class MarketTick:
    price: float
    exchange_timestamp: datetime
    received_timestamp: datetime
    processed_timestamp: datetime | None = None
    source: str = "unknown"
    volume: float = 0.0
    buy_volume: float | None = None
    sell_volume: float | None = None
    bid: float | None = None
    ask: float | None = None
    orderbook_imbalance: float | None = None
    is_synthetic: bool = False

    def latencies(self, prediction_timestamp: datetime | None = None) -> dict[str, float]:
        processed = _utc(self.processed_timestamp or self.received_timestamp)
        prediction = _utc(prediction_timestamp or processed)
        exchange = _utc(self.exchange_timestamp)
        received = _utc(self.received_timestamp)
        return {
            "network_latency": max(0.0, (received - exchange).total_seconds()),
            "processing_latency": max(0.0, (processed - received).total_seconds()),
            "end_to_end_latency": max(0.0, (prediction - exchange).total_seconds()),
        }

    def age_seconds(self, now: datetime | None = None) -> float:
        return max(0.0, (_utc(now or utc_now()) - _utc(self.exchange_timestamp)).total_seconds())


@dataclass(frozen=True)
class Costs:
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    spread_cost: float = 0.0
    slippage_estimate: float = 0.0002

    @property
    def round_trip(self) -> float:
        return 2 * self.taker_fee + self.spread_cost + self.slippage_estimate


@dataclass(frozen=True)
class ModelOutput:
    model: str
    horizon_seconds: int
    p_up: float
    p_down: float
    p_no_move: float
    expected_return: float
    confidence: float
    reasons: tuple[str, ...] = ()
    available: bool = True

    def __post_init__(self) -> None:
        values = (self.p_up, self.p_down, self.p_no_move, self.confidence)
        if any(not 0.0 <= float(x) <= 1.0 for x in values):
            raise ValueError("probabilities and confidence must be between 0 and 1")


@dataclass(frozen=True)
class Forecast:
    timestamp: datetime
    horizon_seconds: int
    p_up: float
    p_down: float
    p_no_move: float
    expected_return: float
    expected_move: float
    confidence: float
    uncertainty: float
    state: SetupState
    quality: str
    model_agreement: float
    reasons: tuple[str, ...] = ()
    latency: dict[str, float] = field(default_factory=dict)
    mode: str = "LIVE"
    execution: str = "DISABLED"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["timestamp"] = self.timestamp.isoformat()
        value["state"] = self.state.value
        return value
