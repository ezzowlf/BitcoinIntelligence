from __future__ import annotations
import numpy as np
import pandas as pd


def rsi(series,period=14):
    delta=series.diff();gain=delta.clip(lower=0).ewm(alpha=1/period,adjust=False,min_periods=period).mean();loss=-delta.clip(upper=0).ewm(alpha=1/period,adjust=False,min_periods=period).mean();rs=gain/loss.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(100).where(gain.notna())


def bollinger(series,period=20,stddev=2):
    middle=series.rolling(period,min_periods=period).mean();sigma=series.rolling(period,min_periods=period).std(ddof=0);upper=middle+stddev*sigma;lower=middle-stddev*sigma
    return pd.DataFrame({"middle":middle,"upper":upper,"lower":lower,"bandwidth":(upper-lower)/middle.replace(0,np.nan),"percent_b":(series-lower)/(upper-lower).replace(0,np.nan)})


def divergence(price,oscillator,window=20):
    prior_price=price.shift(1).rolling(window,min_periods=window).min();prior_osc=oscillator.shift(1).rolling(window,min_periods=window).min();bull=(price<prior_price)&(oscillator>prior_osc)
    prior_high=price.shift(1).rolling(window,min_periods=window).max();prior_osc_high=oscillator.shift(1).rolling(window,min_periods=window).max();bear=(price>prior_high)&(oscillator<prior_osc_high)
    return pd.DataFrame({"bullish":bull.fillna(False),"bearish":bear.fillna(False)})


def _status(close,row):
    if pd.isna(row["upper"]):return "UNAVAILABLE"
    return "ABOVE" if close>row["upper"] else "BELOW" if close<row["lower"] else "INSIDE"


def multi_timeframe_indicators(frame,as_of=None,four_hour=None):
    visible=frame.loc[:as_of].copy() if as_of is not None else frame.copy();daily=visible["close"]
    series={"daily":daily,"weekly":daily.resample("W-MON",label="right",closed="right").last().dropna(),"monthly":daily.resample("ME").last().dropna()}
    if four_hour is not None and not four_hour.empty:series={"4h":four_hour.loc[:as_of,"close"],**series}
    result={}
    for name,close in series.items():
        values=rsi(close);bb=bollinger(close);row=bb.iloc[-1]
        result[name]={"rsi":None if pd.isna(values.iloc[-1]) else round(float(values.iloc[-1]),2),"bollinger":{"middle":None if pd.isna(row.middle) else float(row.middle),"upper":None if pd.isna(row.upper) else float(row.upper),"lower":None if pd.isna(row.lower) else float(row.lower),"bandwidth":None if pd.isna(row.bandwidth) else float(row.bandwidth),"percent_b":None if pd.isna(row.percent_b) else float(row.percent_b),"state":_status(float(close.iloc[-1]),row)}}
    if "4h" not in result:result["4h"]={"rsi":None,"bollinger":{"state":"UNAVAILABLE"},"status":"UNAVAILABLE"}
    r365=rsi(daily,365);result["rsi_365d"]={"value":None if pd.isna(r365.iloc[-1]) else round(float(r365.iloc[-1]),2),"status":"RESEARCH"}
    wd=divergence(series["weekly"],rsi(series["weekly"]));dd=divergence(daily,rsi(daily));result["divergence"]={"daily_bullish":bool(dd.bullish.iloc[-1]),"daily_bearish":bool(dd.bearish.iloc[-1]),"weekly_bullish":bool(wd.bullish.iloc[-1]),"weekly_bearish":bool(wd.bearish.iloc[-1]),"status":"RESEARCH"}
    return result
