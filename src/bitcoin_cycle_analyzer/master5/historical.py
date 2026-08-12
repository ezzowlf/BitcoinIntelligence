from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from ..research.best_entries import causal_feature_frame,add_outcomes

def build_master5_signal_book(frame:pd.DataFrame)->pd.DataFrame:
    f=add_outcomes(causal_feature_frame(frame),frame);close=frame.close;rolling_low=frame.low.shift(1).rolling(730,min_periods=180).min();support=close<=rolling_low*1.12
    groups=pd.DataFrame({"deep_drawdown":f.drawdown<=-.4,"major_support":support,"high_value":f.value_score>=55,"below_200d":f.distance_200d<0,"below_200w":f.distance_200w<0,"daily_rsi_weak":f.rsi_daily<30,"weekly_rsi_weak":f.rsi_weekly<35,"capitulation":f.capitulation_state=="CAPITULATION"}).fillna(False);n=groups.sum(axis=1)
    buy=np.select([(groups.deep_drawdown&groups.major_support&(n>=6)&(groups.capitulation|groups.weekly_rsi_weak)),(groups.deep_drawdown&groups.major_support&(n>=5)),(support&(n>=3)),n>=2],["HISTORICAL_EXTREME","STRONG_BUY_CANDIDATE","BUY_ZONE","WATCH_BUY"],default="NO_BUY")
    ma200=close.rolling(200).mean();weekly=close.resample("W-MON",label="right",closed="right").last().dropna();lower_high=(weekly.rolling(8).max()<weekly.shift(8).rolling(8).max()).reindex(close.index,method="ffill").fillna(False);support_loss=(weekly<weekly.shift(1).rolling(12).min()).reindex(close.index,method="ffill").fillna(False)
    risk_groups=pd.DataFrame({"extended_200d":close/ma200>1.45,"weekly_rsi_extreme":f.rsi_weekly>75,"monthly_rsi_extreme":f.rsi_monthly>80,"bollinger_extension":f.bollinger_weekly_position=="ABOVE_UPPER","ath_proximity":close>=close.cummax()*.95,"lower_high":lower_high,"weekly_support_loss":support_loss,"volatility_expansion":close.pct_change().rolling(14).std()>close.pct_change().rolling(365).std().rolling(365,min_periods=100).quantile(.8)}).fillna(False);rn=risk_groups.sum(axis=1);structure=risk_groups.lower_high|risk_groups.weekly_support_loss
    risk=np.select([(rn>=5)&structure,(rn>=4)&structure,rn>=3,rn>=1],["HIGH_RISK_DISTRIBUTION","DISTRIBUTION_CONFIRMED","DISTRIBUTION_CANDIDATE","WATCH"],default="NONE")
    raw=pd.DataFrame({"buy_state":buy,"risk_state":risk,"buy_groups":n,"risk_groups":rn},index=frame.index);changed=(raw.buy_state.ne(raw.buy_state.shift())|raw.risk_state.ne(raw.risk_state.shift()));events=raw[changed&(raw.index>=f.index[min(365,len(f)-1)])].copy();events=events[(events.buy_state!="NO_BUY")|(events.risk_state!="NONE")]
    rows=[]
    for ts,row in events.iterrows():
        i=frame.index.get_loc(ts);future=frame.iloc[i+1:min(len(frame),i+366)];price=float(close.loc[ts]);bf=[c for c in groups if groups.loc[ts,c]];rf=[c for c in risk_groups if risk_groups.loc[ts,c]]
        direction="BUY" if row.buy_state!="NO_BUY" else "RISK";mae=None if future.empty else float(future.low.min()/price-1);mfe=None if future.empty else float(future.high.max()/price-1)
        rows.append({"event_id":hashlib.sha256(f"{ts}|{row.buy_state}|{row.risk_state}".encode()).hexdigest()[:16],"timestamp":ts,"signal":row.buy_state if direction=="BUY" else row.risk_state,"direction":direction,"price":price,"archetype":"DEEP_CAPITULATION" if groups.loc[ts,"capitulation"] else "HISTORICAL_SUPPORT_RETEST" if groups.loc[ts,"major_support"] else "BEAR_MARKET_VALUE" if groups.loc[ts,"deep_drawdown"] else "CYCLE_ACCUMULATION","factors":bf if direction=="BUY" else rf,"regime":f.loc[ts,"regime"],"return_30d":f.loc[ts,"return_30d"],"return_90d":f.loc[ts,"return_90d"],"return_180d":f.loc[ts,"return_180d"],"return_365d":f.loc[ts,"return_365d"],"MAE":mae,"MFE":mfe,"false_signal":bool((direction=="BUY" and pd.notna(mae) and mae<=-.30 and (mfe or 0)<.20) or (direction=="RISK" and pd.notna(mae) and mae>-.10)),"status":"HISTORICAL_RESEARCH_ONLY"})
    return pd.DataFrame(rows)

