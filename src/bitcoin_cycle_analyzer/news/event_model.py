from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd


class EventDirection(str, Enum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EventCategory(str, Enum):
    WAR = "war"
    CEASEFIRE = "ceasefire"
    SANCTIONS = "sanctions"
    OIL_SUPPLY = "oil_supply"
    FED = "fed"
    ECB = "ecb"
    INFLATION = "inflation"
    LABOR = "labor"
    BANKING_CRISIS = "banking_crisis"
    STABLECOIN = "stablecoin_risk"
    EXCHANGE_HACK = "exchange_hack"
    REGULATION = "regulation"
    ETF = "etf_news"
    SOVEREIGN = "sovereign_bitcoin"
    CORPORATE = "corporate_bitcoin"
    MINER_STRESS = "miner_stress"


@dataclass(frozen=True)
class NewsEvent:
    timestamp: pd.Timestamp
    available_at: pd.Timestamp
    category: EventCategory
    event: str
    severity: float
    direction: EventDirection
    confidence: float
    source: str

    def __post_init__(self):
        if not 0 <= self.severity <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("severity and confidence must be within 0..1")

    def to_dict(self):
        result = asdict(self)
        result["category"] = self.category.value
        result["direction"] = self.direction.value
        return result


def events_as_of(events: list[NewsEvent], as_of) -> list[NewsEvent]:
    cutoff = pd.Timestamp(as_of)
    return [event for event in events if event.available_at <= cutoff]

