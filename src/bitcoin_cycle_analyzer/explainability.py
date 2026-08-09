from __future__ import annotations


def explain_state(state: dict) -> dict:
    technical=state["technical"]["states"]; derivatives=state["modules"]["derivatives"]
    positives=[]; negatives=[]; uncertainties=[]; improve=[]; worsen=[]
    if state["dimensions"]["long_term_value"]>=60: positives.append("long_term_value")
    if state["cycle"]["primary_regime"] in {"RECOVERY","EXPANSION"}: positives.append("cycle_regime")
    if state["drawdown_risk"]["label"]=="HIGH": negatives.append("historical_drawdown_risk")
    if (derivatives.get("risk_score") or 0)>=70: negatives.append("derivatives_leverage_risk")
    for name,module in state["modules"].items():
        if module.get("status")=="UNAVAILABLE": uncertainties.append(f"{name}_unavailable")
    if state["entry_timing"]=="WAIT": improve.extend(["price_structure_reclaim","confirmation_improves_to_medium"])
    if derivatives.get("modules",{}).get("open_interest",{}).get("level")=="HIGH": improve.append("open_interest_reset")
    worsen.extend(["loss_of_weekly_support","drawdown_risk_remains_high"])
    return {"top_positive_factors":positives[:3],"top_negative_factors":negatives[:3],"main_uncertainties":uncertainties[:3],
            "what_would_improve":improve,"what_would_worsen":worsen,
            "entry_trigger":{"current":state["entry_timing"],"next":"CONFIRMING","required_conditions":improve,
                             "execution":"DISABLED"}}
