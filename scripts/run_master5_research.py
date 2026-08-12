from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import pandas as pd
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.master5 import build_master5_signal_book,summarize_signal_book,factor_performance,error_taxonomy

root=Path(__file__).resolve().parents[1];config=load_config(root/"config.yaml");frame=OHLCVStore(root/config["data"]["database"]).load("1d")
book=build_master5_signal_book(frame);summary=summarize_signal_book(book);factors=factor_performance(book)
entries_path=root/"BITCOIN_ENTRY_EPISODES.csv";entries=pd.read_csv(entries_path) if entries_path.exists() else pd.DataFrame();errors=error_taxonomy(frame,book,entries)
out=root/"data"/"reports";out.mkdir(parents=True,exist_ok=True);book.to_csv(out/"master5_signal_book.csv",index=False);factors.to_csv(out/"master5_factor_performance.csv",index=False);errors.to_csv(out/"master5_error_taxonomy.csv",index=False)
payload={"summary":summary,"best_buy_factors":factors[factors.direction=="BUY"].sort_values(["false_rate","n"],ascending=[True,False]).head(10).to_dict("records"),"best_risk_factors":factors[factors.direction=="RISK"].sort_values(["false_rate","n"],ascending=[True,False]).head(10).to_dict("records"),"errors":errors.type.value_counts().to_dict() if not errors.empty else {},"thresholds_predeclared":True,"frequency_not_optimized":True,"old_sell_rule":"REJECTED","elliott":"CONTEXT_ONLY_NOT_COUNTED","news":"INSUFFICIENT_DATA","execution":"DISABLED"}
(out/"master5_research.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8");print(json.dumps(payload,indent=2,default=str))
