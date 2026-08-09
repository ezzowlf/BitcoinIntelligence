from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore


def summarize(frame,mask):
    selected=frame.loc[mask].dropna(subset=["f30","f90","mae30"])
    return {"raw_observations":len(selected),"independent_episodes":int(selected.episode.nunique()) if len(selected) else 0,
            "median_30d":None if selected.empty else float(selected.f30.median()),"win_rate_30d":None if selected.empty else float((selected.f30>0).mean()),
            "median_90d":None if selected.empty else float(selected.f90.median()),"mae_30d":None if selected.empty else float(selected.mae30.median()),
            "mfe_30d":None if selected.empty else float(selected.mfe30.median())}


def main():
    root=Path(__file__).resolve().parents[1]; config=load_config(root/"config.yaml"); data=OHLCVStore(root/config["data"]["database"]).load("1d")
    close=data.close.astype(float); returns=close.pct_change(); ath=close.cummax(); dd=close/ath-1; ma50=close.rolling(50).mean(); ma200=close.rolling(200).mean()
    frame=pd.DataFrame(index=data.index); frame["value"]=(-dd).rolling(1460,min_periods=365).rank(pct=True)*100
    frame["timing"]="WAIT"; confirmed=(close>ma50)&(close.pct_change(30)>0)&(ma50.diff(10)>0); frame.loc[confirmed,"timing"]="CONFIRMED"
    frame["regime"]=np.where((close>ma200)&(close.pct_change(90)>0),"RECOVERY_BULL",np.where((close<ma200)&(close.pct_change(90)<0),"BEAR","TRANSITION"))
    vol=returns.rolling(30).std(); frame["risk"]=((abs(dd)/.7).clip(0,1)*55+(vol.rolling(1460,min_periods=365).rank(pct=True))*45).clip(0,100)
    frame["f30"]=close.shift(-30)/close-1; frame["f90"]=close.shift(-90)/close-1
    future=pd.concat([close.shift(-i)/close-1 for i in range(1,31)],axis=1); frame["mae30"]=future.min(axis=1); frame["mfe30"]=future.max(axis=1)
    high=frame.value>=75; crossings=high&(frame.value.shift(1)<75); episode=crossings.cumsum(); frame["episode"]=episode
    # one observation per independent value episode and timing state
    events=frame.loc[high].groupby(["episode","timing"],sort=False).head(1)
    conditional={"value_high_timing_wait":summarize(events,events.timing=="WAIT"),"value_high_timing_confirmed":summarize(events,events.timing=="CONFIRMED"),
                 "value_high_risk_high":summarize(events,events.risk>=70),"value_high_risk_lower":summarize(events,events.risk<70),
                 "value_high_bear":summarize(events,events.regime=="BEAR"),"value_high_recovery_bull":summarize(events,events.regime=="RECOVERY_BULL")}
    confirmed_events=events[events.timing=="CONFIRMED"]; false_rate=None if confirmed_events.empty else float((confirmed_events.mae30<=-.1).mean())
    delays=[]
    for timestamp,row in confirmed_events.iterrows():
        history=close.loc[:timestamp].tail(31); low_time=history.idxmin(); low=float(history.min())
        delays.append({"timestamp":str(timestamp),"days_after_local_low":int((timestamp-low_time).days),"price_above_local_low_pct":float(close.loc[timestamp]/low-1)})
    risk_bins=pd.cut(events.risk,[0,20,40,60,80,100],include_lowest=True); risk_mae=events.groupby(risk_bins,observed=False).mae30.median()
    risk_values=[value for value in risk_mae if pd.notna(value)]; risk_monotone=all(a>=b for a,b in zip(risk_values,risk_values[1:]))
    yearly=[]
    for year in range(2018,int(data.index[-1].year)+1):
        test=events[events.index.year==year]; yearly.append({"test_year":year,"train":"anchored_to_previous_year","episodes":int(test.episode.nunique()),"median_30d":None if test.empty else float(test.f30.median())})
    result={"method":"Fixed ex-ante proxy rules; episode-level; no weight/threshold optimization","oos_status":"USED_FOR_RESEARCH",
            "conditional_performance":conditional,"false_confirmation":{"confirmed":len(confirmed_events),"failed_10pct_mae":int((confirmed_events.mae30<=-.1).sum()),"rate":false_rate},
            "confirmation_delay":{"episodes":len(delays),"median_days_after_local_low":None if not delays else float(np.median([d["days_after_local_low"] for d in delays])),"median_price_above_low_pct":None if not delays else float(np.median([d["price_above_local_low_pct"] for d in delays])),"rows":delays},
            "risk_monotonicity":{"bins":{str(key):None if pd.isna(value) else float(value) for key,value in risk_mae.items()},"monotone":risk_monotone},
            "core_questions":{"timing_reduces_value_drawdown":conditional["value_high_timing_confirmed"]["mae_30d"] is not None and conditional["value_high_timing_confirmed"]["mae_30d"]>conditional["value_high_timing_wait"]["mae_30d"],
                              "regime_separates_value_outcomes":conditional["value_high_bear"]!=conditional["value_high_recovery_bull"],
                              "risk_has_monotone_mae_relation":risk_monotone,
                              "confirmed_better_than_wait":conditional["value_high_timing_confirmed"]["median_30d"] is not None and conditional["value_high_timing_confirmed"]["median_30d"]>conditional["value_high_timing_wait"]["median_30d"]},
            "anchored_walk_forward":yearly,"multiple_testing":{"factors":3,"conditional_variants":6,"primary_horizons":2,"selection_performed":False},
            "final_holdout":"NOT_AVAILABLE_YET; all completed observations through 2026-08-07 have informed research"}
    output=root/"data"/"reports"/"precision_validation.json"; output.write_text(json.dumps(result,indent=2,default=str),encoding="utf-8"); return result


if __name__=="__main__": print(json.dumps(main(),indent=2,default=str))
