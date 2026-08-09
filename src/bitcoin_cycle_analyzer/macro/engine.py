from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time
from .features import macro_features

MACRO_METRICS = ("fed_funds", "fed_expectations", "us_2y", "us_10y", "real_yields", "dxy", "cpi", "core_cpi", "pce", "nonfarm_payrolls", "unemployment", "gdp", "fed_balance_sheet", "global_liquidity", "m2", "nasdaq", "sp500", "gold", "oil", "stablecoin_supply")


def analyze_macro(series: dict[str, pd.DataFrame] | None, as_of) -> dict:
    series = series or {}
    metrics = {}
    for metric in MACRO_METRICS:
        frame = series.get(metric)
        if frame is None or frame.empty:
            metrics[metric] = {"status": "UNAVAILABLE"}
            continue
        visible = point_in_time(frame, as_of)
        if visible.empty:
            metrics[metric] = {"status": "UNAVAILABLE"}
        else:
            row = visible.sort_values("available_at").iloc[-1]
            metrics[metric] = {**macro_features(visible), "observed_at": row.get("observed_at"), "available_at": row.available_at, "provider": row.get("provider", "unknown")}
    available = sum(value["status"] == "AVAILABLE" for value in metrics.values())
    states={"usd":"UNAVAILABLE","rates":"UNAVAILABLE","inflation":"UNAVAILABLE","labor":"UNAVAILABLE","liquidity":"UNAVAILABLE","equities":"UNAVAILABLE","commodities":"UNAVAILABLE"}
    if metrics["dxy"]["status"]=="AVAILABLE": states["usd"]="STRONG" if metrics["dxy"]["zscore"]>.5 else "WEAK" if metrics["dxy"]["zscore"]<-.5 else "NEUTRAL"
    if metrics["us_2y"]["status"]=="AVAILABLE": states["rates"]="RESTRICTIVE" if metrics["us_2y"]["trend"]=="RISING" else "EASING"
    known=[value for value in states.values() if value!="UNAVAILABLE"]
    return {"status":"AVAILABLE" if available else "UNAVAILABLE","reason":None if available else "FRED_API_KEY_MISSING_OR_NO_RELEASES","score":None,"coverage":available/len(MACRO_METRICS),
            "state":{**states,"overall":"MIXED" if known else "UNAVAILABLE","confidence":round(available/len(MACRO_METRICS),2)},
            "metrics":metrics,"note":"Macro state is context, not a BTC buy/sell signal."}
