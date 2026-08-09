from __future__ import annotations
import pandas as pd

ALLOWED_EVENTS={"WAR_ESCALATION","WAR_ENTRY","MISSILE_STRIKE","ENERGY_SUPPLY_SHOCK","STRAIT_BLOCKAGE","SANCTIONS","DEESCALATION","CEASEFIRE","PEACE_NEGOTIATION"}


def geopolitical_reaction(event,frame,event_time,oil_return=None,nasdaq_return=None):
    if event not in ALLOWED_EVENTS:raise ValueError("unsupported geopolitical event")
    cutoff=pd.Timestamp(event_time);visible=frame.loc[:cutoff];future=frame.loc[cutoff:];base=float(visible.close.iloc[-1]);returns={}
    for label,days in (("24h",1),("3d",3),("7d",7)):returns[label]=None if len(future)<=days else float(future.close.iloc[days]/base-1)
    breakdown=(returns["24h"] or 0)<-.04;transmission=breakdown and (oil_return or 0)>.03 and (nasdaq_return or 0)<-.02
    resilience=event not in {"DEESCALATION","CEASEFIRE","PEACE_NEGOTIATION"} and (returns["3d"] or -1)>=0
    return {"event":event,"returns":returns,"transmission_confirmed":transmission,"risk_action":"REDUCE" if transmission else "WATCH","negative_news_resilience":resilience,"maximum_news_only_state":"WATCH","status":"RESEARCH"}


def market_shocks(frame,as_of=None):
    visible=frame.loc[:as_of] if as_of is not None else frame;ret=visible.close.pct_change();vol=ret.rolling(30).std();volume_z=(visible.volume-visible.volume.rolling(30).mean())/visible.volume.rolling(30).std()
    return {"volatility_shock":bool(abs(ret.iloc[-1])>3*vol.iloc[-1]),"volume_shock":bool(volume_z.iloc[-1]>3),"gap_move":bool(abs(visible.open.iloc[-1]/visible.close.iloc[-2]-1)>.05),"status":"RESEARCH"}
