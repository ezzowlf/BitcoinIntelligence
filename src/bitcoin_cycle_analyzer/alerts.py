from __future__ import annotations


def build_alert(state: dict, min_value: float = 75, min_evidence: float = 50) -> dict | None:
    dimensions = state["dimensions"]
    if dimensions["long_term_value"] < min_value or dimensions["evidence"] < min_evidence:
        return None
    return {"type": "BITCOIN_CONFLUENCE_ALERT", "timestamp": state["timestamp"], "long_term_value": dimensions["long_term_value"], "evidence": dimensions["evidence"], "confluence": state["confluence"], "entry_confirmation": state["entry_timing"], "risk": dimensions["risk"], "action": "WATCH FOR CONFIRMATION", "execution": "DISABLED"}


def transition_alert(previous: dict, current: dict) -> dict | None:
    changes=[]
    if previous.get("entry_timing")=="WAIT" and current.get("entry_timing")=="CONFIRMING": changes.append("ENTRY_WAIT_TO_CONFIRMING")
    if previous.get("drawdown_risk",{}).get("label")=="HIGH" and current.get("drawdown_risk",{}).get("label")=="MEDIUM": changes.append("RISK_HIGH_TO_MEDIUM")
    if previous.get("confluence",{}).get("level")=="LOW" and current.get("confluence",{}).get("level")=="HIGH": changes.append("CONFLUENCE_LOW_TO_HIGH")
    return None if not changes else {"type":"BITCOIN_STATE_TRANSITION","changes":changes,"execution":"DISABLED"}


def precision_alert(previous:dict|None,current:dict,min_score_change=10)->dict|None:
    if previous is None:return None
    changes=[]
    for key in ("market_state",):
        if previous.get(key)!=current.get(key): changes.append(f"{key.upper()}_CHANGE")
    if previous.get("timing",{}).get("state")!=current.get("timing",{}).get("state"): changes.append("TIMING_CHANGE")
    if abs(previous.get("risk",{}).get("horizons",{}).get("30d",0)-current.get("risk",{}).get("horizons",{}).get("30d",0))>=min_score_change: changes.append("RISK_CHANGE")
    if not changes:return None
    severity="IMPORTANT" if any(item in changes for item in ("RISK_CHANGE","TIMING_CHANGE")) else "WATCH"
    return {"type":changes[0],"changes":changes,"severity":severity,"what_changed":changes,"why":current.get("explanation"),
            "what_is_missing":current.get("timing",{}).get("missing_conditions",[]),"invalidation":current.get("scenarios",{}).get("base",{}).get("invalidation"),"execution":"DISABLED"}
