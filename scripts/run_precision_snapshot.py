from __future__ import annotations
import subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.precision.storage import PrecisionStore

root=Path(__file__).resolve().parents[1]; config=load_config(root/"config.yaml"); prices=OHLCVStore(root/config["data"]["database"]).load("1d"); external=ExternalMetricStore(root/config["data"]["external_database"])
feeds={"onchain_provider":StoreOnChainProvider(external),"funding":external.load("funding_rate_8h"),"open_interest":external.load("open_interest_usd"),"macro":{},"etf":external.load("etf_net_flow_usd")}
state=analyze_intelligence(prices,config,feeds=feeds); snapshot=state["precision"]; snapshot["price"]=float(prices.close.iloc[-1]); snapshot["code_commit"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
store=PrecisionStore(root/"database"/"precision_snapshots.db"); store.save_snapshot(snapshot)
print({"timestamp":snapshot["timestamp"],"market_state":snapshot["market_state"],"engine_version":snapshot["engine_version"],"execution":snapshot["execution"]})
