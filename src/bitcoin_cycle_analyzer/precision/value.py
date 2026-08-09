from __future__ import annotations
import numpy as np
import pandas as pd


def value_engine(frame:pd.DataFrame,cycle:dict,technical:dict,as_of=None)->dict:
    visible=frame.loc[:pd.Timestamp(as_of)] if as_of is not None else frame
    close=visible.close.astype(float); price=float(close.iloc[-1]); ath=float(close.cummax().iloc[-1]); dd=price/ath-1
    ma200=float(close.rolling(200,min_periods=30).mean().iloc[-1]); trend_discount=max(-1,min(1,ma200/price-1))
    months=float(cycle["halving"]["months_since"]); cycle_context=max(0,min(1,1-abs(months-30)/30))
    drawdown_component=max(0,min(1,abs(dd)/.75)); trend_component=max(0,min(1,.5+trend_discount*2))
    score=round((.55*drawdown_component+.25*trend_component+.2*cycle_context)*100,2)
    historical_dd=close/close.cummax()-1; attractiveness=(-historical_dd).rank(pct=True)
    percentile=round(float(attractiveness.iloc[-1])*100,1)
    label="EXTREME_VALUE" if score>=85 else "HIGH_VALUE" if score>=65 else "FAIR" if score>=40 else "EXPENSIVE" if score>=20 else "EXTREME_EXPENSIVE"
    return {"score":score,"state":label,"historical_percentile":percentile,"inputs":{"ath_drawdown":dd,"ma200_relation":price/ma200-1,"months_since_halving":months},
            "excluded_inputs":["h4_timing","funding","intraday_oi","news"],"status":"PARTIALLY_VALIDATED"}
