from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time


def analyze_funding(frame: pd.DataFrame | None, as_of) -> dict:
    if frame is None or frame.empty:
        return {"status": "UNAVAILABLE", "value": None, "percentile": None, "state": "UNAVAILABLE"}
    visible = point_in_time(frame, as_of)
    if visible.empty:
        return {"status": "UNAVAILABLE", "value": None, "percentile": None, "state": "UNAVAILABLE"}
    series = visible.set_index(pd.to_datetime(visible.available_at, utc=True)).value.astype(float).sort_index()
    value = float(series.iloc[-1])
    percentile = float((series <= value).mean())
    std = float(series.std())
    zscore = 0.0 if not std else float((value - series.mean()) / std)
    daily = series.resample("1D").mean().dropna()
    mean_24h = float(series.loc[series.index >= series.index[-1] - pd.Timedelta(days=1)].mean())
    mean_7d = float(series.loc[series.index >= series.index[-1] - pd.Timedelta(days=7)].mean())
    state = ("OVERHEATED" if percentile >= .95 and value > 0 else
             "POSITIVE" if value > .0001 else "STRONGLY_NEGATIVE" if percentile <= .05 and value < 0 else
             "NEGATIVE" if value < -.0001 else "NEUTRAL")
    persistence = int((daily.tail(14) > 0).sum()) if value >= 0 else int((daily.tail(14) < 0).sum())
    return {"status": "AVAILABLE", "value": value, "mean_24h": mean_24h, "mean_7d": mean_7d,
            "percentile": percentile, "zscore": zscore, "persistence_days": persistence,
            "state": state, "provider": visible.iloc[-1].get("provider", "unknown"),
            "last_update": visible.iloc[-1].available_at}
