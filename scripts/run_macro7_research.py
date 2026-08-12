from __future__ import annotations
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/"src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.macro7 import MacroSwingEngine,FullHistoryElliottEngine,MacroSwingResearch

def main():
    config=load_config(root/"config.yaml");frame=OHLCVStore(root/config["data"]["database"]).load("1d");engine=MacroSwingEngine();research=MacroSwingResearch();state=engine.analyze(frame);yearly=research.yearly(frame);swings=research.long_swings(frame);staged=research.ladder_backtest(frame);overlays=research.overlays(frame);replay=FullHistoryElliottEngine().replay(frame,"365D");macro_axes=research.macro_axis_studies(frame)
    reports=root/"data"/"reports";reports.mkdir(parents=True,exist_ok=True);yearly.to_csv(reports/"macro7_yearly.csv",index=False);swings.to_csv(reports/"macro7_long_swings.csv",index=False);staged.to_csv(reports/"macro7_staged_entries.csv",index=False);replay.to_csv(reports/"macro7_elliott_replay.csv",index=False)
    payload={"model":state["model"],"status":"RESEARCH_ONLY","coverage":{"from":frame.index.min(),"to":frame.index.max(),"rows":len(frame)},"current":state,"validation":{"yearly_rows":len(yearly),"long_swing_episodes":len(swings),"signals_per_year":len(swings)/max(1,(frame.index.max()-frame.index.min()).days/365.25),"median_return":None if swings.empty else float(swings["return"].median()),"median_MAE":None if swings.empty else float(swings.MAE.median()),"median_MFE":None if swings.empty else float(swings.MFE.median()),"long_swing_rule":"REJECTED_NO_POSITIVE_MEDIAN_EDGE","staged_samples":len(staged),"elliott_replay_points":len(replay),"elliott_revisions":0 if replay.empty else int(replay.revised.sum()),"elliott_incremental_edge":"NOT_ESTABLISHED_CONTEXT_ONLY","200w_breaks":len(macro_axes["200w"]),"weekly_rsi_extremes":len(macro_axes["weekly_rsi_extremes"]),"monthly_rsi_extremes":len(macro_axes["monthly_rsi_extremes"])},"overlays":overlays,"macro_axis_studies":macro_axes,"execution":"DISABLED"}
    (reports/"macro7_research.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8");print(json.dumps({"coverage":payload["coverage"],"actions":state["actions"],"cycle":state["cycle"],"scenarios":[{"name":x["name"],"status":x["status"],"zone":x["price_zone"]} for x in state["scenarios"]],"indicators":state["indicators"],"validation":payload["validation"]},indent=2,default=str))
if __name__=="__main__":main()