def summarize_signal_book(book:pd.DataFrame)->dict:
    if book.empty:return {"status":"INSUFFICIENT_DATA"}
    years=max(1,(pd.Timestamp(book.timestamp.max())-pd.Timestamp(book.timestamp.min())).days/365.25);freq=book.groupby("signal").size().div(years).round(2).to_dict();false=book.groupby("direction").false_signal.mean().round(3).to_dict();return {"status":"RESEARCH_ONLY","years":round(years,2),"events":len(book),"frequency_per_year":freq,"false_signal_rate":false,"buy_events":int((book.direction=="BUY").sum()),"risk_events":int((book.direction=="RISK").sum()),"method":"causal features; state changes only; thresholds predeclared before output inspection"}

def factor_performance(book:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for direction in ("BUY","RISK"):
        part=book[book.direction==direction]
        factors=sorted({factor for values in part.factors for factor in values})
        for factor in factors:
            group=part[part.factors.map(lambda values:factor in values)]
            rows.append({"direction":direction,"factor":factor,"n":len(group),"median_30d":group.return_30d.median(),"median_90d":group.return_90d.median(),"median_365d":group.return_365d.median(),"median_MAE":group.MAE.median(),"median_MFE":group.MFE.median(),"false_rate":group.false_signal.mean(),"status":"INSUFFICIENT_DATA" if len(group)<5 else "RESEARCH_ONLY"})
    return pd.DataFrame(rows)

def error_taxonomy(frame:pd.DataFrame,book:pd.DataFrame,best_entries:pd.DataFrame|None=None)->pd.DataFrame:
    rows=[]
    for row in book.itertuples():
        if row.false_signal:rows.append({"timestamp":row.timestamp,"type":"FALSE_BUY" if row.direction=="BUY" else "FALSE_SELL","signal":row.signal,"detail":"predeclared adverse/outcome condition"})
    if best_entries is not None and not best_entries.empty:
        buys=pd.to_datetime(book.loc[book.direction=="BUY","timestamp"],utc=True)
        for date in pd.to_datetime(best_entries.date,utc=True):
            if buys.empty or not ((buys-date).abs()<=pd.Timedelta(days=30)).any():rows.append({"timestamp":date,"type":"MISSED_BUY","signal":None,"detail":"top-entry reference without challenger BUY within 30D"})
    close=frame.close;future_low=frame.low.shift(-1)[::-1].rolling(90,min_periods=90).min()[::-1];crash=(future_low/close-1)<=-.20;selected=[]
    for date in frame.index[crash.fillna(False)]:
        if not selected or (date-selected[-1]).days>=90:selected.append(date)
    risks=pd.to_datetime(book.loc[book.direction=="RISK","timestamp"],utc=True)
    for date in selected:
        if risks.empty or not (((risks-date)<=pd.Timedelta(0))&((risks-date)>=-pd.Timedelta(days=30))).any():rows.append({"timestamp":date,"type":"MISSED_SELL","signal":None,"detail":">=20% forward 90D drawdown without prior 30D risk event"})
    return pd.DataFrame(rows)
