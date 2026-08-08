from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import pandas as pd


class DataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MetricObservation:
    metric: str
    value: Any
    observed_at: pd.Timestamp | None
    available_at: pd.Timestamp | None
    provider: str
    status: DataStatus
    expected_delay_seconds: int = 0
    source_url: str | None = None
    note: str | None = None

    def visible_as_of(self, as_of) -> bool:
        return self.available_at is not None and pd.Timestamp(self.available_at) <= pd.Timestamp(as_of)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["status"] = self.status.value
        return result


def unavailable(metric: str, provider: str = "not configured", note: str | None = None) -> MetricObservation:
    return MetricObservation(metric, None, None, None, provider, DataStatus.UNAVAILABLE, note=note)


def freshness(observed_at, expected_delay_seconds: int, now=None) -> dict:
    if observed_at is None:
        return {"status": DataStatus.UNAVAILABLE.value, "age_seconds": None}
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    observed = pd.Timestamp(observed_at)
    if observed.tzinfo is None:
        observed = observed.tz_localize("UTC")
    age = max(0, int((now - observed).total_seconds()))
    status = DataStatus.AVAILABLE if age <= expected_delay_seconds else DataStatus.DELAYED if age <= expected_delay_seconds * 3 else DataStatus.STALE
    return {"status": status.value, "age_seconds": age, "observed_at": observed, "checked_at": now}


def point_in_time(frame: pd.DataFrame, as_of, available_column: str = "available_at") -> pd.DataFrame:
    if available_column not in frame:
        raise ValueError(f"missing {available_column}")
    available = pd.to_datetime(frame[available_column], utc=True)
    return frame.loc[available <= pd.Timestamp(as_of)].copy()
