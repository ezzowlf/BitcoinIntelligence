from __future__ import annotations
import numpy as np
import pandas as pd

FEATURES = ["drawdown", "rsi_14", "ema_distance", "atr_pct", "volume_ratio", "return_30", "volatility_30"]


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["ema_distance"] = out.close / out.ema_200 - 1
    out["atr_pct"] = out.atr_14 / out.close
    return out[FEATURES].replace([np.inf, -np.inf], np.nan)


def find_similar(frame: pd.DataFrame, as_of=None, neighbors: int = 30, exclusion_days: int = 730, min_history_days: int = 365, min_case_spacing_days: int = 30) -> pd.DataFrame:
    cutoff = frame.index[-1] if as_of is None else pd.Timestamp(as_of)
    history = frame.loc[:cutoff]
    features = feature_frame(history)
    if features.empty or features.iloc[-1].isna().any():
        return pd.DataFrame(columns=["date", "similarity"])
    earliest = history.index[0] + pd.Timedelta(days=min_history_days)
    latest = cutoff - pd.Timedelta(days=exclusion_days)
    candidates = features.loc[earliest:latest].dropna()
    if candidates.empty:
        return pd.DataFrame(columns=["date", "similarity"])
    scale = candidates.std().replace(0, 1)
    distance = (((candidates - features.iloc[-1]) / scale) ** 2).mean(axis=1) ** 0.5
    selected = []
    spacing = pd.Timedelta(days=min_case_spacing_days)
    for date, value in distance.sort_values().items():
        if all(abs(date - chosen[0]) >= spacing for chosen in selected):
            selected.append((date, value))
        if len(selected) >= neighbors:
            break
    return pd.DataFrame({"date": [x[0] for x in selected], "similarity": [100 / (1 + x[1]) for x in selected], "distance": [x[1] for x in selected]}).set_index("date")


def evidence_label(sample_size: int) -> str:
    if sample_size < 5:
        return "sehr geringe Evidenz"
    if sample_size < 10:
        return "geringe Evidenz"
    if sample_size < 20:
        return "moderate Evidenz"
    return "höhere historische Evidenz"


def forward_returns(frame: pd.DataFrame, dates, horizons=(7, 30, 90, 180, 365, 730)) -> pd.DataFrame:
    rows = []
    for date in dates:
        pos = frame.index.get_indexer([date], method="nearest")[0]
        entry = frame.close.iloc[pos]
        row = {"date": frame.index[pos]}
        for days in horizons:
            target = frame.index[pos] + pd.Timedelta(days=days)
            target_pos = frame.index.searchsorted(target)
            row[f"return_{days}d"] = np.nan if target_pos >= len(frame) else frame.close.iloc[target_pos] / entry - 1
            future = frame.iloc[pos + 1:min(target_pos + 1, len(frame))]
            row[f"max_drawdown_{days}d"] = np.nan if future.empty else future.low.min() / entry - 1
        rows.append(row)
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def summarize_forward(returns: pd.DataFrame, horizon: int) -> dict:
    if f"return_{horizon}d" not in returns.columns:
        return {"count": 0}
    values = returns[f"return_{horizon}d"].dropna()
    dd = returns[f"max_drawdown_{horizon}d"].dropna()
    if values.empty:
        return {"count": 0}
    return {"count": len(values), "positive": int((values > 0).sum()), "negative": int((values <= 0).sum()), "win_rate": float((values > 0).mean()), "median": float(values.median()), "mean": float(values.mean()), "min": float(values.min()), "max": float(values.max()), "q10": float(values.quantile(.1)), "q25": float(values.quantile(.25)), "q75": float(values.quantile(.75)), "q90": float(values.quantile(.9)), "worst_drawdown": float(dd.min()) if not dd.empty else None}
