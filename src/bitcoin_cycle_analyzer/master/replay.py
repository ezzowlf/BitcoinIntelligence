from __future__ import annotations
import pandas as pd
from ..rare_signals import build_historical_signal_book


def build_master_historical_signal_book(frame):
    source=build_historical_signal_book(frame);rows=[];errors=[]
    for row in source.to_dict("records"):
        signal=row["signal_type"]
        if signal=="SELL":
            errors.append({"date":row["date"],"error":"FALSE_SELL" if row.get("false_sell_30d") else "REJECTED_SELL_PROXY","source_signal":"SELL","master_action":"HOLD","missed_upside":row.get("missed_upside_before_decline")});continue
        if signal not in {"BUY","REDUCE"}:continue
        row.update({"master_signal":signal,"master_version":"MASTER-3.0-RESEARCH","source_2_3":"VALUE_CONTEXT" if signal=="BUY" else "RISK_CONTEXT","source_2_5":signal,"research_status":"RESEARCH_ONLY"});rows.append(row)
    return pd.DataFrame(rows),pd.DataFrame(errors)


def model_comparison(row):
    return {"2.3":row.get("source_2_3"),"2.5":row.get("source_2_5"),"MASTER":row.get("master_signal"),"method":"hierarchy, not voting"}
