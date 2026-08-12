from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
import pandas as pd
from ..research.best_entries import causal_feature_frame

VERSION="MASTER_5_0_CHALLENGER"

def _archetype(f,support):
    if f.capitulation_state=="CAPITULATION":return "DEEP_CAPITULATION"
    if support and f.drawdown<=-.30:return "HISTORICAL_SUPPORT_RETEST"
    if f.drawdown<=-.50 and f.value_score>=55:return "BEAR_MARKET_VALUE"
    if f.recovery_state in {"EARLY","CONFIRMED"}:return "RECOVERY_RETEST"
    return "CYCLE_ACCUMULATION" if f.drawdown<=-.25 else "NONE"

def _zone_lifecycle(price,zone,confirmed_close,previous_close=None):
    if not zone:return {"state":"UNAVAILABLE","preview":False,"distance_pct":None}
    low=zone.get("low",zone.get("lower_bound"));high=zone.get("high",zone.get("upper_bound"));distance=0 if low<=price<=high else (low-price)/price if price<low else (price-high)/price
    if confirmed_close<low:return {"state":"FAILED","preview":False,"distance_pct":round(distance*100,3)}
    if previous_close is not None and previous_close<low and confirmed_close>=low:return {"state":"RECLAIMED","preview":False,"distance_pct":round(distance*100,3)}
    if low<=price<=high:return {"state":"ENTERED","preview":True,"distance_pct":0.0}
    if price>high and distance<.05:return {"state":"APPROACHING","preview":True,"distance_pct":round(distance*100,3)}
    return {"state":"REJECTING" if confirmed_close>high else "DISTANT","preview":False,"distance_pct":round(distance*100,3)}

@dataclass
class Master5Challenger:
    version:str=VERSION
    def evaluate(self,state:dict,frame:pd.DataFrame,live_price:float|None=None)->dict:
        features=causal_feature_frame(frame);f=features.iloc[-1];price=float(live_price or frame.close.iloc[-1]);advanced=state["advanced"];zones=state["master"]["state"]["buy_zones"];zone=next((z for z in zones if z.get("status")=="AVAILABLE"),None);support=state["master"]["state"].get("nearest_support");resistance=state["master"]["state"].get("nearest_resistance")
        factors={"deep_drawdown":bool(f.drawdown<=-.40),"major_support":bool(support and support.get("confidence") in {"MODERATE","HIGH"}),"high_value":bool(f.value_score>=55),"below_200d":bool(f.distance_200d<0),"below_200w":bool(pd.notna(f.distance_200w) and f.distance_200w<0),"daily_rsi_weak":bool(f.rsi_daily<30),"weekly_rsi_weak":bool(pd.notna(f.rsi_weekly) and f.rsi_weekly<35),"capitulation":bool(f.capitulation_state=="CAPITULATION")}
        groups=sum(factors.values());archetype=_archetype(f,factors["major_support"]);quality=round(min(100,groups/8*80+(10 if factors["deep_drawdown"] and factors["major_support"] else 0)+(10 if factors["weekly_rsi_weak"] and factors["major_support"] else 0)),1)
        if factors["deep_drawdown"] and factors["major_support"] and groups>=6 and (factors["capitulation"] or factors["weekly_rsi_weak"]):buy_state="HISTORICAL_EXTREME"
        elif factors["deep_drawdown"] and factors["major_support"] and groups>=5:buy_state="STRONG_BUY_CANDIDATE"
        elif zone and groups>=3:buy_state="BUY_ZONE"
        elif groups>=2:buy_state="WATCH_BUY"
        else:buy_state="NO_BUY"
        close=frame.close;ma200=close.rolling(200).mean();weekly=close.resample("W-MON",label="right",closed="right").last().dropna();wrsi=features.rsi_weekly.iloc[-1];monthly_rsi=features.rsi_monthly.iloc[-1];bbpos=str(f.bollinger_weekly_position)
        risk_factors={"extended_200d":bool(pd.notna(ma200.iloc[-1]) and close.iloc[-1]/ma200.iloc[-1]>1.45),"weekly_rsi_extreme":bool(pd.notna(wrsi) and wrsi>75),"monthly_rsi_extreme":bool(pd.notna(monthly_rsi) and monthly_rsi>80),"bollinger_extension":bbpos=="ABOVE_UPPER","ath_proximity":bool(close.iloc[-1]>=close.cummax().iloc[-1]*.95),"lower_high":bool(len(weekly)>16 and weekly.iloc[-8:].max()<weekly.iloc[-16:-8].max()),"weekly_support_loss":bool(len(weekly)>20 and weekly.iloc[-1]<weekly.shift(1).rolling(12).min().iloc[-1]),"volatility_expansion":bool(close.pct_change().rolling(14).std().iloc[-1]>close.pct_change().rolling(365).std().quantile(.8))}
        rg=sum(risk_factors.values());structure=risk_factors["lower_high"] or risk_factors["weekly_support_loss"]
        distribution="HIGH_RISK_DISTRIBUTION" if rg>=5 and structure else "DISTRIBUTION_CONFIRMED" if rg>=4 and structure else "DISTRIBUTION_CANDIDATE" if rg>=3 else "WATCH" if rg>=1 else "NONE"
        sell_risk="EXTREME" if rg>=5 else "HIGH" if rg>=4 else "MODERATE" if rg>=2 else "LOW"
        action="EXIT_CANDIDATE" if distribution=="HIGH_RISK_DISTRIBUTION" else "TAKE_PARTIAL_PROFIT" if distribution=="DISTRIBUTION_CONFIRMED" else "REDUCE_RISK" if distribution=="DISTRIBUTION_CANDIDATE" else "WATCH_RISK" if distribution=="WATCH" else "HOLD"
        timing=state["master"]["state"]["timing"];entry_confirmation="CONFIRMED" if timing=="CONFIRMED" else "CONFIRMING" if timing=="CONFIRMING" else "WAIT"
        lifecycle=_zone_lifecycle(price,zone,float(frame.close.iloc[-1]),float(frame.close.iloc[-2]) if len(frame)>1 else None)
        rules={"buy":"domain hierarchy: value -> location -> stress -> timing; no universal weights","risk":"extension + distribution structure; news cannot trigger alone","elliott":"excluded from signal factors","execution":"DISABLED"};config_hash=hashlib.sha256(json.dumps(rules,sort_keys=True).encode()).hexdigest()
        return {"model":self.version,"status":"CHALLENGER_RESEARCH_SHADOW","buy":{"state":buy_state,"quality":quality,"quality_is_probability":False,"archetype":archetype,"factors":factors,"independent_groups":groups,"zone":zone,"zone_lifecycle":lifecycle},"entry_confirmation":{"state":entry_confirmation,"source":"MASTER confirmed timing"},"risk":{"sell_off_risk":sell_risk,"distribution":distribution,"existing_position_action":action,"factors":risk_factors,"independent_groups":rg,"news_only_trigger":False},"levels":{"support":support,"resistance":resistance},"config_hash":config_hash,"champion_unchanged":True,"elliott":"CONTEXT_ONLY_NOT_COUNTED","openai":"NOT_USED_FOR_SIGNALS","execution":"DISABLED"}
