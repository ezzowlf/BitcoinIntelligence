from __future__ import annotations
import json,sys,time
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"src"));sys.path.insert(0,str(root/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.macro7_live import Macro7ShadowLedger
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore

def run_once():
    frozen=json.loads((root/"frozen"/"macro_swing_7_0_research_frozen.json").read_text(encoding="utf-8"));state,_=bitcoin_intelligence.state();live=state["live_market"];ledger=Macro7ShadowLedger(root/"database"/"macro7_shadow.db",frozen["forward_start"]);results={}
    cfg=load_config(root/"config.yaml");daily=OHLCVStore(root/cfg["data"]["database"]).load("1d");weekly=daily.resample("W-MON",label="right",closed="right").last().dropna();weekly=weekly[weekly.index<=pd.Timestamp.now(tz="UTC")]
    stamps={"4H":live.get("last_confirmed_h4"),"D1":live.get("last_confirmed_d1"),"W1":None if weekly.empty else weekly.index[-1]}
    for timeframe,timestamp in stamps.items():
        if timestamp is None or pd.Timestamp(timestamp)<=pd.Timestamp(frozen["forward_start"]):results[timeframe]="NO_CONFIRMED_POST_FREEZE_CANDLE";continue
        payload={"timestamp":timestamp,"timeframe":timeframe,"btc_price":live.get("tick",{}).get("mid"),"macro7":state["macro7"],"control_3":state["master"],"specialist_5":state["master5_challenger"],"fusion_6":state["fusion6"],"frozen_config_hash":frozen["config_hash"],"execution":"DISABLED"};results[timeframe]=ledger.append(timeframe,timestamp,payload)
    return {"status":results,"health":ledger.health(),"execution":"DISABLED"}
def main():
    import argparse;p=argparse.ArgumentParser();p.add_argument("--watch",action="store_true");p.add_argument("--interval",type=int,default=60);a=p.parse_args()
    while True:
        print(json.dumps(run_once(),default=str),flush=True)
        if not a.watch:break
        time.sleep(max(30,a.interval))
if __name__=="__main__":main()
