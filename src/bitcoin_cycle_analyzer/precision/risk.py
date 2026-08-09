from __future__ import annotations
import numpy as np
import pandas as pd


def precision_risk(frame:pd.DataFrame,technical:dict,derivatives:dict|None=None,as_of=None)->dict:
    data=frame.loc[:pd.Timestamp(as_of)] if as_of is not None else frame; returns=data.close.astype(float).pct_change(); vol=float(returns.rolling(30).std().iloc[-1])
    vol_pct=float((returns.rolling(30).std().dropna()<=vol).mean()); dd=float(data.close.iloc[-1]/data.close.cummax().iloc[-1]-1)
    leverage=(derivatives or {}).get("state",{}).get("leverage","UNAVAILABLE"); base=.45*min(1,abs(dd)/.7)+.35*vol_pct+.2*(1 if leverage=="ELEVATED" else .5)
    horizons={"7d":round(base*85,1),"30d":round(base*100,1),"90d":round(min(1,base*1.1)*100,1)}
    tail_score=max(horizons.values()); tail="EXTREME" if tail_score>=85 else "HIGH" if tail_score>=70 else "ELEVATED" if tail_score>=55 else "NORMAL" if tail_score>=30 else "LOW"
    daily=float(returns.iloc[-1]); weekly=float(data.close.pct_change(7).iloc[-1]); volume=data.volume.astype(float); volume_z=float((volume.iloc[-1]-volume.rolling(90).mean().iloc[-1])/(volume.rolling(90).std().iloc[-1] or 1))
    stress=(abs(daily)>=.1)+(abs(weekly)>=.2)+(vol_pct>=.95)+(volume_z>=2)
    capitulation="CAPITULATION" if stress>=3 else "CAPITULATION_CANDIDATE" if stress==2 else "STRESS" if stress==1 else "NONE"
    return {"horizons":horizons,"tail_state":tail,"volatility_percentile":round(vol_pct*100,1),"capitulation":capitulation,
            "capitulation_features":{"daily_return":daily,"weekly_return":weekly,"volume_zscore":volume_z},
            "historical_mae":technical.get("forward_summary_365d",{}).get("worst_drawdown"),"note":"Ordinal risk states, not probabilities.","status":"RESEARCH"}
