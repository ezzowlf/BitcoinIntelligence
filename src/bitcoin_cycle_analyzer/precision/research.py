from __future__ import annotations
import pandas as pd


def era_diagnostics(frame:pd.DataFrame)->dict:
    returns=frame.close.astype(float).pct_change().dropna(); boundaries=[("EARLY_BITCOIN",None,"2017-12-31"),("DERIVATIVES_ERA","2018-01-01","2023-12-31"),("ETF_ERA","2024-01-01",None)]
    eras={}
    for name,start,end in boundaries:
        series=returns
        if start: series=series.loc[pd.Timestamp(start,tz="UTC"):]
        if end: series=series.loc[:pd.Timestamp(end,tz="UTC")]
        eras[name]={"n":len(series),"daily_volatility":None if series.empty else float(series.std()),"median_return":None if series.empty else float(series.median())}
    return {"status":"RESEARCH","eras":eras,"note":"Era labels are diagnostics, not hardcoded model weights."}


def holdout_registry()->dict:
    return {"2011-2024":"USED_FOR_RESEARCH","2024-10-29_to_present":"USED_FOR_RESEARCH","final_holdout":"NOT_AVAILABLE_YET",
            "note":"A new untouched temporal holdout requires future observations."}
