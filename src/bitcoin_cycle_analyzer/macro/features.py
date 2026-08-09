from __future__ import annotations
import pandas as pd


def macro_features(frame: pd.DataFrame | None) -> dict:
    if frame is None or frame.empty:
        return {"status": "UNAVAILABLE"}
    values=frame.sort_values("available_at").value.astype(float); latest=float(values.iloc[-1])
    def roc(n): return None if len(values)<=n else latest/float(values.iloc[-n-1])-1
    std=float(values.std())
    return {"status":"AVAILABLE","value":latest,"roc_1m":roc(1),"roc_3m":roc(3),"roc_6m":roc(6),
            "zscore":0.0 if not std else float((latest-values.mean())/std),"percentile":float((values<=latest).mean()),
            "trend":"RISING" if len(values)>1 and latest>values.iloc[-2] else "FALLING" if len(values)>1 else "UNKNOWN",
            "acceleration":None if len(values)<3 else float(values.diff().diff().iloc[-1])}
