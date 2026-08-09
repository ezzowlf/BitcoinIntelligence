from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class MT5Quote:
    source: str
    symbol: str
    bid: float
    ask: float
    timestamp: pd.Timestamp
    timeframe: str

    def __post_init__(self):
        if self.source != "mt5" or self.bid<=0 or self.ask<self.bid: raise ValueError("invalid MT5 quote")


@dataclass(frozen=True)
class MeanPulseInput:
    service: str
    symbol: str
    h4_alignment: str
    rejection: bool
    reclaim: bool
    entry_readiness: float
    confidence: float

    def __post_init__(self):
        if self.service!="meanpulse" or not 0<=self.entry_readiness<=100 or not 0<=self.confidence<=100: raise ValueError("invalid MeanPulse input")
