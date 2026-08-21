from __future__ import annotations

import pandas as pd


def resolve_vantage_path(candidate: dict, ticks: pd.DataFrame, *, target: float, adverse: float, horizon: int) -> dict:
    """Resolve one candidate against the persisted future Vantage bid/ask path.

    Entry is executable: LONG enters at ask and exits against bid; SHORT enters
    at bid and exits against ask.  The path is strictly after the candidate.
    """
    if target <= 0 or adverse <= 0 or horizon <= 0:
        raise ValueError("target, adverse and horizon must be positive")
    start = pd.Timestamp(candidate["timestamp"])
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    end = start + pd.Timedelta(seconds=horizon)
    path = ticks.copy()
    if not isinstance(path.index, pd.DatetimeIndex):
        if "timestamp" not in path:
            raise TypeError("ticks require a DatetimeIndex or timestamp column")
        path.index = pd.to_datetime(path["timestamp"], utc=True)
    path.index = pd.to_datetime(path.index, utc=True)
    path = path.sort_index()
    available_until = path.index.max() if not path.empty else None
    path = path.loc[(path.index > start) & (path.index <= end)].dropna(subset=["bid", "ask"])
    if path.empty or available_until is None or available_until < end:
        return {"status": "INSUFFICIENT_DATA", "target_first": None, "adverse_first": None, "mfe": None, "mae": None,
                "time_to_target": None, "time_to_adverse": None, "remaining_move": None}
    entry = float(candidate.get("entry_price") or candidate.get("ask" if candidate.get("direction") == "LONG" else "bid"))
    direction = str(candidate.get("direction", "LONG")).upper()
    if direction == "LONG":
        favorable = path["bid"].astype(float) - entry
        unfavorable = entry - path["bid"].astype(float)
        target_hit = favorable >= target
        adverse_hit = unfavorable >= adverse
        remaining = target - float(favorable.iloc[-1])
    elif direction == "SHORT":
        favorable = entry - path["ask"].astype(float)
        unfavorable = path["ask"].astype(float) - entry
        target_hit = favorable >= target
        adverse_hit = unfavorable >= adverse
        remaining = target - float(favorable.iloc[-1])
    else:
        raise ValueError("direction must be LONG or SHORT")
    target_time = path.index[target_hit.argmax()] if target_hit.any() else None
    adverse_time = path.index[adverse_hit.argmax()] if adverse_hit.any() else None
    return {"status": "RESOLVED", "target_first": bool(target_time is not None and (adverse_time is None or target_time <= adverse_time)),
            "adverse_first": bool(adverse_time is not None and (target_time is None or adverse_time < target_time)),
            "mfe": float(favorable.max()), "mae": -float(unfavorable.max()),
            "time_to_target": None if target_time is None else (target_time - start).total_seconds(),
            "time_to_adverse": None if adverse_time is None else (adverse_time - start).total_seconds(),
            "remaining_move": float(remaining)}


def label_horizons(frame: pd.DataFrame, horizons=(30, 60, 180, 300, 600, 900, 1800, 3600), price_column: str = "close") -> pd.DataFrame:
    """Create causal labels; future prices are labels and never features."""
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("frame index must be a DatetimeIndex")
    if price_column not in frame:
        raise ValueError(f"missing {price_column}")
    result = frame.copy()
    for seconds in horizons:
        targets = result.index + pd.to_timedelta(seconds, unit="s")
        positions = result.index.searchsorted(targets, side="left")
        values = [
            (float(result[price_column].iloc[position]) / float(price) - 1.0)
            if position < len(result) else float("nan")
            for position, price in zip(positions, result[price_column])
        ]
        result[f"return_{seconds}s"] = values
    return result
