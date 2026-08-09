from __future__ import annotations
from dataclasses import dataclass, asdict
import pandas as pd


@dataclass(frozen=True)
class MacroObservation:
    metric: str
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    observation_value: float
    release_time: pd.Timestamp
    available_at: pd.Timestamp
    revision_id: str
    provider: str

    def to_dict(self) -> dict:
        return asdict(self)
