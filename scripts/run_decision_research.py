from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore

root=Path(__file__).resolve().parents[1];config=load_config(root/"config.yaml");data=OHLCVStore(root/config["data"]["database"]).load("1d");close=data.close.astype(float);dd=close/close.cummax()-1;ma50=close.rolling(50).mean();ma200=close.rolling(200).mean();value=(-dd).rolling(1460,min_periods=365).rank(pct=True)*100;confirmed=(close>ma50)&(close.pct_change(30)>0)&(ma50.diff(10)>0);bear=(close<ma200)&(close.pct_change(90)<0)
decision=pd.Series("WAIT",index=data.index);decision.loc[value>=75]="ACCUMULATE";decision.loc[(value>=75)&confirmed&~bear]="BUY";decision.loc[(value<20)&bear]="REDUCE";decision.loc[(value<10)&bear&(close.pct_change(30)<-.15)]="SELL"
future=pd.concat([close.shift(-i)/close-1 for i in range(1,91)],axis=1);frame=pd.DataFrame({"decision":decision,"f30":close.shift(-30)/close-1,"f90":close.shift(-90)/close-1,"mae":future.iloc[:,:30].min(axis=1)});frame["new"]=frame.decision.ne(frame.decision.shift());events=frame[frame.new]
matrix={}
for name,group in events.groupby("decision"):
    mature=group.dropna();matrix[name]={"episodes":len(mature),"median_30d":None if mature.empty else float(mature.f30.median()),"median_90d":None if mature.empty else float(mature.f90.median()),"mae":None if mature.empty else float(mature.mae.median()),"false_sell_rate":None if name!="SELL" or mature.empty else float((mature.f30>0).mean())}
result={"status":"HISTORICAL_RESEARCH_ONLY","matrix":matrix,"buy_vs_accumulate":"BUY is not promoted unless both return and MAE improve robustly; no threshold was optimized","forward_start":"2026-08-10T00:00:00Z"};(root/"data"/"reports"/"decision_research.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps(result,indent=2))
