from __future__ import annotations

import hashlib
import json


def _inside(price,zone):return zone.get("status")=="AVAILABLE" and zone["low"]<=price<=zone["high"]
def detect_events(current,previous):
    if previous is None:return []
    c=current["decision"];p=previous["decision"];cp=current["precision"];pp=previous["precision"];events=[]
    if c["long_term_decision"]!=p["long_term_decision"]:events.append("DECISION_CHANGE")
    if cp["timing"]["state"]!=pp["timing"]["state"]:events.append("TIMING_CHANGE")
    if c["risk_action"]!=p["risk_action"]:events.append("RISK_CHANGE")
    if cp["regime"]["current"]!=pp["regime"]["current"]:events.append("REGIME_CHANGE")
    if cp["risk"]["capitulation"]!=pp["risk"]["capitulation"]:events.append("CAPITULATION")
    if cp["data_health"]["critical_healthy"] is False and pp["data_health"]["critical_healthy"] is True:events.append("DATA_WARNING")
    price=c["zones"]["current_price"];old_price=p["zones"]["current_price"]
    for name in ("buy_zone_1","buy_zone_2"):
        if _inside(price,c["zones"][name]) and not _inside(old_price,p["zones"][name]):events.append(name.upper()+"_REACHED")
    level=c["zones"]["invalidation"].get("below")
    old_level=p["zones"]["invalidation"].get("below")
    if level is not None and price<level and (old_level is None or old_price>=old_level):events.append("INVALIDATION")
    if "master" in current and "master" in previous:
        cm=current["master"];pm=previous["master"]
        if cm["decision"]["production_signal"]!=pm["decision"]["production_signal"] and cm["decision"]["production_signal"]!="NO_PRODUCTION_SIGNAL":events.append("MASTER_PRODUCTION_SIGNAL")
        if cm["state"]["buy_candidate"]!=pm["state"]["buy_candidate"] or cm["state"]["sell_candidate"]!=pm["state"]["sell_candidate"]:events.append("MASTER_CANDIDATE_CHANGE")
        if cm["state"]["distribution"]=="DISTRIBUTION_CONFIRMED" and pm["state"]["distribution"]!="DISTRIBUTION_CONFIRMED":events.append("DISTRIBUTION_CONFIRMED")
        support=cm["state"].get("nearest_support");old_support=pm["state"].get("nearest_support")
        if support and price<support["lower_bound"] and (not old_support or old_price>=old_support["lower_bound"]):events.append("MAJOR_SUPPORT_BREAKDOWN")
        resistance=cm["state"].get("nearest_resistance");old_resistance=pm["state"].get("nearest_resistance")
        if resistance and price>resistance["upper_bound"] and (not old_resistance or old_price<=old_resistance["upper_bound"]):events.append("MAJOR_RESISTANCE_BREAKOUT")
    return events


def event_id(event,state):
    payload=(event,str(state["precision"]["timestamp"]),state["decision"]["long_term_decision"],state["precision"]["timing"]["state"],state["decision"]["risk_action"],state["precision"]["regime"]["current"])
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def event_message(event,state):
    d=state["decision"];p=state["precision"];price=d["zones"]["current_price"]
    heading={"DECISION_CHANGE":"BITCOIN DECISION CHANGE","TIMING_CHANGE":"BITCOIN TIMING CHANGE","RISK_CHANGE":"BITCOIN RISK ALERT","REGIME_CHANGE":"BITCOIN REGIME CHANGE","CAPITULATION":"BITCOIN MARKET STRESS","DATA_WARNING":"BITCOIN DATA WARNING","INVALIDATION":"BITCOIN SETUP INVALIDATED","BUY_ZONE_1_REACHED":"BITCOIN BUY ZONE REACHED","BUY_ZONE_2_REACHED":"BITCOIN BUY ZONE REACHED","MASTER_PRODUCTION_SIGNAL":"BITCOIN MASTER PRODUCTION SIGNAL","MASTER_CANDIDATE_CHANGE":"BITCOIN MASTER CANDIDATE UPDATE","DISTRIBUTION_CONFIRMED":"BITCOIN DISTRIBUTION CONFIRMED","MAJOR_SUPPORT_BREAKDOWN":"BITCOIN MAJOR SUPPORT BREAKDOWN","MAJOR_RESISTANCE_BREAKOUT":"BITCOIN MAJOR RESISTANCE BREAKOUT"}.get(event,event)
    warning="\nThis invalidates the previous setup. It is not automatically a SELL signal." if event=="INVALIDATION" else ""
    if d["long_term_decision"]=="SELL":warning+="\nSELL requires independent downside evidence."
    master_line=""
    if "master" in state:
        md=state["master"]["decision"];master_line=f"\nMaster Production: {md['production_signal']}\nExisting Position: {md['existing_position_action']}"
    return f"₿ {heading}\n\nBTC: ${price:,.2f}\nLong-Term: {d['long_term_decision']}\nSwing: {d['swing_decision']}\nRisk: {d['risk_action']}\nTiming: {p['timing']['state']}\nRegime: {p['regime']['current']}\nConfidence: {d['confidence']}\nEvidence: {p['evidence']['label']}{master_line}\nChampion: 2.3-FROZEN\nMaster: 3.0\nExecution: DISABLED{warning}"
