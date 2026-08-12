from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from ..advanced.indicators import rsi,bollinger
from ..advanced.zones import HistoricalZoneEngine
from ..fibonacci import levels
from .elliott import FullHistoryElliottEngine
from .research import MacroSwingResearch

def _zone(low,high,horizon,evidence,status="AVAILABLE"):
    groups=sorted(set(x[0] for x in evidence));return {"low":round(float(low),2),"high":round(float(high),2),"horizon":horizon,"evidence":[x[1] for x in evidence],"independent_groups":groups,"status":status,"support":"HIGH" if len(groups)>=4 else "MODERATE" if len(groups)>=2 else "LOW"}

@dataclass
class MacroSwingEngine:
    version:str="MACRO_SWING_7_0_RESEARCH"
    def _ladder(self,frame):
        ath=float(frame.high.cummax().iloc[-1]);current=float(frame.close.iloc[-1]);rows=[]
        for dd in (-.1,-.2,-.3,-.4,-.5,-.6,-.7,-.8,-.85,-.9):
            price=ath*(1+dd);historical=frame[frame.close/frame.high.cummax()-1<=dd];samples=historical.iloc[::90];outcomes=[];mae=[]
            for ts in samples.index:
                future=frame.loc[ts:ts+pd.Timedelta(days=365)]
                if len(future)>=300:outcomes.append(float(future.close.iloc[-1]/frame.loc[ts,"close"]-1));mae.append(float(future.low.min()/frame.loc[ts,"close"]-1))
            rows.append({"drawdown":dd,"price":price,"current_marker":abs(current-price)==min(abs(current-ath*(1+x)) for x in (-.1,-.2,-.3,-.4,-.5,-.6,-.7,-.8,-.85,-.9)),"historical_frequency":len(samples),"median_365d_return":None if not outcomes else float(np.median(outcomes)),"median_further_MAE":None if not mae else float(np.median(mae)),"historical_archetypes":["BEAR","CAPITULATION"] if dd<=-.5 else ["CORRECTION","ACCUMULATION"]})
        return {"ath":ath,"current_drawdown":current/ath-1,"levels":rows}
    def _phase(self,frame):
        close=frame.close;ath=close.cummax();dd=close/ath-1;recovery=close/close.rolling(365,min_periods=90).min()-1;ma200=close.rolling(200).mean();current={"dd":float(dd.iloc[-1]),"recovery":float(recovery.iloc[-1]),"above200":bool(close.iloc[-1]>ma200.iloc[-1])}
        if current["dd"]<=-.55 and current["recovery"]<.15:phase="CAPITULATION"
        elif current["dd"]<=-.35 and current["recovery"]<.25:phase="BEAR"
        elif current["dd"]<=-.25 and current["recovery"]>=.25:phase="EARLY_RECOVERY"
        elif current["dd"]<=-.2:phase="ACCUMULATION"
        elif current["dd"]>-.1 and current["above200"]:phase="EXPANSION"
        else:phase="TRANSITION"
        daily=[]
        for ts in frame.index:
            x=float(dd.loc[ts]);r=float(recovery.loc[ts]) if pd.notna(recovery.loc[ts]) else 0;a=bool(close.loc[ts]>ma200.loc[ts]) if pd.notna(ma200.loc[ts]) else False
            daily.append("CAPITULATION" if x<=-.55 and r<.15 else "BEAR" if x<=-.35 and r<.25 else "EARLY_RECOVERY" if x<=-.25 and r>=.25 else "ACCUMULATION" if x<=-.2 else "EXPANSION" if x>-.1 and a else "TRANSITION")
        s=pd.Series(daily,index=frame.index);change=s.ne(s.shift()).cumsum();durations=s.groupby(change).agg(["first","size"]);same=durations[durations["first"]==phase]["size"];age=int((s.iloc[::-1]==phase).cumprod().sum())
        return {"phase":phase,"confidence":"MODERATE","days_in_state":age,"historical_duration":{"median":None if same.empty else float(same.median()),"min":None if same.empty else int(same.min()),"max":None if same.empty else int(same.max())}}
    def analyze(self,frame,control=None,specialist=None,fusion=None,four_hour=None):
        close=frame.close.astype(float);price=float(close.iloc[-1]);ath=float(frame.high.cummax().iloc[-1]);ma200=float(close.rolling(200).mean().iloc[-1]);ma200w=float(close.rolling(1400).mean().iloc[-1]);weekly=close.resample("W-MON").last();monthly=close.resample("ME").last();weekly_rsi=float(rsi(weekly).iloc[-1]);monthly_rsi=float(rsi(monthly).iloc[-1]);ladder=self._ladder(frame);phase=self._phase(frame)
        # HTF anchors and Fib share a structure group and therefore never count independently.
        cycle_low=float(frame.low.loc[frame.index>=frame.index[-1]-pd.Timedelta(days=1460)].min());fib=[x for x in levels(cycle_low,ath) if x.kind=="retracement"]
        hz=HistoricalZoneEngine().analyze(frame,fib_levels=[x.price for x in fib]);supports=[z for z in hz if z["upper_bound"]<price];resistances=[z for z in hz if z["lower_bound"]>price]
        nearest_support=max(supports,key=lambda x:x["upper_bound"],default=None);nearest_resistance=min(resistances,key=lambda x:x["lower_bound"],default=None)
        tactical=_zone(nearest_support["lower_bound"],nearest_support["upper_bound"],"TACTICAL",[("structure","Nearest confirmed support")]) if nearest_support else None
        swing_center=min(ma200w,ma200);swing=_zone(swing_center*.92,swing_center*1.04,"SWING",[("moving_average","200D/200W macro axis"),("structure","HTF reaction band")])
        macro_fib=min(fib,key=lambda x:abs(x.ratio-.618)).price;macro=_zone(min(ma200w,macro_fib)*.92,max(ma200w,macro_fib)*1.05,"MACRO",[("moving_average","200W"),("structure","Cycle 0.618 retracement"),("drawdown","Macro drawdown band")])
        deep_level=ath*.5;deep=_zone(deep_level*.9,deep_level*1.1,"CYCLE",[("drawdown","50% ATH drawdown"),("structure","Deep-cycle structural band")])
        extreme_level=ath*.25;extreme=_zone(extreme_level*.8,extreme_level*1.2,"CYCLE",[("drawdown","75%+ ATH drawdown")])
        elliott=FullHistoryElliottEngine().analyze(frame,four_hour=four_hour)
        support_break=nearest_support is not None and price<nearest_support["lower_bound"];below200w=price<ma200w
        scenarios=[
          {"name":"BULL RECOVERY","status":"WATCH" if price>ma200 else "DORMANT","price_zone":_zone(price,max(ath,price*1.15),"MACRO",[("structure","200D reclaim and ATH path")]),"activation_conditions":["Weekly structure holds above 200D","Confirmed higher high"],"invalidation_conditions":["Weekly close below major support"],"historical_analogues":[],"elliott_context":"Possible next impulse only after confirmation","drawdown_context":ladder["current_drawdown"],"support_context":nearest_support,"confidence_state":"MODERATE"},
          {"name":"BASE CONSOLIDATION","status":"ACTIVE" if not below200w and not support_break else "WATCH","price_zone":_zone(min(price,ma200),max(price,ma200),"SWING",[("structure","Current price and 200D")]),"activation_conditions":["Current structure remains range-bound"],"invalidation_conditions":["Confirmed weekly support break or breakout"],"historical_analogues":[],"elliott_context":elliott["primary"]["name"],"drawdown_context":ladder["current_drawdown"],"support_context":nearest_support,"confidence_state":"MODERATE"},
          {"name":"DEEP BEAR","status":"ACTIVE" if below200w and support_break else "WATCH" if support_break or below200w else "DORMANT","price_zone":deep,"activation_conditions":["200W lost","Weekly support break","Lower-high structure persists"],"invalidation_conditions":["200W reclaim and confirmed higher high"],"historical_analogues":["Deep historical bear-market bands"],"elliott_context":"Larger C-wave alternative","drawdown_context":-.5,"support_context":deep,"confidence_state":"LOW"},
          {"name":"EXTREME CYCLE","status":"WATCH" if ladder["current_drawdown"]<=-.65 else "DORMANT","price_zone":extreme,"activation_conditions":["Deep Bear active","Capitulation and 70%+ drawdown","Macro supports fail"],"invalidation_conditions":["Major support reclaim before activation"],"historical_analogues":["Historical 75%+ cycle drawdowns"],"elliott_context":"Extended C-wave only; conditional","drawdown_context":-.75,"support_context":extreme,"confidence_state":"LOW"}]
        macro_action="ACCUMULATE" if phase["phase"] in {"ACCUMULATION","CAPITULATION","EARLY_RECOVERY"} or (phase["phase"]=="BEAR" and price>=ma200w) else "HOLD" if phase["phase"] in {"EXPANSION","TRANSITION"} else "REDUCE"
        # Historical long-swing candidate had no validated positive edge; it cannot emit BUY before a future challenger proves one.
        long_swing="REDUCE" if support_break and below200w else "WAIT";medium="BUY" if fusion and fusion.get("new_entry") not in {"WAIT",None} else "WAIT";timing="WAIT" if fusion is None else fusion.get("timing","WAIT")
        return {"model":self.version,"status":"RESEARCH_CHALLENGER","horizon_hierarchy":["MACRO_CYCLE","MONTHLY","WEEKLY","DAILY","4H"],"actions":{"macro":macro_action,"long_swing":long_swing,"medium_swing":medium,"tactical_timing":timing,"risk":"CAUTION" if phase["phase"] in {"BEAR","TRANSITION"} else "NORMAL"},"cycle":phase,"elliott":elliott,"zones":{"tactical_buy":tactical,"swing_buy":swing,"macro_accumulation":macro,"deep_value":deep,"extreme_cycle":extreme,"major_support":nearest_support,"major_resistance":nearest_resistance,"macro_breakout":None if nearest_resistance is None else _zone(nearest_resistance["lower_bound"],nearest_resistance["upper_bound"],"MACRO",[("structure","Major confirmed resistance")])},"scenarios":scenarios,"drawdown_ladder":ladder,"indicators":{"price":price,"ath":ath,"drawdown":price/ath-1,"ma200":ma200,"ma200w":ma200w,"distance_200w":price/ma200w-1,"weekly_rsi":weekly_rsi,"monthly_rsi":monthly_rsi,"rsi_365d":float(rsi(close,365).iloc[-1]),"weekly_bollinger":bollinger(weekly).bandwidth.iloc[-1],"monthly_bollinger":bollinger(monthly).bandwidth.iloc[-1]},"waiting_for":["Weekly structure confirmation","200W hold or reclaim","Higher-low and higher-high sequence"],"why":[f"Macro phase: {phase['phase']}",f"ATH drawdown: {price/ath-1:.1%}",f"Distance to 200W: {price/ma200w-1:.1%}",f"Weekly RSI: {weekly_rsi:.1f}"],"control_3_reference":control,"specialist_5_reference":specialist,"fusion_6_reference":fusion,"production_impact":"NONE","execution":"DISABLED"}
