from __future__ import annotations
from .zones import build_zones


def _confidence(precision):
    evidence=precision["evidence"]["score"]; quality=precision["data_health"]["score"]; groups=precision["confluence"].get("independent_groups",0); agreement=precision["regime"].get("model_agreement",0)
    return "HIGH" if evidence>=75 and quality>=80 and groups>=6 and agreement>=.6 else "MODERATE" if evidence>=50 and quality>=60 and groups>=4 else "LOW"


def build_decision(state:dict,technical_raw:dict)->dict:
    p=state["precision"]; value=p["value"]; regime=p["regime"]; timing=p["timing"]; risk=p["risk"]; quality=p["data_health"]; confidence=_confidence(p)
    if not quality["critical_healthy"]:
        long_term=swing="DATA_UNRELIABLE"; risk_action="HIGH_RISK"
    else:
        exceptional=value["state"]=="EXTREME_VALUE" and regime["current"] in {"ACCUMULATION","RECOVERY"} and timing["state"] in {"CONFIRMING","CONFIRMED"} and risk["tail_state"] not in {"HIGH","EXTREME"} and p["confluence"].get("independent_groups",0)>=6
        if exceptional: long_term="STRONG_BUY"
        elif value["state"] in {"HIGH_VALUE","EXTREME_VALUE"} and timing["state"] in {"CONFIRMING","CONFIRMED"} and regime["current"]!="BEAR": long_term="BUY"
        elif value["state"] in {"HIGH_VALUE","EXTREME_VALUE"}: long_term="ACCUMULATE"
        elif value["state"] in {"EXPENSIVE","EXTREME_EXPENSIVE"} and regime["current"]=="DISTRIBUTION": long_term="REDUCE"
        else: long_term="WAIT"
        sell_evidence=value["state"]=="EXTREME_EXPENSIVE" and regime["current"]=="DISTRIBUTION" and technical_raw.get("structure",{}).get("trend")=="bearish" and p["evidence"]["score"]>=70
        if sell_evidence:swing="SELL"
        elif risk["tail_state"] in {"HIGH","EXTREME"}:swing="DO_NOT_BUY"
        elif timing["state"]=="CONFIRMED" and regime["current"]!="BEAR":swing="BUY"
        elif value["state"] in {"EXPENSIVE","EXTREME_EXPENSIVE"} and technical_raw.get("structure",{}).get("trend")=="bearish":swing="REDUCE"
        elif p.get("no_edge"):swing="NO_EDGE"
        else:swing="WAIT"
        risk_action="REDUCE_RISK" if risk["tail_state"]=="EXTREME" else "HIGH_RISK" if risk["tail_state"]=="HIGH" else "CAUTION" if p["uncertainty"]["state"] in {"HIGH","VERY_HIGH"} or regime["current"]=="BEAR" else "NORMAL"
    positives=[f"Long-term value {value['state']}",f"Value percentile {value['historical_percentile']}"]
    negatives=[f"Regime {regime['current']}",f"Timing {timing['state']}",f"Uncertainty {p['uncertainty']['state']}"]
    waiting=timing.get("missing_conditions",[])[:3]
    zones=build_zones(float(technical_raw["price"]),technical_raw)
    accumulation="STRONG_ACCUMULATION" if long_term=="STRONG_BUY" else "NORMAL_ACCUMULATION" if long_term=="BUY" else "SMALL_ACCUMULATION" if long_term=="ACCUMULATE" else "NO_BUY"
    return {"long_term_decision":long_term,"swing_decision":swing,"risk_action":risk_action,"confidence":confidence,
            "decision_type":"LONG_TERM_AND_SWING_SEPARATED","reason_codes":positives+negatives,"why":{"positive":positives,"negative":negatives,"uncertain":[f"Evidence {p['evidence']['label']}"]},
            "waiting_for":waiting,"invalidation_conditions":["weekly_support_break","confirmed_lower_low","tail_risk_escalation"],
            "next_upgrade_conditions":waiting+["regime_improvement","risk_acceptable"],"next_downgrade_conditions":["weekly_support_break","regime_deterioration","tail_risk_high"],
            "accumulation_mode":accumulation,"zones":zones,"frozen_model":"2.3-FROZEN","execution":"DISABLED"}
