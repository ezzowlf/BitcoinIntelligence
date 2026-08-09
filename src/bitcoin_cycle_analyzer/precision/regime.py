from __future__ import annotations
import pandas as pd

REGIMES=("BEAR","ACCUMULATION","RECOVERY","EARLY_BULL","BULL","DISTRIBUTION","TRANSITION")


def _normalize(scores):
    total=sum(max(0,v) for v in scores.values()) or 1
    return {key:round(max(0,value)/total*100,1) for key,value in scores.items()}


def regime_ensemble(frame:pd.DataFrame,cycle:dict,onchain:dict|None=None,as_of=None)->dict:
    data=frame.loc[:pd.Timestamp(as_of)] if as_of is not None else frame; close=data.close.astype(float)
    ret90=float(close.pct_change(90).iloc[-1]); ret365=float(close.pct_change(365).iloc[-1]); dd=float(close.iloc[-1]/close.cummax().iloc[-1]-1)
    ma200=float(close.rolling(200,min_periods=30).mean().iloc[-1]); vol=float(close.pct_change().rolling(30).std().iloc[-1])
    price_model={r:0 for r in REGIMES}; price_model["RECOVERY" if close.iloc[-1]>ma200 and ret90>0 else "BEAR" if ret90<-.15 else "TRANSITION"]=1
    draw_model={r:0 for r in REGIMES}; draw_model["ACCUMULATION" if dd<-.5 else "RECOVERY" if dd<-.25 and ret90>0 else "DISTRIBUTION" if dd>-.1 and ret90<0 else "TRANSITION"]=1
    momentum={r:0 for r in REGIMES}; momentum["BULL" if ret365>.5 and ret90>0 else "BEAR" if ret365<0 and ret90<0 else "RECOVERY" if ret90>0 else "TRANSITION"]=1
    timing={r:0 for r in REGIMES}; months=cycle["halving"]["months_since"]; timing["EARLY_BULL" if 0<=months<12 else "BULL" if months<24 else "DISTRIBUTION" if months<30 else "TRANSITION"]=1
    models={"price_structure":price_model,"drawdown":draw_model,"momentum":momentum,"cycle_timing":timing}
    if onchain and onchain.get("state",{}).get("holder_behavior")!="UNAVAILABLE":
        state=onchain["state"]["holder_behavior"]; model={r:0 for r in REGIMES}; model["ACCUMULATION" if state=="ACCUMULATION" else "DISTRIBUTION" if state=="DISTRIBUTION" else "TRANSITION"]=1; models["onchain"]=model
    aggregate={r:sum(model[r] for model in models.values()) for r in REGIMES}; support=_normalize(aggregate); ordered=sorted(support,key=support.get,reverse=True)
    agreement=aggregate[ordered[0]]/len(models); margin=support[ordered[0]]-support[ordered[1]]
    stability="HIGH" if agreement>=.75 and margin>=25 else "MEDIUM" if agreement>=.5 and margin>=10 else "LOW"
    candidate=ordered[1] if ordered[0]=="TRANSITION" else ordered[0]
    transition="CONFIRMED" if agreement>=.75 else "CONFIRMING" if agreement>=.4 else "CANDIDATE"
    return {"current":ordered[0],"candidate":candidate,"relative_support":support,"models":{name:max(model,key=model.get) for name,model in models.items()},
            "model_agreement":round(agreement,2),"support_margin":margin,"stability":stability,"transition_status":transition,
            "volatility_30d":vol,"note":"Relative support is not a calibrated probability.","status":"RESEARCH"}
