from __future__ import annotations
import numpy as np
import pandas as pd


def event_metrics(frame:pd.DataFrame,events:pd.DataFrame,horizons=(1,7,30,90))->dict:
    close=frame.close.astype(float); rows=[]
    for event in events.itertuples():
        if event.Index not in close.index: continue
        loc=close.index.get_loc(event.Index); future=close.iloc[loc:min(len(close),loc+max(horizons)+1)]/close.iloc[loc]-1
        row={"timestamp":event.Index,"state":event.state,"mae":float(future.min()),"mfe":float(future.max())}
        for horizon in horizons: row[f"return_{horizon}d"]=None if loc+horizon>=len(close) else float(close.iloc[loc+horizon]/close.iloc[loc]-1)
        rows.append(row)
    return {"raw_observations":len(rows),"rows":rows}


def false_confirmation(rows,threshold=-.1,horizon="return_30d"):
    confirmed=[row for row in rows if row["state"]=="CONFIRMED" and row.get(horizon) is not None]; failed=[row for row in confirmed if row["mae"]<=threshold]
    return {"confirmed_setups":len(confirmed),"failed":len(failed),"false_confirmation_rate":None if not confirmed else len(failed)/len(confirmed)}


def conditional_performance(rows,condition):
    selected=[row for row in rows if condition(row)]
    return {"n":len(selected),"median_30d":None if not selected else float(np.median([r["return_30d"] for r in selected if r["return_30d"] is not None])),
            "median_90d":None if not selected else float(np.median([r["return_90d"] for r in selected if r["return_90d"] is not None])),
            "mae":None if not selected else float(np.median([r["mae"] for r in selected]))}


def monotonicity(scores:pd.Series,outcomes:pd.Series)->dict:
    bins=pd.cut(scores,[0,20,40,60,80,100],include_lowest=True); medians=outcomes.groupby(bins,observed=False).median().to_dict()
    values=[value for value in medians.values() if pd.notna(value)]; return {"bins":{str(key):None if pd.isna(value) else float(value) for key,value in medians.items()},"monotone":all(a<=b for a,b in zip(values,values[1:]))}
