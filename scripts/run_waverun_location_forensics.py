"""Forensic audit of frozen V5.3 candidates; location descriptors are descriptive only."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"reports"/"waverun_location_forensics"
COLS=["timestamp","spot_price","flow_pressure","spot_futures_agreement","price_return_30s","price_acceleration_30s","flow_price_absorption","macd_30s_cross_direction","macd_30s_histogram","macd_30s_histogram_slope","macd_30s_histogram_acceleration","regime"]

def load():
    fs=[]
    for p in sorted((ROOT/"runtime"/"waverun_data"/"derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(p) or "2026\\08\\17" in str(p): continue
        try:d=pd.read_parquet(p,columns=COLS)
        except (OSError,ValueError):continue
        d.timestamp=pd.to_datetime(d.timestamp,utc=True); d["period"]="Q1_2025" if "q1_2025" in str(p) else ("JUL_2026" if "2026\\07" in str(p) else "APR_JUN_2025"); fs.append(d)
    f=pd.concat(fs,ignore_index=True).sort_values("timestamp").reset_index(drop=True); p=f.spot_price
    f["range_pos_1h"]=(p-p.rolling(720,min_periods=720).min())/(p.rolling(720,min_periods=720).max()-p.rolling(720,min_periods=720).min()).replace(0,np.nan)
    f["vwap_day"]=p.groupby(f.timestamp.dt.floor("D")).transform("mean"); f["vwap_distance_bp"]=(p/f.vwap_day-1)*10000; f["session"]=pd.cut(f.timestamp.dt.hour,[0,7,13,18,24],labels=["EUROPE","US","OVERLAP","ASIA"],right=False,include_lowest=True)
    return f

def main():
    f=load(); qh=f[f.period=="Q1_2025"].macd_30s_histogram.abs().quantile(.8); qa=f[f.period=="Q1_2025"].macd_30s_histogram_acceleration.abs().quantile(.8)
    mask=(f.macd_30s_cross_direction<0)&(f.macd_30s_histogram<0)&(f.macd_30s_histogram_slope<0)&(f.macd_30s_histogram_acceleration<0)&(f.macd_30s_histogram.abs()>=qh)&(f.macd_30s_histogram_acceleration.abs()>=qa)
    idx=np.flatnonzero(mask.to_numpy()); ts=f.timestamp.to_numpy(dtype="datetime64[s]"); keep=[]
    for i in idx:
        if not keep or ts[i]-ts[keep[-1]]>=np.timedelta64(180,"s"):keep.append(int(i))
    rows=[]; price=f.spot_price.to_numpy(float)
    for i in keep:
        future=price[i+1:i+721]; valid=len(future)==720 and ts[i+720]-ts[i]<=np.timedelta64(3600,"s")
        if not valid:continue
        fav=price[i]-8.5-future
        mfe=float(np.max(fav)); mae=float(np.min(price[i]-8.5-future)); group="WINNER_500" if mfe>=500 else ("WINNER_300" if mfe>=300 else ("WINNER_100" if mfe>=100 else "ABSORBED" if mae<-100 else "FAILED"))
        def tt(values, x):
            h=np.flatnonzero(values>=x); return None if len(h)==0 else float((h[0]+1)*5)
        row=f.iloc[i]; rows.append({"index":i,"timestamp":row.timestamp.isoformat(),"period":row.period,"group":group,"session":str(row.session),"range_pos_1h":None if pd.isna(row.range_pos_1h) else float(row.range_pos_1h),"vwap_distance_bp":None if pd.isna(row.vwap_distance_bp) else float(row.vwap_distance_bp),"mfe_60m":mfe,"mae_60m":mae,"time_to_25_s":tt(fav,25),"time_to_50_s":tt(fav,50),"time_to_100_s":tt(fav,100),"time_to_200_s":tt(fav,200),"agreement":float(row.spot_futures_agreement) if pd.notna(row.spot_futures_agreement) else None,"flow_absorption":float(row.flow_price_absorption) if pd.notna(row.flow_price_absorption) else None})
    c=pd.DataFrame(rows); winners=c[c.group.str.startswith("WINNER")]; losers=c[c.group.isin(["ABSORBED","FAILED"])]
    def summary(g): return {"N":len(g),"mfe_median":None if g.empty else float(g.mfe_60m.median()),"mae_median":None if g.empty else float(g.mae_60m.median()),"time_to_100_median":None if g.time_to_100_s.dropna().empty else float(g.time_to_100_s.median()),"range_pos_median":None if g.range_pos_1h.dropna().empty else float(g.range_pos_1h.median()),"vwap_distance_bp_median":None if g.vwap_distance_bp.dropna().empty else float(g.vwap_distance_bp.median())}
    payload={"execution":"DISABLED","holdout_closed":["2026-08-16","2026-08-17"],"selection":"frozen V5.3 Q1 top-20% SHORT MACD pressure, 180s decluster","case_count":len(c),"groups":c.group.value_counts().to_dict(),"winner_summary":summary(winners),"loser_summary":summary(losers),"session_winners":winners.session.value_counts(dropna=False).to_dict(),"session_losers":losers.session.value_counts(dropna=False).to_dict(),"cases":rows,"data_limits":["historical Vantage Bid/Ask unavailable","no OHLC high/low for objective multi-timeframe FVG","no historical L2 order-book path","location descriptors are descriptive, not optimized"]}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"location_forensics.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8"); print(json.dumps({k:payload[k] for k in ("groups","winner_summary","loser_summary","session_winners","session_losers")},indent=2))
if __name__=="__main__":main()
