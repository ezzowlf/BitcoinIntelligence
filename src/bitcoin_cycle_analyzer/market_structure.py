from __future__ import annotations
import pandas as pd


def classify_structure(swings: pd.DataFrame) -> dict:
    if swings.empty:
        return {"trend": "unknown", "labels": [], "support": None, "resistance": None}
    labels, previous = [], {}
    for row in swings.itertuples():
        old = previous.get(row.kind)
        label = row.kind.upper() if old is None else ("HH" if row.kind == "high" and row.price > old else "LH" if row.kind == "high" else "LL" if row.price < old else "HL")
        labels.append(label)
        previous[row.kind] = row.price
    recent = labels[-4:]
    trend = "bullish" if "HH" in recent and "HL" in recent else "bearish" if "LL" in recent and "LH" in recent else "corrective"
    lows = swings[swings.kind == "low"].price
    highs = swings[swings.kind == "high"].price
    return {"trend": trend, "labels": labels, "support": None if lows.empty else float(lows.iloc[-1]), "resistance": None if highs.empty else float(highs.iloc[-1])}

