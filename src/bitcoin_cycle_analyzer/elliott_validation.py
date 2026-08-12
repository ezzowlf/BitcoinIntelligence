from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from .elliott_wave import analyze_scenarios
from .swing_detection import detect_swings,swings_as_of

def replay_elliott(frame:pd.DataFrame,frequency="30D",start=None):
    """Historical PIT replay over predeclared calendar checkpoints."""
    swings=detect_swings(frame);start=pd.Timestamp(start or frame.index[min(730,len(frame)-1)])
    if getattr(frame.index,"tz",None) is not None and start.tzinfo is None:start=start.tz_localize(frame.index.tz)
    cutoffs=pd.date_range(start,frame.index[-1],freq=frequency)
    rows=[];previous=None
    for cutoff in cutoffs:
        known=swings_as_of(swings,cutoff);scenarios=analyze_scenarios(known);primary=scenarios[0];recent=known.tail(5)
        name=primary["name"];changed=previous is not None and name!=previous
        rows.append({"timestamp":cutoff,"primary_count":name,"alternative_counts":[x["name"] for x in scenarios[1:]],"relative_support":primary["confidence"],"invalidation":None if recent.empty else float(recent.price.min()),"confirmation":None if recent.empty else float(recent.price.max()),"reason_for_change":"NEW_CONFIRMED_SWING_STRUCTURE" if changed else "UNCHANGED","used_swing_count":len(known),"max_confirmed_at":None if known.empty else known.confirmed_at.max()});previous=name
    ledger=pd.DataFrame(rows)
    if ledger.empty:return ledger,{"status":"INSUFFICIENT_DATA"}
    ledger["changed"]=ledger.primary_count.ne(ledger.primary_count.shift());groups=ledger.changed.cumsum();durations=ledger.groupby(groups).timestamp.agg(lambda x:(x.max()-x.min()).days+30)
    invalidated=[]
    for i,row in ledger.iterrows():
        end=ledger.iloc[i+1].timestamp if i+1<len(ledger) else frame.index[-1];future=frame.loc[row.timestamp:end]
        invalidated.append(bool(row.invalidation is not None and not future.empty and future.low.min()<row.invalidation))
    ledger["invalidated_before_next_checkpoint"]=invalidated;revisions=max(0,int(ledger.changed.sum())-1)
    stats={"status":"RESEARCH_ONLY","checkpoints":len(ledger),"primary_revisions":revisions,"revisions_per_30d":round(revisions/len(ledger),4),"revisions_per_90d":round(revisions/len(ledger)*3,4),"average_count_duration_days":round(float(durations.mean()),1),"median_count_duration_days":round(float(durations.median()),1),"invalidation_rate":round(float(ledger.invalidated_before_next_checkpoint.mean()),4),"pit_violations":int(((ledger.max_confirmed_at.notna())&(ledger.max_confirmed_at>ledger.timestamp)).sum()),"factor_status":"CONTEXT_ONLY"}
    return ledger,stats

def write_revision_ledger(path:Path,ledger:pd.DataFrame):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8") as f:
        for row in ledger.to_dict("records"):f.write(json.dumps(row,default=str,ensure_ascii=False)+"\n")
