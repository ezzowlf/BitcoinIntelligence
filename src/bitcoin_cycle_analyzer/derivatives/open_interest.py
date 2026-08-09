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
    percentile = float((series <= latest).mean()); std=float(series.std())
    price_change = None
    if "price" in visible:
        prices=visible.set_index(pd.to_datetime(visible.available_at,utc=True)).price.astype(float)
        price_change=None if len(prices)<25 else float(prices.iloc[-1]/prices.iloc[-25]-1)
    oi_24h=change(1)
    divergence="UNAVAILABLE" if price_change is None or oi_24h is None else "LEVERAGE_BUILDUP" if price_change>0 and oi_24h>0 else "DELEVERAGING" if oi_24h<0 else "DIVERGENCE"
    return {"status": "AVAILABLE", "value": latest, "change_1h": change(1 / 24),
            "change_4h":change(4/24),"change_24h":oi_24h, "change_7d": change(7), "percentile": percentile,
            "zscore":0.0 if not std else float((latest-series.mean())/std),"price_oi_state":divergence,
            "level":"HIGH" if percentile>=.8 else "LOW" if percentile<=.2 else "NORMAL","factor_status":"RESEARCH",
            "provider": visible.iloc[-1].get("provider", "unknown"), "last_update": visible.iloc[-1].available_at}
