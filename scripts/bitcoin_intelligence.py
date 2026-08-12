from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.telegram import TelegramDecisionBot
from bitcoin_cycle_analyzer.live import MT5MarketDataProvider
from bitcoin_cycle_analyzer.ai import BitcoinAIRouter
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.system_health import runtime_health
from bitcoin_cycle_analyzer.runtime import env_values

root=Path(__file__).resolve().parents[1]
if hasattr(sys.stdout,"reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def state():
    config=load_config(root/"config.yaml");prices=OHLCVStore(root/config["data"]["database"]).load("1d");store=ExternalMetricStore(root/config["data"]["external_database"])
    mt5=MT5MarketDataProvider(values=env_values(root/".env"));health=mt5.connect();tick=mt5.tick() if health.status=="ONLINE" else {"status":"UNAVAILABLE","reason":health.reason};h4=mt5.confirmed_candles("4h",500) if health.status=="ONLINE" else OHLCVStore(root/config["data"]["database"]).load("4h");d1=mt5.confirmed_candles("1d",500) if health.status=="ONLINE" else prices.iloc[0:0];w1=mt5.confirmed_candles("1w",260) if health.status=="ONLINE" else prices.iloc[0:0];m1=mt5.confirmed_candles("1mo",180) if health.status=="ONLINE" else prices.iloc[0:0]
    divergence=MT5MarketDataProvider.divergence(tick.get("mid"),float(prices.close.iloc[-1]))
    usable=health.status=="ONLINE" and tick.get("freshness") in {"LIVE","DELAYED"} and not d1.empty and divergence.get("status")!="CRITICAL"
    if usable:prices=pd.concat([prices.loc[prices.index<d1.index[0]],d1]).sort_index();prices=prices[~prices.index.duplicated(keep="last")]
    live_market={"status":"ONLINE" if usable else health.status,"health":health.__dict__,"tick":tick,"divergence":divergence,"last_confirmed_h4":None if health.status!="ONLINE" or h4.empty else h4.index[-1],"last_confirmed_d1":None if health.status!="ONLINE" or d1.empty else d1.index[-1],"last_confirmed_w1":None if health.status!="ONLINE" or w1.empty else w1.index[-1],"last_confirmed_1m":None if health.status!="ONLINE" or m1.empty else m1.index[-1],"timing_confirmation":"ENABLED" if usable else "BLOCKED","provenance":mt5.provenance()}
    discovery=HistoricalPatternDiscoveryEngine().discover(prices)
    feeds={"onchain_provider":StoreOnChainProvider(store),"funding":store.load("funding_rate_8h"),"open_interest":store.load("open_interest_usd"),"macro":{},"etf":store.load("etf_net_flow_usd"),"four_hour":h4,"live_market":live_market,"price_provider":"MT5 confirmed D1 + BITSTAMP historical" if usable else "BITSTAMP historical dataset","project_root":root,"fusion_discovery":discovery}
    mt5.close()
    return analyze_intelligence(prices,config,feeds=feeds),config
def main():
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("run","master","snapshot","telegram","health","ai-models"));parser.add_argument("--telegram-command",default="/decision");parser.add_argument("--dry-run",action="store_true");args=parser.parse_args()
    if args.command=="ai-models":print(json.dumps(BitcoinAIRouter(cache_dir=root/"runtime"/"ai_cache").discover_models(),indent=2));return
    current,config=state();ledger=ForwardLedger(root/"database"/"forward_validation.db")
    if args.command in {"run","master"}:print(json.dumps(current["master"],indent=2,default=str))
    elif args.command=="health":print(json.dumps({**ledger.health(),**runtime_health(root,current["live_market"]),"data_health":current["precision"]["data_health"],"openai":BitcoinAIRouter(cache_dir=root/"runtime"/"ai_cache").health(),"execution":"DISABLED"},indent=2,default=str))
    elif args.command=="telegram":print(TelegramDecisionBot(dry_run=True).command(args.telegram_command,current,runtime_health(root,current["live_market"])))
    else:
        commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip();control=ledger.append_snapshot(current,commit,current["precision"]["config_hash"]);master=ledger.append_master_snapshot(current["master"]);print(json.dumps({"control":control,"master":master},indent=2,default=str))
if __name__=="__main__":main()
