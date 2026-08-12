from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"src"));sys.path.insert(0,str(root/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.fusion_live import Fusion6ForwardLedger
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.config import load_config

def run_once():
    frozen=json.loads((root/"frozen"/"fusion_6_research_frozen.json").read_text(encoding="utf-8"));state,_=bitcoin_intelligence.state();live=state["live_market"];timestamp=live.get("last_confirmed_h4")
    result={"status":"NO_CONFIRMED_POST_FREEZE_CANDLE","forward_start":frozen["forward_start"],"last_confirmed_h4":timestamp,"execution":"DISABLED"}
    if live.get("status")=="ONLINE" and timestamp is not None and pd.Timestamp(timestamp)>pd.Timestamp(frozen["forward_start"]):
        fusion=state["fusion6"];master=state["master"]["state"];specialist=state["master5_challenger"]
        payload={"timestamp":timestamp,"btc_price":live["tick"].get("mid"),"control_3":state["master"],"specialist_5":specialist,"fusion_6":fusion,"engine_comparison":{"control_3":state["master"]["decision"],"specialist_5":{"buy":specialist["buy"]["state"],"risk":specialist["risk"]["sell_off_risk"]},"fusion_6":{"long_term":fusion["long_term"],"new_entry":fusion["new_entry"],"risk":fusion["risk"]}},"regime":fusion["regime"],"timing":fusion["timing"],"rare_buy":fusion["rare_buy"],"distribution":fusion["distribution"],"risk":fusion["risk"],"active_patterns":fusion["active_historical_patterns"],"buy_zones":master["buy_zones"],"support":master["nearest_support"],"resistance":master["nearest_resistance"],"drawdown":master["drawdown"],"rsi":{"weekly":master["weekly_rsi"],"daily":state["advanced"]["momentum"]["daily"]["rsi"],"monthly":state["advanced"]["momentum"]["monthly"]["rsi"]},"data_quality":fusion["data_quality"],"event_context":{"news":state["modules"]["news"],"calendar":state["modules"]["seasonality"]},"provider_provenance":live["provenance"],"frozen_config_hash":frozen["config_hash"],"execution":"DISABLED"}
        ledger=Fusion6ForwardLedger(root/"database"/"fusion6_live.db",frozen["forward_start"]);previous=ledger.latest_payload();snap=ledger.append_snapshot(timestamp,float(payload["btc_price"]),payload);transitions=ledger.append_transitions(snap["id"],timestamp,None if previous is None else previous.get("fusion_6"),fusion)
        config=load_config(root/"config.yaml");prices=OHLCVStore(root/config["data"]["database"]).load("4h");matured=ledger.mature_outcomes(prices)
        result={"status":"SNAPSHOT_APPENDED_OR_ALREADY_PRESENT","snapshot":snap,"transitions":transitions,"outcomes_matured":matured,"health":ledger.health(),"timestamp":timestamp,"execution":"DISABLED"}
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--watch",action="store_true");p.add_argument("--interval",type=int,default=60);a=p.parse_args()
    while True:
        print(json.dumps(run_once(),default=str),flush=True)
        if not a.watch:break
        time.sleep(max(30,a.interval))
if __name__=="__main__":main()
