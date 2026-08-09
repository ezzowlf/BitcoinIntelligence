from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from .event_model import NewsEvent, EventCategory, EventDirection, BtcDirection

CATEGORY_ALIASES={"ENERGY_SHOCK":"ENERGY","BANKING":"BANKING_CRISIS","CORPORATE_BTC":"CORPORATE",
                  "GOVERNMENT_BTC":"SOVEREIGN","MINER":"MINER_STRESS","LIQUIDITY":"FED"}


def parse_meanpulse_event(payload: dict) -> NewsEvent:
    required={"event_id","event_time","available_at","category","severity","risk_direction","btc_direction","confidence","source"}
    missing=required-payload.keys()
    if missing: raise ValueError(f"missing fields: {sorted(missing)}")
    category=CATEGORY_ALIASES.get(str(payload["category"]).upper(),str(payload["category"]).upper())
    return NewsEvent(timestamp=pd.Timestamp(payload["event_time"]),available_at=pd.Timestamp(payload["available_at"]),
                     category=EventCategory[category],event=str(payload["event_id"]),severity=float(payload["severity"]),
                     direction=EventDirection(str(payload["risk_direction"]).lower()),confidence=float(payload["confidence"]),
                     source=str(payload["source"]),btc_direction=BtcDirection(str(payload["btc_direction"]).lower()),
                     market_scope=tuple(payload.get("market_scope", [])))


def load_meanpulse_jsonl(path: str | Path, as_of=None) -> list[NewsEvent]:
    events=[parse_meanpulse_event(json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return events if as_of is None else [event for event in events if event.available_at<=pd.Timestamp(as_of)]
