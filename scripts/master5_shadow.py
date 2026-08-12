from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"src"));sys.path.insert(0,str(root/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.master5 import Master5ShadowLedger

def run_once():
    frozen=json.loads((root/"frozen"/"master_5_0_challenger_frozen.json").read_text(encoding="utf-8"));state,_=bitcoin_intelligence.state();live=state["live_market"];timestamp=live.get("last_confirmed_h4")
    result={"status":"NO_CONFIRMED_POST_FREEZE_CANDLE","forward_start":frozen["forward_start"],"last_confirmed_h4":timestamp,"execution":"DISABLED"}
    if live.get("status")=="ONLINE" and timestamp is not None and pd.Timestamp(timestamp)>=pd.Timestamp(frozen["forward_start"]):
        payload={"timestamp":timestamp,"mt5_price":live["tick"].get("mid"),"master_state":state["master"],"challenger_state":state["master5_challenger"],"buy_quality":state["master5_challenger"]["buy"]["quality"],"sell_risk":state["master5_challenger"]["risk"]["sell_off_risk"],"zones":state["master5_challenger"]["buy"]["zone"],"factors":{"buy":state["master5_challenger"]["buy"]["factors"],"risk":state["master5_challenger"]["risk"]["factors"]},"provider_provenance":live["provenance"],"frozen_config_hash":frozen["config_hash"],"execution":"DISABLED"}
        ledger=Master5ShadowLedger(root/"database"/"master5_shadow.db",frozen["forward_start"]);result={"status":"SNAPSHOT_APPENDED_OR_ALREADY_PRESENT","id":ledger.append(timestamp,payload),"count":ledger.count(),"timestamp":timestamp,"execution":"DISABLED"}
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--watch",action="store_true");parser.add_argument("--interval",type=int,default=60);args=parser.parse_args()
    while True:
        print(json.dumps(run_once(),default=str),flush=True)
        if not args.watch:break
        time.sleep(max(30,args.interval))

if __name__=="__main__":main()
