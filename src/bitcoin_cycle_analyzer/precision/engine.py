from __future__ import annotations
from .value import value_engine
from .regime import regime_ensemble
from .risk import precision_risk
from .timing import timing_engine
from .similarity import sequence_analogues
from .decision import uncertainty_engine,market_taxonomy,scenarios
from .storage import PrecisionStore


def data_quality_state(data_status:dict)->dict:
    critical=data_status.get("price",{}).get("status") in {"AVAILABLE","LIVE"}; unavailable=sum(item.get("status")=="UNAVAILABLE" for item in data_status.values())
    stale=sum(item.get("status")=="STALE" for item in data_status.values()); score=max(0,100-unavailable*8-stale*15)
    return {"score":score,"state":"HIGH" if score>=80 else "MODERATE" if score>=60 else "LOW","critical_healthy":critical and stale==0,"unavailable_groups":unavailable,"stale_groups":stale}


def hysteresis(previous:str|None,candidate:str,days_in_candidate:int,min_days=3)->dict:
    if previous is None or previous==candidate:return {"state":candidate,"held":False}
    return {"state":candidate if days_in_candidate>=min_days else previous,"held":days_in_candidate<min_days}


def analyze_precision(frame,technical,cycle,modules,evidence,confluence,data_status,config,as_of=None)->dict:
    cutoff=frame.index[-1] if as_of is None else as_of; quality=data_quality_state(data_status)
    value=value_engine(frame,cycle,technical,cutoff); regime=regime_ensemble(frame,cycle,modules.get("onchain"),cutoff)
    risk=precision_risk(frame,technical,modules.get("derivatives"),cutoff); timing=timing_engine(technical,risk,quality,modules.get("derivatives"))
    analogues=sequence_analogues(frame,cutoff); dispersion=.5 if analogues["dispersion"] is None else min(1,analogues["dispersion"])
    uncertainty=uncertainty_engine(regime,confluence,evidence,quality,dispersion); taxonomy=market_taxonomy(value,timing,risk,regime,evidence,confluence)
    explanation={"why_value":sorted(value["inputs"],key=lambda key:abs(value["inputs"][key]),reverse=True)[:3],
                 "why_timing":timing["missing_conditions"][:3],"why_risk":["ath_drawdown","volatility_percentile","historical_analogue_tail"],
                 "why_evidence":[key for key,value_ in evidence.get("components",{}).items() if value_<10][:3]}
    return {"engine_version":"2.3","timestamp":cutoff,"value":value,"cycle":cycle,"regime":regime,"timing":timing,"risk":risk,
            "evidence":evidence,"confluence":confluence,"data_health":quality,"analogues":analogues,"uncertainty":uncertainty,
            **taxonomy,"scenarios":scenarios(value,regime,timing,risk),"explanation":explanation,"execution":"DISABLED",
            "analysis_mode":"CLOSED_CANDLE","config_hash":PrecisionStore.config_hash(config)}
