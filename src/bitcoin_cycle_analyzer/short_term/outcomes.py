from __future__ import annotations

import pandas as pd


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
