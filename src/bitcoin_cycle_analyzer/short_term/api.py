from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from .contracts import Forecast


@dataclass(frozen=True)
class ForecastSnapshot:
    mode: str
    generated_at: str
    state: str
    forecasts: list[dict[str, Any]]
    feeds: dict[str, dict]
    price: float | None
    data_age_seconds: float | None
    execution: str = "DISABLED"

    @classmethod
    def from_forecasts(cls, forecasts: list[Forecast], mode: str, feeds: dict, price: float | None, data_age_seconds: float | None):
        generated = forecasts[0].timestamp.isoformat() if forecasts else datetime.now(UTC).isoformat()
        state = forecasts[0].state.value if forecasts else "NEUTRAL"
        return cls(mode, generated, state, [x.to_dict() for x in forecasts], feeds, price, data_age_seconds)

    def to_dict(self) -> dict:
        return asdict(self)
