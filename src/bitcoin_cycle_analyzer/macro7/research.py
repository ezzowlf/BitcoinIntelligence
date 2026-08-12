from __future__ import annotations
import numpy as np
import pandas as pd
from ..research.best_entries import causal_feature_frame
from ..advanced.indicators import rsi

class MacroSwingResearch:
    def yearly(self,frame):
        y=frame.resample("YE",label="right",closed="right").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna();y["return"]=y.close/y.open-1;y["max_drawdown"]=y.low/y.open-1;y["year"]=y.index.year;y["rolling_2y_return"]=y.close/y.close.shift(2)-1;y["rolling_4y_return"]=y.close/y.close.shift(4)-1;y["yearly_roc"]=y.close.pct_change();return y
    def overlays(self,frame):
        close=frame.close;ath=close.cummax();dd=close/ath-1;halvings=pd.to_datetime(["2012-11-28","2016-07-09","2020-05-11","2024-04-20"],utc=True)
        halving=[]
        for h in halvings:
            s=close.loc[h:h+pd.Timedelta(days=1500)]
            if not s.empty:halving.append({"anchor":h,"points":[{"day":(t-h).days,"normalized":float(v/s.iloc[0])} for t,v in s.resample("7D").last().items()]})
        peaks=close[(close==ath)&(dd.shift(-180).fillna(0)<-.2)].index;ath_paths=[]
        for p in peaks[::max(1,len(peaks)//8 or 1)]:
            s=close.loc[p:p+pd.Timedelta(days=730)];ath_paths.append({"anchor":p,"points":[{"day":(t-p).days,"drawdown":float(v/close.loc[p]-1)} for t,v in s.resample("7D").last().items()]})
        return {"halving":halving,"ath_drawdowns":ath_paths}
    def long_swings(self,frame):
        f=causal_feature_frame(frame);entry=(f.drawdown<=-.30)&((f.distance_200w<=.08)|(f.rsi_weekly<=42));entry=entry & ~entry.shift(1,fill_value=False);rows=[]
        for ts in f.index[entry]:
            future=frame.loc[ts:ts+pd.Timedelta(days=180)]
            if len(future)<15:continue
            exit_ts=future.index[-1];price=float(frame.loc[ts,"close"]);exit_price=float(future.close.iloc[-1]);rows.append({"entry_date":ts,"entry_price":price,"exit_date":exit_ts,"exit_price":exit_price,"return":exit_price/price-1,"MAE":float(future.low.min()/price-1),"MFE":float(future.high.max()/price-1),"duration":(exit_ts-ts).days,"regime":f.loc[ts,"regime"],"entry_archetype":"DEEP_VALUE" if f.loc[ts,"drawdown"]<=-.5 else "SUPPORT_RETEST","signal_input":"PIT"})
        return pd.DataFrame(rows)
    def ladder_backtest(self,frame,levels=(-.2,-.35,-.5,-.65)):
        ath=frame.close.cummax();rows=[]
        for ts in frame.index[::90]:
            known_ath=float(ath.loc[ts]);future=frame.loc[ts:ts+pd.Timedelta(days=365)];fills=[]
            for dd in levels:
                target=known_ath*(1+dd);hit=future[future.low<=target]
                if not hit.empty:fills.append(target)
            if fills:avg=float(np.mean(fills));rows.append({"date":ts,"stages_filled":len(fills),"average_entry":avg,"MAE":float(future.low.min()/avg-1),"return_365d":float(future.close.iloc[-1]/avg-1),"capital_timing":len(fills)/len(levels)})
        return pd.DataFrame(rows)
    def macro_axis_studies(self,frame):
        close=frame.close;ma200w=close.rolling(1400).mean();below=close<ma200w;cross_below=below & ~below.shift(1,fill_value=False);cross_above=~below & below.shift(1,fill_value=False);events=[]
        for ts in close.index[cross_below]:
            future=frame.loc[ts:ts+pd.Timedelta(days=730)];reclaim=cross_above.loc[ts:].loc[cross_above.loc[ts:]].index.min() if cross_above.loc[ts:].any() else None
            events.append({"break_date":ts,"price":float(close.loc[ts]),"weeks_below":None if reclaim is None else (reclaim-ts).days/7,"reclaim":reclaim,"additional_drawdown":None if future.empty else float(future.low.min()/close.loc[ts]-1),"return_1y":None if len(future)<365 else float(future.close.iloc[364]/close.loc[ts]-1),"return_2y":None if len(future)<700 else float(future.close.iloc[-1]/close.loc[ts]-1)})
        weekly=close.resample("W-MON").last();monthly=close.resample("ME").last();wrsi=rsi(weekly);mrsi=rsi(monthly)
        def extremes(series,low,high):
            rows=[]
            for ts in series.index[(series<=low)|(series>=high)]:
                future=close.loc[ts:ts+pd.Timedelta(days=365)]
                if len(future)>=300:rows.append({"date":ts,"rsi":float(series.loc[ts]),"side":"LOW" if series.loc[ts]<=low else "HIGH","return_365d":float(future.iloc[-1]/future.iloc[0]-1),"MAE":float(future.min()/future.iloc[0]-1)})
            return rows
        return {"200w":events,"weekly_rsi_extremes":extremes(wrsi,30,70),"monthly_rsi_extremes":extremes(mrsi,35,75)}
