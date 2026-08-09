from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class DrawdownCycleEngine:
    minimum:float=-.20
    def analyze(self,frame,as_of=None):
        visible=frame.loc[:as_of].copy() if as_of is not None else frame.copy();close=visible.close;ath=close.cummax();dd=close/ath-1;cycles=[];peak_i=0;i=1
        while i<len(close):
            if close.iloc[i]>=close.iloc[peak_i]:peak_i=i;i+=1;continue
            trough_i=i
            while i+1<len(close) and close.iloc[i+1]<close.iloc[peak_i]:
                i+=1
                if close.iloc[i]<close.iloc[trough_i]:trough_i=i
            depth=close.iloc[trough_i]/close.iloc[peak_i]-1
            if depth<=self.minimum:
                recovered=i if i<len(close) and close.iloc[i]>=close.iloc[peak_i] else None
                cycles.append({"peak_date":close.index[peak_i],"peak_price":float(close.iloc[peak_i]),"trough_date":close.index[trough_i],"trough_price":float(close.iloc[trough_i]),"drawdown":float(depth),"days_to_trough":int((close.index[trough_i]-close.index[peak_i]).days),"recovery_date":None if recovered is None else close.index[recovered],"days_to_ath_recovery":None if recovered is None else int((close.index[recovered]-close.index[trough_i]).days),"recovery_gain":float(close.iloc[-1]/close.iloc[trough_i]-1) if recovered is None else float(close.iloc[recovered]/close.iloc[trough_i]-1)})
            if i>=len(close):break
            peak_i=i;i+=1
        current=float(dd.iloc[-1]);severity=float((dd.dropna()<=current).mean()*100);days_under=int((visible.index[-1]-ath[ath==close].index[-1]).days);last_low=close.loc[ath[ath==close].index[-1]:].idxmin();recovery=float(close.iloc[-1]/close.loc[last_low]-1)
        state="NEW_EXPANSION" if current==0 else "EXTREME_DRAWDOWN" if current<=-.7 else "DEEP_DRAWDOWN" if current<=-.4 else "MID_DRAWDOWN" if current<=-.2 else "EARLY_DRAWDOWN"
        if current>-.2 and recovery>.3:state="RECOVERY" if current<-.05 else "LATE_RECOVERY"
        return {"current_drawdown":current,"historical_severity_percentile":round(severity,2),"maximum_historical_drawdown":float(dd.min()),"days_below_previous_ath":days_under,"drawdown_velocity":{"7d":float(close.pct_change(7).iloc[-1]),"30d":float(close.pct_change(30).iloc[-1]),"90d":float(close.pct_change(90).iloc[-1])},"last_major_low":last_low,"recovery_from_major_low":recovery,"state":state,"cycles":cycles,"status":"RESEARCH"}
