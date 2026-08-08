from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time


def analyze_funding(frame: pd.DataFrame | None, as_of) -> dict:
    if frame is None or frame.empty:
        return {"status": "UNAVAILABLE", "value": None, "percentile": None, "state": "UNAVAILABLE"}
    visible = point_in_time(frame, as_of)
    if visible.empty:
        return {"status": "UNAVAILABLE", "value": None, "percentile": None, "state": "UNAVAILABLE"}
    value = float(visible.iloc[-1].value)
    percentile = float((visible.value <= value).mean())
    state = "OVERHEATED_POSITIVE" if percentile >= .95 and value > 0 else "STRONGLY_NEGATIVE" if percentile <= .05 and value < 0 else "NORMAL"
    return {"status": "AVAILABLE", "value": value, "percentile": percentile, "state": state, "provider": visible.iloc[-1].get("provider", "unknown"), "last_update": visible.iloc[-1].available_at}

