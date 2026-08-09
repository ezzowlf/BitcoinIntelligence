from __future__ import annotations


def timing_engine(technical:dict,risk:dict,data_quality:dict,derivatives:dict|None=None)->dict:
    states=technical["states"]; structure=technical.get("structure",{}).get("trend","unknown"); confirmation=states.get("confirmation","LOW")
    mandatory={"no_confirmed_lower_low":structure!="bearish","structure_reclaim":structure=="bullish",
               "h4_or_d1_confirmation":confirmation in {"MEDIUM","HIGH"},"risk_not_extreme":risk.get("tail_state")!="EXTREME",
               "critical_data_healthy":data_quality.get("critical_healthy",True)}
    points=(30 if mandatory["no_confirmed_lower_low"] else 0)+(30 if mandatory["structure_reclaim"] else 0)+(25 if mandatory["h4_or_d1_confirmation"] else 0)
    funding=(derivatives or {}).get("modules",{}).get("funding",{}).get("state"); points+=10 if funding in {"NEGATIVE","STRONGLY_NEGATIVE"} else 0
    score=max(0,min(100,points)); hard=all(mandatory.values())
    state="CONFIRMED" if hard and confirmation=="HIGH" else "CONFIRMING" if hard else "EARLY" if score>=40 and mandatory["no_confirmed_lower_low"] else "WAIT" if any(mandatory.values()) else "NO_SETUP"
    if not mandatory["critical_data_healthy"]: state="STATE_HELD_DUE_TO_DATA_QUALITY"
    return {"score":score,"state":state,"next_state":"CONFIRMING" if state in {"NO_SETUP","WAIT","EARLY"} else "CONFIRMED",
            "mandatory_conditions":mandatory,"missing_conditions":[key for key,value in mandatory.items() if not value],"execution":"DISABLED","status":"RESEARCH"}
