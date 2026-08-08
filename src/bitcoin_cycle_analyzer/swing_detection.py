from __future__ import annotations
import pandas as pd


def detect_swings(frame: pd.DataFrame, window: int = 8, min_atr_move: float = 1.5) -> pd.DataFrame:
    """Confirmed pivots only: a pivot at t becomes known at t+window."""
    highs = frame.high.rolling(2 * window + 1, center=True).max()
    lows = frame.low.rolling(2 * window + 1, center=True).min()
    candidates = []
    for pos in range(window, len(frame) - window):
        kind = "high" if frame.high.iloc[pos] >= highs.iloc[pos] else "low" if frame.low.iloc[pos] <= lows.iloc[pos] else None
        if kind:
            candidates.append({"pivot_time": frame.index[pos], "confirmed_at": frame.index[pos + window], "kind": kind, "price": float(frame[kind].iloc[pos]), "position": pos})
    accepted = []
    for item in candidates:
        if accepted and accepted[-1]["kind"] == item["kind"]:
            better = item["price"] > accepted[-1]["price"] if item["kind"] == "high" else item["price"] < accepted[-1]["price"]
            if better:
                accepted[-1] = item
            continue
        if accepted:
            atr = frame.get("atr_14", pd.Series(index=frame.index, dtype=float)).iloc[item["position"]]
            if pd.notna(atr) and abs(item["price"] - accepted[-1]["price"]) < min_atr_move * atr:
                continue
        accepted.append(item)
    return pd.DataFrame(accepted)


def swings_as_of(swings: pd.DataFrame, timestamp: pd.Timestamp) -> pd.DataFrame:
    if swings.empty:
        return swings.copy()
    return swings[swings.confirmed_at <= timestamp].copy()

