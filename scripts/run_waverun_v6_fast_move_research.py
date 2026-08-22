"""Deterministic V6 fast-move/base-rate research; no model fitting or holdout access."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_v6"
COLS = ["timestamp", "spot_price", "flow_pressure", "flow_pressure_acceleration", "spot_pressure_10s", "futures_pressure_10s", "price_return_30s", "price_acceleration_30s", "price_response_efficiency", "flow_price_absorption", "expansion_score", "volatility_score", "macd_30s_cross_age", "regime"]
LADDER = {"50_60s": (50, 12), "75_120s": (75, 24), "100_180s": (100, 36), "100_300s": (100, 60), "150_300s": (150, 60), "200_300s": (200, 60), "200_600s": (200, 120), "300_600s": (300, 120), "300_900s": (300, 180), "500_1800s": (500, 360)}

def load() -> pd.DataFrame:
    frames=[]
    for path in sorted((ROOT/"runtime"/"waverun_data"/"derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path): continue
        try: d=pd.read_parquet(path,columns=COLS)
        except (OSError,ValueError): continue
        d.timestamp=pd.to_datetime(d.timestamp,utc=True); d["period"]="Q1_2025" if "q1_2025" in str(path) else ("JUL_2026" if "2026\\07" in str(path) else "APR_JUN_2025"); frames.append(d)
    return pd.concat(frames,ignore_index=True).sort_values("timestamp").reset_index(drop=True)

def valid_return(f: pd.DataFrame, rows: int) -> np.ndarray:
    p=f.spot_price.to_numpy(float); t=f.timestamp.to_numpy(dtype="datetime64[s]"); out=np.full(len(f),np.nan); out[:-rows]=p[rows:]-p[:-rows]; valid=np.zeros(len(f),bool); valid[:-rows]=(t[rows:]-t[:-rows] <= np.timedelta64(rows*5,"s")); return np.where(valid,out,np.nan)

def side_stats(f: pd.DataFrame, mask: np.ndarray, direction: int) -> dict:
    idx=np.flatnonzero(mask); out={"N":len(idx)}
    for name,(target,rows) in LADDER.items():
        r=f"ret_{rows}"; vals=f.loc[idx,r].to_numpy(float)*direction; hit=np.isfinite(vals)&(vals>=target); out[name]={"hits":int(hit.sum()),"rate":None if len(idx)==0 else float(hit.mean())}
    return out

def decluster(mask: np.ndarray, f: pd.DataFrame) -> np.ndarray:
    idx=np.flatnonzero(mask); ts=f.timestamp.to_numpy(dtype="datetime64[s]"); keep=[]
    for i in idx:
        if not keep or ts[i]-ts[keep[-1]]>=np.timedelta64(300,"s"): keep.append(int(i))
    return np.asarray(keep,dtype=int)

def main() -> None:
    f=load();
    for name,(_,rows) in LADDER.items(): f[f"ret_{rows}"]=valid_return(f,rows)
    q=f[f.period=="Q1_2025"].flow_pressure.abs().quantile(.80); medvol=f[f.period=="Q1_2025"].volatility_score.quantile(.80)
    pressure=f.flow_pressure.abs()>=q; response=np.sign(f.flow_pressure)*f.price_return_30s>0; efficient=np.sign(f.flow_pressure)*f.price_response_efficiency>0; noabs=f.flow_price_absorption.abs()<f[f.period=="Q1_2025"].flow_price_absorption.abs().quantile(.80)
    modes={"PRESSURE":pressure,"IGNITION_RESPONSE":pressure&response,"EFFICIENCY":pressure&efficient,"NO_ABSORPTION":pressure&noabs,"COMBINED":pressure&response&efficient&noabs}
    result={"execution":"DISABLED","holdout_closed":["2026-08-16","2026-08-17"],"thresholds":{"pressure_q1_80":float(q),"volatility_q1_80":float(medvol)},"base_rate":{},"signals":{},"fast_move_library":{}}
    for name,(target,rows) in LADDER.items():
        result["base_rate"][name]={"LONG":side_stats(f,np.ones(len(f),bool),1)[name],"SHORT":side_stats(f,np.ones(len(f),bool),-1)[name]}
    for mode,mask in modes.items():
        result["signals"][mode]={}
        for direction,label in ((1,"LONG"),(-1,"SHORT")):
            idx=decluster(mask.to_numpy()&(np.sign(f.flow_pressure.to_numpy())==direction),f); c=f.iloc[idx]; result["signals"][mode][label]={"N":len(c),"signals_per_day":float(len(c)/(c.timestamp.max()-c.timestamp.min()).total_seconds()*86400) if len(c)>1 else 0.0}
            result["signals"][mode][label]["ladder"] = side_stats(f, np.isin(np.arange(len(f)),idx), direction)
            result["signals"][mode][label]["periods"]={p:side_stats(f,np.isin(np.arange(len(f)),idx)&(f.period.to_numpy()==p),direction) for p in ("Q1_2025","APR_JUN_2025","JUL_2026")}
    for name,(target,rows) in LADDER.items():
        mask=np.abs(f[f"ret_{rows}"].to_numpy(float))>=target; idx=decluster(mask,f); result["fast_move_library"][name]={"N":len(idx),"long":int((f.iloc[idx][f"ret_{rows}"]>=target).sum()),"short":int((f.iloc[idx][f"ret_{rows}"]<=-target).sum())}
    live=ROOT/"runtime"/"waverun_v5_1"/"live_6h_20260821_vantage_path"; ticks=pd.read_json(live/"vantage_ticks.jsonl",lines=True); ticks.timestamp=pd.to_datetime(ticks.timestamp,utc=True)
    result["live"]={"ticks":len(ticks),"start":ticks.timestamp.min().isoformat(),"end":ticks.timestamp.max().isoformat(),"bid_ask_complete":bool(ticks[["bid","ask"]].notna().all().all()),"crossed_quotes":int((ticks.bid>ticks.ask).sum()),"median_spread":float(ticks.spread.median()),"p95_gap_s":float(ticks.timestamp.diff().dt.total_seconds().quantile(.95))}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"v6_fast_move_results.json").write_text(json.dumps(result,indent=2,default=str),encoding="utf-8"); print(json.dumps({"primary_base":result["base_rate"]["100_300s"],"combined":result["signals"]["COMBINED"],"live":result["live"]},indent=2))
if __name__=="__main__": main()
