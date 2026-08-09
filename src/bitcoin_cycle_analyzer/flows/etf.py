from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time


def analyze_etf_flows(frame: pd.DataFrame | None, as_of) -> dict:
    if frame is None or frame.empty:
        return {"status": "UNAVAILABLE", "reason":"NO_LICENSED_POINT_IN_TIME_PROVIDER", "score": None, "provider": "not configured", "note": "No licensed point-in-time ETF flow feed configured"}
    visible = point_in_time(frame, as_of).sort_values("available_at")
    if visible.empty:
        return {"status": "UNAVAILABLE", "score": None}
    flows = visible.net_flow_usd.astype(float)
    daily, five, twenty, cumulative = float(flows.iloc[-1]), float(flows.tail(5).sum()), float(flows.tail(20).sum()), float(flows.sum())
    acceleration = five - float(flows.iloc[-10:-5].sum()) if len(flows) >= 10 else None
    state = "STRONG_ACCUMULATION" if five > 0 and twenty > 0 and (acceleration is None or acceleration > 0) else "INSTITUTIONAL_SELLING" if five < 0 and twenty < 0 else "NEUTRAL"
    score = 75 if state == "STRONG_ACCUMULATION" else 25 if state == "INSTITUTIONAL_SELLING" else 50
    return {"status": "AVAILABLE", "score": score, "daily": daily, "five_day": five, "twenty_day": twenty, "cumulative": cumulative, "acceleration": acceleration, "state": state, "provider": visible.iloc[-1].get("provider", "unknown"), "last_update": visible.iloc[-1].available_at}
