from __future__ import annotations
import numpy as np
import pandas as pd


def sequence_analogues(frame:pd.DataFrame,as_of=None,window=90,top_n=12,spacing_days=120)->dict:
    data=frame.loc[:pd.Timestamp(as_of)] if as_of is not None else frame; close=data.close.astype(float); returns=close.pct_change().fillna(0)
    if len(data)<window*3: return {"status":"UNAVAILABLE","analogues":[],"independent_episodes":0,"dispersion":None}
    current=np.asarray(close.iloc[-window:]/close.iloc[-window]-1); candidates=[]; last_selected=None
    for end in range(window,len(close)-365,7):
        path=np.asarray(close.iloc[end-window:end]/close.iloc[end-window]-1); similarity=max(0,1-float(np.sqrt(np.mean((current-path)**2))))
        candidates.append((similarity,end))
    selected=[]
    for similarity,end in sorted(candidates,reverse=True):
        date=close.index[end]
        if all(abs((date-item["date"]).days)>=spacing_days for item in selected):
            future=close.iloc[end+365]/close.iloc[end]-1; segment=close.iloc[end:end+366]/close.iloc[end]-1
            selected.append({"date":date,"similarity":round(similarity,4),"forward_30d":float(close.iloc[end+30]/close.iloc[end]-1),"forward_90d":float(close.iloc[end+90]/close.iloc[end]-1),"forward_365d":float(future),"further_drawdown":float(segment.min())})
        if len(selected)>=top_n: break
    dispersion=float(np.std([item["forward_365d"] for item in selected])) if selected else None
    return {"status":"RESEARCH","window_days":window,"analogues":selected,"independent_episodes":len(selected),"dispersion":dispersion}
