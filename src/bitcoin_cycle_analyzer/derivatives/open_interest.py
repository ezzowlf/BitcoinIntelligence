from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time


def analyze_open_interest(frame: pd.DataFrame | None, as_of) -> dict:
    if frame is None or frame.empty:
        return {"status": "UNAVAILABLE", "value": None}
    visible = point_in_time(frame, as_of)
    if visible.empty:
        return {"status": "UNAVAILABLE", "value": None}
    series = visible.set_index(pd.to_datetime(visible.available_at, utc=True)).value.astype(float)
    latest = float(series.iloc[-1])
    def change(days):
        past = series.loc[:series.index[-1] - pd.Timedelta(days=days)]
        return None if past.empty else latest / float(past.iloc[-1]) - 1
    percentile = float((series <= latest).mean())
    return {"status": "AVAILABLE", "value": latest, "change_1h": change(1 / 24),
            "change_24h": change(1), "change_7d": change(7), "percentile": percentile,
            "provider": visible.iloc[-1].get("provider", "unknown"), "last_update": visible.iloc[-1].available_at}
