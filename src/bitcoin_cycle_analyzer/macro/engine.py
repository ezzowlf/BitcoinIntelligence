from __future__ import annotations
import pandas as pd
from ..data_contracts import point_in_time

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
            metrics[metric] = {"status": "AVAILABLE", "value": float(row.value), "observed_at": row.get("observed_at"), "available_at": row.available_at, "provider": row.get("provider", "unknown")}
    available = sum(value["status"] == "AVAILABLE" for value in metrics.values())
    return {"status": "AVAILABLE" if available else "UNAVAILABLE", "score": None, "coverage": available / len(MACRO_METRICS), "metrics": metrics, "note": "Macro correlations require point-in-time backtesting; no fixed causal sign is assumed."}

