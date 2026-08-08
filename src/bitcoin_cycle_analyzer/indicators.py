from __future__ import annotations
import numpy as np
import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"]
    for span in (20, 50, 100, 200):
        out[f"ema_{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    out["sma_200"] = close.rolling(200, min_periods=200).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi_14"] = (100 - 100 / (1 + rs)).fillna(100).where(gain.notna())
    previous = close.shift(1)
    true_range = pd.concat([(out.high - out.low), (out.high - previous).abs(), (out.low - previous).abs()], axis=1).max(axis=1)
    out["atr_14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    out["volume_sma_20"] = out.volume.rolling(20, min_periods=20).mean()
    out["volume_ratio"] = out.volume / out.volume_sma_20.replace(0, np.nan)
    out["ath"] = close.cummax()
    out["drawdown"] = close / out.ath - 1
    out["return_30"] = close.pct_change(30)
    out["volatility_30"] = close.pct_change().rolling(30, min_periods=20).std()
    return out

