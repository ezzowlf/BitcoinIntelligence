from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from ..advanced.indicators import rsi


HORIZONS=(1,7,30,90,180,365)
def _outcomes(frame,i,direction):
    price=float(frame.close.iloc[i]);result={}
    for h in HORIZONS:
        future=frame.iloc[i+1:min(len(frame),i+h+1)]
        result[f"return_{h}d"]=None if len(future)<h else float(future.close.iloc[-1]/price-1)
        result[f"MAE_{h}d"]=None if future.empty else float(future.low.min()/price-1)
        result[f"MFE_{h}d"]=None if future.empty else float(future.high.max()/price-1)
    future=frame.iloc[i+1:min(len(frame),i+91)];result["maximum_decline_after_signal"]=None if future.empty else float(future.low.min()/price-1);result["missed_upside_before_decline"]=None if future.empty else float(future.high.max()/price-1);result["false_sell_30d"]=None if direction!="SELL" or len(future)<30 else bool(future.high.iloc[:30].max()/price-1>.15 and future.low.iloc[:30].min()/price-1>-.10)
    return result


def build_historical_signal_book(frame):
    close=frame.close;ath=close.cummax();dd=close/ath-1;r=rsi(close);ma200=close.rolling(200).mean();weekly=close.resample("W-MON").last();wrsi=rsi(weekly).reindex(frame.index,method="ffill");breakdown=close<frame.low.shift(1).rolling(30).min();records=[];last={}
    for i in range(365,len(frame)-1):
        buy_groups=sum([dd.iloc[i]<=-.4,close.iloc[i]<ma200.iloc[i],wrsi.iloc[i]<35,r.iloc[i]<35]);near_major_high=frame.high.iloc[max(0,i-60):i].max()>=ath.iloc[i]*.90;overvalued=(close.iloc[i]/ma200.iloc[i]>1.5) or (wrsi.iloc[i]>75);distribution=near_major_high and r.iloc[i]<55;sell_groups=sum([overvalued,distribution,breakdown.iloc[i],close.iloc[i]<close.iloc[i-14]])
        signal="BUY" if buy_groups>=4 else "ACCUMULATE" if buy_groups>=3 else "SELL" if sell_groups>=4 else "REDUCE" if sell_groups>=3 else None
        if signal is None or (signal in last and (frame.index[i]-last[signal]).days<30):continue
        last[signal]=frame.index[i];direction="SELL" if signal in {"SELL","REDUCE"} else "BUY";price=float(close.iloc[i]);window=frame.iloc[max(0,i-90):min(len(frame),i+91)];local_low=float(window.low.min());local_high=float(window.high.max())
        row={"signal_id":hashlib.sha256(f"{frame.index[i]}|{signal}".encode()).hexdigest()[:16],"date":frame.index[i],"price":price,"signal_type":signal,"level":"PRODUCTION" if signal in {"BUY","SELL"} else "CANDIDATE","market_state":"HISTORICAL_RESEARCH","regime":"BEAR" if close.iloc[i]<ma200.iloc[i] else "BULL","value":round(abs(float(dd.iloc[i]))*100,2),"timing":"RESEARCH_PROXY","risk":None,"evidence":"RESEARCH_ONLY","confluence":buy_groups if direction=="BUY" else sell_groups,"reason_codes":[],"zone":None,"invalidation":None,"days_after_local_low":int((frame.index[i]-window.low.idxmin()).days),"percent_above_local_low":price/local_low-1,"days_after_local_high":int((frame.index[i]-window.high.idxmax()).days),"percent_below_local_high":price/local_high-1,**_outcomes(frame,i,direction)};records.append(row)
    return pd.DataFrame(records)
