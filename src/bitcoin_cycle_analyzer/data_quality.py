from __future__ import annotations
import numpy as np
import pandas as pd


def quality_report(frame: pd.DataFrame, timeframe: str, gap_threshold: float = .35, volume_z: float = 8.0) -> dict:
    expected = {"4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1), "1w": pd.Timedelta(days=7)}.get(timeframe)
    idx = frame.index
    duplicate_count = int(idx.duplicated().sum())
    monotonic = bool(idx.is_monotonic_increasing)
    timezone = str(idx.tz) if isinstance(idx, pd.DatetimeIndex) else None
    gaps = []
    if expected is not None and len(idx) > 1:
        deltas = idx.to_series().diff()
        gaps = [{"after": str(date - delta), "before": str(date), "missing_intervals": int(delta / expected) - 1} for date, delta in deltas[deltas > expected].items()]
    previous = frame.close.shift(1)
    gap_return = frame.open / previous - 1
    log_volume = np.log1p(frame.volume)
    rolling_mean = log_volume.rolling(90, min_periods=30).mean()
    rolling_std = log_volume.rolling(90, min_periods=30).std().replace(0, np.nan)
    volume_outliers = ((log_volume - rolling_mean).abs() / rolling_std > volume_z)
    sources = frame["provider"].astype(str) if "provider" in frame else pd.Series("unknown", index=idx)
    switches = sources.ne(sources.shift())
    switch_rows = [{"timestamp": str(ts), "provider": sources.loc[ts]} for ts in idx[switches][1:]]
    issues = {
        "duplicate_timestamps": duplicate_count,
        "non_monotonic": not monotonic,
        "timezone": timezone,
        "zero_prices": int((frame[["open", "high", "low", "close"]] == 0).any(axis=1).sum()),
        "negative_prices": int((frame[["open", "high", "low", "close"]] < 0).any(axis=1).sum()),
        "high_below_low": int((frame.high < frame.low).sum()),
        "open_outside_range": int(((frame.open > frame.high) | (frame.open < frame.low)).sum()),
        "close_outside_range": int(((frame.close > frame.high) | (frame.close < frame.low)).sum()),
        "extreme_gaps": [{"timestamp": str(ts), "gap": float(value)} for ts, value in gap_return[gap_return.abs() > gap_threshold].items()],
        "volume_outliers": [str(ts) for ts in frame.index[volume_outliers.fillna(False)]],
        "missing_periods": gaps,
        "provider_switches": switch_rows,
    }
    critical = duplicate_count + int(not monotonic) + issues["zero_prices"] + issues["negative_prices"] + issues["high_below_low"] + issues["open_outside_range"] + issues["close_outside_range"]
    return {"timeframe": timeframe, "rows": len(frame), "from": None if frame.empty else str(idx.min()), "to": None if frame.empty else str(idx.max()), "critical_issue_count": critical, "issues": issues, "repairs_applied": []}
