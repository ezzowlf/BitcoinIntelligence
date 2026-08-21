"""Bounded, chronological V5.4 pressure/response research; no ML and no retuning on July."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_v5_4"
HORIZONS = {"5m": 60, "10m": 120, "15m": 180, "30m": 360, "60m": 720}
TARGETS = (100, 150, 200, 300, 400, 500)
COLS = ["timestamp", "spot_price", "flow_pressure", "flow_pressure_acceleration", "spot_pressure_10s", "futures_pressure_10s", "spot_pressure_persistence", "futures_pressure_persistence", "spot_cvd_acceleration", "futures_cvd_acceleration", "price_response_efficiency", "flow_price_absorption", "price_return_30s", "price_acceleration_30s", "expansion_score", "volatility_score", "macd_30s_histogram", "macd_30s_histogram_slope", "macd_30s_histogram_acceleration", "macd_30s_cross_age", "regime"]

def load() -> pd.DataFrame:
    parts = []
    for path in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path):
            continue
        try: d = pd.read_parquet(path, columns=COLS)
        except (OSError, ValueError): continue
        d["timestamp"] = pd.to_datetime(d.timestamp, utc=True)
        d["period"] = "Q1_2025" if "q1_2025" in str(path) else ("JUL_2026" if "2026\\07" in str(path) else "APR_JUN_2025")
        parts.append(d)
    return pd.concat(parts, ignore_index=True).sort_values("timestamp").reset_index(drop=True)

def labels(f: pd.DataFrame) -> pd.DataFrame:
    p = f.spot_price.to_numpy(float); t = f.timestamp.to_numpy(dtype="datetime64[s]")
    for name, n in HORIZONS.items():
        future = np.full(len(f), np.nan); future[:len(f)-n] = p[n:]-p[:-n]
        valid = np.zeros(len(f), dtype=bool); valid[:len(f)-n] = (t[n:]-t[:-n] <= np.timedelta64(n*5, "s"))
        f[f"ret_{name}"] = np.where(valid, future, np.nan)
    return f

def events(f: pd.DataFrame, mode: str) -> pd.DataFrame:
    q = f[f.period == "Q1_2025"].flow_pressure.abs().quantile(.80)
    pressure = f.flow_pressure.abs() >= q
    direction = np.sign(f.flow_pressure)
    response = direction * f.price_return_30s > 0
    efficient = direction * f.price_response_efficiency > 0
    no_abs = f.flow_price_absorption.abs() < f[f.period == "Q1_2025"].flow_price_absorption.abs().quantile(.80)
    if mode == "PRESSURE": mask = pressure
    elif mode == "RESPONSE": mask = pressure & response
    elif mode == "EFFICIENCY": mask = pressure & efficient
    elif mode == "AGE": mask = pressure & (f.macd_30s_cross_age.fillna(0).abs() <= f[f.period == "Q1_2025"].macd_30s_cross_age.abs().quantile(.80))
    else: mask = pressure & no_abs
    idx = np.flatnonzero(mask.fillna(False).to_numpy()); keep=[]; ts=f.timestamp.to_numpy(dtype="datetime64[s]")
    for i in idx:
        if not keep or ts[i]-ts[keep[-1]] >= np.timedelta64(180,"s"): keep.append(int(i))
    out=f.iloc[keep].copy(); out["direction"] = np.where(out.flow_pressure >= 0, "LONG", "SHORT"); out["mode"] = mode
    return out

def stats(c: pd.DataFrame) -> dict:
    result={"N":len(c),"signals_per_day":float(len(c)/(c.timestamp.max()-c.timestamp.min()).total_seconds()*86400) if len(c)>1 else 0.0,"periods":{}}
    for period, g in c.groupby("period"):
        d={"N":len(g)}
        for h in HORIZONS:
            row={}
            for target in TARGETS:
                hit=(g[f"ret_{h}"].abs()>=target)
                row[str(target)]={"hits":int(hit.sum()),"rate":None if len(g)==0 else float(hit.mean())}
            d[h]=row
        result["periods"][period]=d
    return result

def main() -> None:
    f=labels(load()); payload={"execution":"DISABLED","holdout_closed":["2026-08-16","2026-08-17"],"definition":"Q1 80th percentile absolute flow pressure, 180s decluster; thresholds frozen before Apr-Jun and Jul","modes":{}}
    for mode in ("PRESSURE","RESPONSE","EFFICIENCY","AGE","NO_ABSORPTION"):
        c=events(f,mode); payload["modes"][mode]=stats(c)
    live=ROOT/"runtime"/"waverun_v5_1"/"live_6h_20260821_vantage_path"
    ticks=pd.read_json(live/"vantage_ticks.jsonl",lines=True)
    ticks.timestamp=pd.to_datetime(ticks.timestamp,utc=True); payload["live"]={"ticks":len(ticks),"start":ticks.timestamp.min().isoformat(),"end":ticks.timestamp.max().isoformat(),"bid_ask_complete":bool(ticks[["bid","ask"]].notna().all().all()),"crossed_quotes":int((ticks.bid>ticks.ask).sum()),"median_spread":float(ticks.spread.median()),"p95_gap_s":float(ticks.timestamp.diff().dt.total_seconds().quantile(.95))}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"v5_4_oos.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"modes":{k:v["N"] for k,v in payload["modes"].items()},"live":payload["live"],"output":str(OUT/"v5_4_oos.json")},indent=2))
if __name__ == "__main__": main()
