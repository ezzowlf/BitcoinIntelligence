from __future__ import annotations
from dataclasses import dataclass
import hashlib,json
import pandas as pd


def _weekly(frame):return frame.resample("W-MON",label="right",closed="right").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()


@dataclass
class SellOpportunityEngine:
    def evaluate(self,state,technical,advanced):
        frame=technical["data"];weekly=_weekly(frame);close=weekly.close;momentum=close.pct_change(4);ath=close.cummax();near_ath=float(close.iloc[-1]/ath.iloc[-1])>.85
        lower_high=len(weekly)>16 and weekly.high.iloc[-8:].max()<weekly.high.iloc[-16:-8].max();weekly_break=len(weekly)>20 and close.iloc[-1]<weekly.low.shift(1).rolling(12).min().iloc[-1];momentum_break=len(momentum)>3 and momentum.iloc[-1]<0 and momentum.iloc[-1]<momentum.iloc[-2]
        mtf=advanced["momentum"];overbought=(mtf["weekly"]["rsi"] or 0)>=70 or (mtf["monthly"]["rsi"] or 0)>=75;bear_div=mtf["divergence"]["weekly_bearish"] or mtf["divergence"]["daily_bearish"]
        derivatives=state["modules"]["derivatives"];derivative_state=derivatives.get("risk_state") or derivatives.get("state");derivative_state=derivative_state if isinstance(derivative_state,str) else None;leverage=derivative_state in {"ELEVATED","EXTREME","OVERHEATED"}
        onchain_state=state["modules"]["onchain"].get("regime");onchain_state=onchain_state if isinstance(onchain_state,str) else None;onchain=onchain_state in {"DISTRIBUTION","HEAVY_DISTRIBUTION"}
        etf_state=state["modules"]["etf"].get("state");etf_state=etf_state if isinstance(etf_state,str) else None;etf=etf_state in {"OUTFLOW","STRONG_OUTFLOW"}
        factors={"valuation":bool(near_ath and overbought),"distribution":bool(bear_div or lower_high or onchain),"structure":bool(weekly_break),"momentum":bool(momentum_break),"derivatives":bool(leverage),"etf":bool(etf)}
        groups=sum(bool(v) for v in factors.values());distribution_score=sum([bear_div,lower_high,onchain,etf,near_ath])*20
        distribution="DISTRIBUTION_CONFIRMED" if distribution_score>=60 and weekly_break else "DISTRIBUTION" if distribution_score>=60 else "DISTRIBUTION_CANDIDATE" if distribution_score>=20 else "NONE"
        evidence=state["precision"]["evidence"]["score"];quality=state["precision"]["data_health"]["critical_healthy"]
        sell="STRONG_SELL" if quality and evidence>=70 and groups>=4 and weekly_break and distribution=="DISTRIBUTION_CONFIRMED" else "SELL" if quality and evidence>=60 and groups>=3 and weekly_break and distribution in {"DISTRIBUTION","DISTRIBUTION_CONFIRMED"} else "REDUCE" if quality and groups>=3 else "WATCH_DISTRIBUTION" if groups>=1 else "NO_SELL"
        return {"state":sell,"distribution":distribution,"distribution_score":distribution_score,"independent_groups":groups,"factors":factors,"failed_breakout":near_ath and lower_high and momentum_break,"blow_off_top":{"state":"RESEARCH","candidate":near_ath and overbought and float(close.pct_change(12).iloc[-1])>.5},"reason_codes":[name for name,value in factors.items() if value],"confirmation":"CONFIRMED" if weekly_break and distribution in {"DISTRIBUTION","DISTRIBUTION_CONFIRMED"} else "NOT_YET"}


@dataclass
class RareSignalEngine:
    version:str="RARE_SIGNAL_CHALLENGER_1"
    def evaluate(self,state,technical,advanced):
        p=state["precision"];decision=state["decision"];sell=SellOpportunityEngine().evaluate(state,technical,advanced);zones=advanced["historical_zones"];price=technical["price"]
        support=next((z for z in zones if z["upper_bound"]<=price and "SUPPORT" in z["zone_type"]),None);resistance=next((z for z in zones if z["lower_bound"]>=price and "RESISTANCE" in z["zone_type"]),None)
        buy_factors={"value":p["value"]["state"] in {"HIGH_VALUE","EXTREME_VALUE"},"drawdown":advanced["drawdown"]["current_drawdown"]<=-.4,"major_support":support is not None and support["confidence"] in {"MODERATE","HIGH"},"momentum_extreme":(advanced["momentum"]["weekly"]["rsi"] or 100)<35,"capitulation":p["risk"]["capitulation"] in {"CAPITULATION_CANDIDATE","CAPITULATION","POST_CAPITULATION"},"timing":p["timing"]["state"] in {"CONFIRMING","CONFIRMED"}}
        buy_groups=sum(buy_factors.values());quality=p["data_health"]["critical_healthy"] and p["evidence"]["score"]>=50
        buy_candidate="BUY_CANDIDATE" if quality and buy_groups>=3 else "ACCUMULATION_CANDIDATE" if quality and buy_groups>=2 else "NONE"
        buy="STRONG_BUY" if quality and buy_groups>=5 and buy_factors["timing"] and buy_factors["capitulation"] else "BUY" if quality and buy_groups>=4 and buy_factors["timing"] else "ACCUMULATE" if quality and buy_groups>=3 and buy_factors["value"] else "NO_BUY"
        production="NO_PRODUCTION_SIGNAL";direction=None
        if sell["state"] in {"REDUCE","SELL","STRONG_SELL"}:production=sell["state"];direction="SELL"
        elif buy in {"BUY","STRONG_BUY"}:production=buy;direction="BUY"
        strength="EXCEPTIONAL" if production in {"STRONG_BUY","STRONG_SELL"} else "VERY_HIGH" if production in {"BUY","SELL"} else "HIGH" if production=="REDUCE" else None
        candidate={"buy":buy_candidate,"sell":sell["state"] if sell["state"]=="WATCH_DISTRIBUTION" else "NONE","buy_completion":round(buy_groups/6*100,1),"sell_completion":round(sell["independent_groups"]/6*100,1),"missing_buy":[k for k,v in buy_factors.items() if not v],"missing_sell":[k for k,v in sell["factors"].items() if not v]}
        definition={"version":self.version,"production_requires":"data quality, evidence and independent confluence","strong_sell":"distribution plus weekly breakdown and at least four groups","strong_buy":"value, drawdown/support, capitulation and confirmation"};config_hash=hashlib.sha256(json.dumps(definition,sort_keys=True).encode()).hexdigest()
        return {"level_a":{"signal":production,"direction":direction,"strength":strength},"level_b":candidate,"level_c":{"buy_factors":buy_factors,"sell_factors":sell["factors"]},"buy_state":buy,"sell":sell,"historical_support":support,"historical_resistance":resistance,"model":self.version,"config_hash":config_hash,"status":"CHALLENGER","history_label":"RESEARCH_ONLY","forward_start":"2026-08-10T00:00:00Z","execution":"DISABLED"}
