from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import pandas as pd
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.seasonality.event_windows import event_window_statistics
from bitcoin_cycle_analyzer.seasonality.calendar_effects import turn_of_month_statistics,quarter_statistics

root=Path(__file__).resolve().parents[1];config=load_config(root/"config.yaml");frame=OHLCVStore(root/config["data"]["database"]).load("1d");result=HistoricalPatternDiscoveryEngine().discover(frame);out=root/"data"/"reports";out.mkdir(parents=True,exist_ok=True)
flat=[]
for p in result["patterns"]:flat.append({**{k:v for k,v in p.items() if k not in {"regimes","walk_forward","factors","independence_groups"}},"factors":" + ".join(p["factors"]),"independence_groups":" + ".join(p["independence_groups"]),"regimes":json.dumps(p["regimes"]),"walk_forward":json.dumps(p["walk_forward"])})
pd.DataFrame(flat).to_csv(out/"fusion6_pattern_registry.csv",index=False)
calendar={event:{f"-{before}/+{after}":event_window_statistics(frame,event,before,after) for before,after in ((14,30),(7,14),(3,7))} for event in ("thanksgiving","black_friday","christmas","new_year")};calendar["turn_of_month"]=turn_of_month_statistics(frame);calendar["quarters"]=quarter_statistics(frame)
payload={"status":"RESEARCH_ONLY","coverage":result["coverage"],"hypotheses_tested":result["hypotheses_tested"],"promising":[p for p in result["patterns"] if p["status"]=="PROMISING"],"active_patterns":result["active_patterns"],"status_counts":pd.Series([p["status"] for p in result["patterns"]]).value_counts().to_dict(),"longevity_counts":pd.Series([p["longevity"] for p in result["patterns"]]).value_counts().to_dict(),"multiple_testing":result["multiple_testing"],"reverse_study_counts":{k:v["events"] for k,v in result["reverse_studies"].items()},"event_database":{"status":"INSUFFICIENT_DATA","verified_events":0,"reason":"No sourced PIT event dataset; no history invented"},"external_macro":{"status":"INSUFFICIENT_DATA","pre_bitcoin_claims":False},"calendar":calendar,"negative_results":["RSI extreme alone is not promoted","Black Friday is context only","Elliott has no demonstrated incremental value","Legacy SELL rule remains rejected"],"execution":"DISABLED"}
(out/"fusion6_discovery.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8");print(json.dumps({k:payload[k] for k in ("coverage","hypotheses_tested","status_counts","longevity_counts","reverse_study_counts","event_database","negative_results")},indent=2,default=str))
