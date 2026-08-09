from __future__ import annotations

ICONS={"STRONG_BUY":"🟢","BUY":"🟢","ACCUMULATE":"🟢","WAIT":"🟡","NO_EDGE":"⚪","DO_NOT_BUY":"🟠","REDUCE":"🟠","SELL":"🔴","HIGH_RISK":"🔴","DATA_UNRELIABLE":"⚫","CAUTION":"🟠","NORMAL":"🟢","REDUCE_RISK":"🔴"}
def icon(state):return ICONS.get(state,"⚪")
def money(value):return f"${value:,.2f}"

def decision_message(state):
    d=state["decision"];p=state["precision"];z=d["zones"]["buy_zone_1"]
    waiting="\n".join(f"• {item}" for item in d["waiting_for"]) or "• no mandatory condition reported"
    why="\n".join(f"• {item}" for item in d["reason_codes"][:5])
    zone="UNAVAILABLE" if z["status"]!="AVAILABLE" else f"{money(z['low'])} – {money(z['high'])} ({z['confidence']})"
    return f"₿ BITCOIN DECISION\n\nLONG TERM\n{icon(d['long_term_decision'])} {d['long_term_decision']}\n\nSWING\n{icon(d['swing_decision'])} {d['swing_decision']}\n\nRISK\n{icon(d['risk_action'])} {d['risk_action']}\n\nConfidence: {d['confidence']}\n\nWHY?\n{why}\n\nWAITING FOR\n{waiting}\n\nBUY ZONE\n{zone}\n\nNext upgrade:\n{', '.join(d['next_upgrade_conditions'])}\n\nNext downgrade:\n{', '.join(d['next_downgrade_conditions'])}\n\nEvidence: {p['evidence']['label']}\nModel: 2.3-FROZEN\nExecution: DISABLED"

def compact_message(state):
    d=state["decision"];p=state["precision"]
    return f"₿ BITCOIN INTELLIGENCE\nBTC {money(d['zones']['current_price'])}\nMARKET STATE {p['market_state']}\nLONG TERM {d['long_term_decision']}\nSWING {d['swing_decision']}\nRISK {d['risk_action']}\nVALUE {p['value']['score']} {p['value']['state']}\nREGIME {p['regime']['current']} ({p['regime']['stability']})\nTIMING {p['timing']['state']}\nEVIDENCE {p['evidence']['label']}\nLast confirmed: {p['timestamp']}"

def command_message(command,state,health=None):
    p=state["precision"];d=state["decision"]
    if command in {"/btc"}:return compact_message(state)
    if command=="/decision":return decision_message(state)
    if command=="/value":return f"VALUE {p['value']['score']} {p['value']['state']}\nPercentile {p['value']['historical_percentile']}\nATH drawdown {p['value']['inputs']['ath_drawdown']:.2%}\nEpisodes {p['analogues']['independent_episodes']}"
    if command=="/timing":return f"TIMING {p['timing']['state']} ({p['timing']['score']})\nMissing: {', '.join(p['timing']['missing_conditions'])}\nModel status: {p['timing'].get('status','RESEARCH')}"
    if command=="/risk":return f"RISK 7D {p['risk']['horizons']['7d']} | 30D {p['risk']['horizons']['30d']} | 90D {p['risk']['horizons']['90d']}\nTail {p['risk']['tail_state']}\nVolatility percentile {p['risk']['volatility_percentile']}\nModel status: RESEARCH"
    if command=="/cycle":return f"CYCLE {p['cycle']['primary_regime']}\nREGIME {p['regime']['current']}\nSupport {p['regime']['relative_support']}\nStability {p['regime']['stability']}\nTransition {p['regime']['transition_status']}"
    if command=="/zones":return str(d["zones"])
    if command=="/why":return f"POSITIVE {d['why']['positive']}\nNEGATIVE {d['why']['negative']}\nUNCERTAIN {d['why']['uncertain']}\nMISSING {p['confluence']['unavailable']}"
    if command=="/health":return str(health or {"data_health":p["data_health"],"frozen_model":"2.3-FROZEN","execution":"DISABLED"})
    if command=="/candidates":
        c=state["rare_signal"]["level_b"]
        return f"BITCOIN RARE SIGNAL CANDIDATES\nBuy: {c['buy']} ({c['buy_completion']}%)\nSell: {c['sell']} ({c['sell_completion']}%)\nMissing buy: {', '.join(c['missing_buy'])}\nMissing sell: {', '.join(c['missing_sell'])}\nStatus: CHALLENGER / RESEARCH\nExecution: DISABLED"
    if command=="/signals":
        rare=state["rare_signal"];signal=rare["level_a"]
        return f"BITCOIN PRODUCTION SIGNAL\nCurrent: {signal['signal']}\nStrength: {signal['strength'] or 'N/A'}\nRare Buy: {rare['buy_state']}\nRare Sell: {rare['sell']['state']}\nHistorical: RESEARCH_ONLY\nForward BUY episodes: 0\nForward SELL episodes: 0\nModel: RARE_SIGNAL_CHALLENGER_1\nExecution: DISABLED"
    return "Supported: /btc /decision /value /timing /risk /cycle /zones /why /health /candidates /signals"
