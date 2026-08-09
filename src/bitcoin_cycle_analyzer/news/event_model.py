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
    GEOPOLITICAL = "geopolitical"
    WAR_ESCALATION = "war_escalation"
    DEESCALATION = "deescalation"
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
    ENERGY = "energy"


class BtcDirection(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


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
    btc_direction: BtcDirection = BtcDirection.UNKNOWN
    market_scope: tuple[str, ...] = ()

    def __post_init__(self):
        if not 0 <= self.severity <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("severity and confidence must be within 0..1")

    def to_dict(self):
        result = asdict(self)
        result["category"] = self.category.value
        result["direction"] = self.direction.value
        result["btc_direction"] = self.btc_direction.value
        return result


def events_as_of(events: list[NewsEvent], as_of) -> list[NewsEvent]:
    cutoff = pd.Timestamp(as_of)
    return [event for event in events if event.available_at <= cutoff]


DEFAULT_HALF_LIVES_HOURS={"exchange_hack":6,"stablecoin_risk":24,"war":168,"war_escalation":168,
                          "geopolitical":168,"regulation":336,"fed":72,"ecb":72,"inflation":48,"labor":48,
                          "energy":96,"sanctions":168}


def decay_weight(event: NewsEvent, as_of, half_lives_hours: dict[str,float] | None=None) -> float:
    import math
    defaults=DEFAULT_HALF_LIVES_HOURS.copy()
    defaults.update(half_lives_hours or {})
    age=(pd.Timestamp(as_of)-event.available_at).total_seconds()/3600
    if age < 0:
        return 0.0
    half_life=defaults.get(event.category.value,48)
    return event.severity*event.confidence*math.pow(.5,age/half_life)
