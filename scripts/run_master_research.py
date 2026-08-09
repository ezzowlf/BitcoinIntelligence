from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.master.replay import build_master_historical_signal_book


def main():
    cfg=load_config(ROOT/"config.yaml");frame=OHLCVStore(ROOT/cfg["data"]["database"]).load("1d");book,errors=build_master_historical_signal_book(frame);reports=ROOT/"data"/"reports";reports.mkdir(parents=True,exist_ok=True);book.to_csv(reports/"master_historical_signal_book.csv",index=False);errors.to_csv(reports/"master_error_taxonomy.csv",index=False)
    frequency=book.assign(year=pd.to_datetime(book.date).dt.year).pivot_table(index="year",columns="master_signal",values="signal_id",aggfunc="count",fill_value=0).astype(int) if not book.empty else pd.DataFrame()
    performance={}
    for name,group in book.groupby("master_signal"):
        performance[name]={field:{"n":int(group[field].notna().sum()),"median":None if group[field].dropna().empty else float(group[field].median())} for field in ("return_30d","return_90d","return_180d","return_365d","MAE_90d","MFE_90d")}
    payload={"status":"RESEARCH_ONLY","model":"MASTER-3.0","signals":len(book),"frequency":frequency.to_dict(orient="index"),"performance":performance,"errors":errors.to_dict("records"),"sell_production_status":"DISABLED_FOR_PRODUCTION","note":"Rejected 2.5 historical SELL proxy is isolated; no threshold re-optimization."};(reports/"master_30_research.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8");print(json.dumps({"signals":len(book),"errors":len(errors),"frequency":payload["frequency"],"performance":performance},indent=2))
if __name__=="__main__":main()
