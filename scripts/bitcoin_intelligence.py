from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.telegram import TelegramDecisionBot

root=Path(__file__).resolve().parents[1]
if hasattr(sys.stdout,"reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def state():
    config=load_config(root/"config.yaml");prices=OHLCVStore(root/config["data"]["database"]).load("1d");store=ExternalMetricStore(root/config["data"]["external_database"])
    feeds={"onchain_provider":StoreOnChainProvider(store),"funding":store.load("funding_rate_8h"),"open_interest":store.load("open_interest_usd"),"macro":{},"etf":store.load("etf_net_flow_usd"),"four_hour":OHLCVStore(root/config["data"]["database"]).load("4h")}
    return analyze_intelligence(prices,config,feeds=feeds),config
def main():
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("run","snapshot","telegram","health"));parser.add_argument("--telegram-command",default="/decision");args=parser.parse_args();current,config=state();ledger=ForwardLedger(root/"database"/"forward_validation.db")
    if args.command=="run":print(json.dumps(current["decision"],indent=2,default=str))
    elif args.command=="health":print(json.dumps({**ledger.health(),"data_health":current["precision"]["data_health"]},indent=2))
    elif args.command=="telegram":print(TelegramDecisionBot(dry_run=True).command(args.telegram_command,current,ledger.health()))
    else:
        commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip();print(json.dumps(ledger.append_snapshot(current,commit,current["precision"]["config_hash"]),indent=2,default=str))
if __name__=="__main__":main()
