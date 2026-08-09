from __future__ import annotations


def uncertainty_engine(regime:dict,confluence:dict,evidence:dict,data_health:dict,analogue_dispersion:float=.5)->dict:
    missing=data_health.get("unavailable_groups",0); score=(1-regime.get("model_agreement",0))*.3+min(1,missing/8)*.25+analogue_dispersion*.2+(1-evidence.get("score",0)/100)*.15+(1-min(1,confluence.get("independent_groups",0)/8))*.1
    level="VERY_HIGH" if score>=.75 else "HIGH" if score>=.55 else "MODERATE" if score>=.3 else "LOW"
    return {"score":round(score*100,1),"state":level,"drivers":{"regime_disagreement":1-regime.get("model_agreement",0),"missing_groups":missing,"analogue_dispersion":analogue_dispersion}}


def market_taxonomy(value:dict,timing:dict,risk:dict,regime:dict,evidence:dict,confluence:dict)->dict:
    high_value=value["state"] in {"HIGH_VALUE","EXTREME_VALUE"}; high_risk=risk["tail_state"] in {"HIGH","EXTREME"}
    if risk["capitulation"]=="CAPITULATION": state="CAPITULATION"
    elif high_value and high_risk: state="HIGH_VALUE_HIGH_RISK"
    elif high_value and timing["state"] not in {"CONFIRMING","CONFIRMED"}: state="VALUE_WITHOUT_CONFIRMATION"
    elif regime["current"]=="RECOVERY" and timing["state"]=="CONFIRMING": state="RECOVERY_CONFIRMING"
    elif regime["current"]=="RECOVERY" and timing["state"]=="CONFIRMED": state="CONFIRMED_RECOVERY"
    elif value["state"]=="FAIR" and timing["state"] in {"WAIT","NO_SETUP"} and confluence.get("level")=="LOW": state="NO_EDGE"
    else: state="EARLY_ACCUMULATION" if high_value else "NO_EDGE"
    conclusion="ATTRACTIVE_VALUE_BUT_NO_CONFIRMED_ENTRY_EDGE" if high_value and timing["state"] not in {"CONFIRMING","CONFIRMED"} else state
    return {"market_state":state,"system_conclusion":conclusion,"no_edge":state=="NO_EDGE"}


def scenarios(value:dict,regime:dict,timing:dict,risk:dict)->dict:
    return {"bullish":{"required":["structure_reclaim","higher_low","risk_normalization"],"invalidation":"new_confirmed_lower_low","relative_support_factors":sum([value["score"]>=65,regime["candidate"] in {"RECOVERY","EARLY_BULL"}])},
            "base":{"required":["range_holds","no_risk_escalation"],"invalidation":"range_break","relative_support_factors":sum([timing["state"]=="WAIT",regime["stability"]=="LOW"])},
            "bearish":{"required":["weekly_support_loss","lower_low"],"invalidation":"confirmed_reclaim","relative_support_factors":sum([risk["tail_state"] in {"HIGH","EXTREME"},timing["state"] in {"WAIT","NO_SETUP"}])},
            "note":"Factor counts are not probabilities; no price targets are generated."}
