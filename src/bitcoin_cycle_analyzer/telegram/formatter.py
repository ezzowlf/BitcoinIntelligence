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

def _range(zone):
    if not zone:return "UNAVAILABLE"
    low=zone.get("low",zone.get("lower_bound"));high=zone.get("high",zone.get("upper_bound"));return f"{money(low)} - {money(high)} ({zone.get('confidence','UNKNOWN')})"

def _history_block(state,detail=False):
    h=state["historical_entry_quality"];mae=h.get("mae_context",{});closest=h.get("closest_historical_entries",[])
    analogue="UNAVAILABLE" if not closest else f"{closest[0]['date'][:10]} {closest[0]['similarity']}% ({closest[0]['archetype']})"
    matched=", ".join(h.get("matched_factors",[])) or "none";missing=", ".join(h.get("missing_factors",[])) or "none";unavailable=", ".join(h.get("contradicting_factors",[])) or "none"
    base=f"HISTORICAL ENTRY QUALITY\n{h['state']} ({h.get('score')} / 100; not probability)\nArchetype: {h['entry_archetype']}\nMatched: {matched}\nMissing: {missing}\nUnavailable: {unavailable}\nClosest: {analogue}\nHistorical MAE median/worst: {mae.get('median')} / {mae.get('worst')}"
    if detail and closest:base+="\n\nHISTORICAL OUTCOMES - NOT FORECASTS\n"+"\n".join(f"{x['date'][:10]} | sim {x['similarity']}% | 365D {x['historical_return_365d']:.1%} | MAE {x['historical_MAE_365d']:.1%}" for x in closest)+f"\n\nFailed-buy reference n: {h['control_comparison']['failed_buy_reference_n']}"
    return base

def master_message(state):
    s=state["master"]["state"];d=state["master"]["decision"]
    why="\n".join(f"• {x}" for x in (d["positive_drivers"]+d["negative_drivers"])[:5]);waiting="\n".join(f"• {x}" for x in d["waiting_for"])
    return f"₿ BITCOIN MASTER\n\nBTC\n{money(s['btc_price'])}\n\nLONG TERM\n{d['long_term_action']}\n\nNEW ENTRY\n{d['new_entry_action']}\n\nEXISTING POSITION\n{d['existing_position_action']}\n\nRISK\n{d['risk_action']}\n\nPRODUCTION\n{d['production_signal']}\n\nBUY CANDIDATE\n{s['buy_completion']}% (completion, not probability)\n\nSELL CANDIDATE\n{s['sell_completion']}% (completion, not probability)\n\nMAJOR SUPPORT\n{_range(s['nearest_support'])}\n\nMAJOR RESISTANCE\n{_range(s['nearest_resistance'])}\n\nDRAWDOWN\n{s['drawdown']:.1%}\n\nWEEKLY RSI\n{s['weekly_rsi']}\n\nREGIME\n{s['regime']} ({s['regime_stability']})\n\nWHY?\n{why}\n\nWAITING FOR\n{waiting}\n\nMaster: 3.0\nPrimary: 2.5\nControl: 2.3-FROZEN\nExecution: DISABLED"

def command_message(command,state,health=None):
    p=state["precision"];d=state["decision"]
    if command in {"/btc"}:return compact_message(state)
    if command=="/decision":return decision_message(state)
    if command=="/value":return f"VALUE {p['value']['score']} {p['value']['state']}\nPercentile {p['value']['historical_percentile']}\nATH drawdown {p['value']['inputs']['ath_drawdown']:.2%}\nEpisodes {p['analogues']['independent_episodes']}"
    if command=="/timing":return f"TIMING {p['timing']['state']} ({p['timing']['score']})\nMissing: {', '.join(p['timing']['missing_conditions'])}\nModel status: {p['timing'].get('status','RESEARCH')}"
    if command=="/risk":return f"RISK 7D {p['risk']['horizons']['7d']} | 30D {p['risk']['horizons']['30d']} | 90D {p['risk']['horizons']['90d']}\nTail {p['risk']['tail_state']}\nVolatility percentile {p['risk']['volatility_percentile']}\nModel status: RESEARCH"
    if command=="/cycle":
        ec=state.get("elliott_cycle",{});ell=ec.get("elliott",{});ch=ec.get("cycle_history",{}).get("current",{})
        primary=ell.get("primary",{})
        return f"BITCOIN CYCLE · RESEARCH\nREGIME {p['regime']['current']}\nELLIOTT {primary.get('name','UNAVAILABLE')}\nRelative Support {primary.get('relative_support','UNAVAILABLE')} (not probability)\nDrawdown {ch.get('drawdown','UNAVAILABLE')}\nDays since ATH {ch.get('days_since_ath','UNAVAILABLE')}\nExecution DISABLED"
    if command=="/elliott":
        e=state.get("elliott_cycle",{}).get("elliott",{});primary=e.get("primary",{});alt=(e.get("alternatives") or [{}])[0]
        return f"ELLIOTT WAVE · RESEARCH_ONLY\nPrimary: {primary.get('name','UNAVAILABLE')}\nAlternative: {alt.get('name','UNAVAILABLE')}\nDegree: {primary.get('degree','UNAVAILABLE')}\nRelative Support: {primary.get('relative_support','UNAVAILABLE')} (not probability)\nInvalidation: {primary.get('invalidation_level','UNAVAILABLE')}\nConfirmation: {primary.get('confirmation_level','UNAVAILABLE')}\nExecution: DISABLED"
    if command=="/analyse":
        return master_message(state)+"\n\nDeterministische MASTER-Erklärung. OpenAI Mini wird ausschließlich in einem konfigurierten Bot-Runtime-Adapter aufgerufen; kein Modell ist hier vorgetäuscht.\nExecution: DISABLED"
    if command=="/shadow":
        c=state.get("master5_challenger",{});b=c.get("buy",{});r=c.get("risk",{});zone=b.get("zone") or {}
        return f"BITCOIN MASTER 5.0 SHADOW\nBTC {money(state['master']['state']['btc_price'])}\nBUY OPPORTUNITY {b.get('state','UNAVAILABLE')}\nBUY QUALITY {b.get('quality','UNAVAILABLE')} / 100 (not probability)\nARCHETYPE {b.get('archetype','UNAVAILABLE')}\nENTRY {c.get('entry_confirmation',{}).get('state','UNAVAILABLE')}\nSELL-OFF RISK {r.get('sell_off_risk','UNAVAILABLE')}\nDISTRIBUTION {r.get('distribution','UNAVAILABLE')}\nEXISTING POSITION {r.get('existing_position_action','UNAVAILABLE')}\nBUY ZONE {_range(zone)}\nStatus SHADOW / RESEARCH\nExecution DISABLED"
    if command=="/fusion":
        f=state.get("fusion6",{});m3=state["master"]["decision"];m5=state.get("master5_challenger",{});patterns=f.get("active_historical_patterns",[])
        s=state["master"]["state"];zone=m5.get("buy",{}).get("zone") or {};support=s.get("nearest_support");resistance=s.get("nearest_resistance")
        return f"₿ FUSION 6\n\nBTC\n{money(s['btc_price'])}\n\nLONG TERM\n{f.get('long_term','UNAVAILABLE')}\n\nNEW ENTRY\n{f.get('new_entry','UNAVAILABLE')}\n\nRARE BUY\n{f.get('rare_buy','UNAVAILABLE')}\n\nRISK\n{f.get('risk','UNAVAILABLE')}\n\nREGIME\n{f.get('regime','UNAVAILABLE')}\n\nTIMING\n{f.get('timing','UNAVAILABLE')}\n\nCONTROL 3\n{m3['long_term_action']}\n\nSPECIALIST 5\n{m5.get('buy',{}).get('state','UNAVAILABLE')}\n\nACTIVE PATTERNS\n{len(patterns)}\n\nNEXT BUY ZONE\n{_range(zone)}\n\nSUPPORT\n{_range(support)}\n\nRESISTANCE\n{_range(resistance)}\n\nExecution: DISABLED"
    if command=="/patterns":
        patterns=state.get("fusion6",{}).get("active_historical_patterns",[])
        return "FUSION 6 ACTIVE RESEARCH PATTERNS\n"+("No active promoted research pattern." if not patterns else "\n".join(f"{p['pattern_id']} | {' + '.join(p['factors'])} | {p['status']} | n={p['sample_size']}" for p in patterns))+"\nNot probability. Execution DISABLED"
    if command=="/events":
        news=state.get("modules",{}).get("news",{});season=state.get("modules",{}).get("seasonality",{})
        return f"FUSION 6 EVENT CONTEXT\nNEWS {news.get('status','UNAVAILABLE')}\nCALENDAR {season.get('status','UNAVAILABLE')}\nHistorical sourced event DB: INSUFFICIENT_DATA\nNo event-only signal. Execution DISABLED"
    if command=="/zones":return str(d["zones"])
    if command=="/why":return f"POSITIVE {d['why']['positive']}\nNEGATIVE {d['why']['negative']}\nUNCERTAIN {d['why']['uncertain']}\nMISSING {p['confluence']['unavailable']}"
    if command=="/health":return str(health or {"data_health":p["data_health"],"frozen_model":"2.3-FROZEN","execution":"DISABLED"})
    if command=="/candidates":
        c=state["rare_signal"]["level_b"]
        return f"BITCOIN RARE SIGNAL CANDIDATES\nBuy: {c['buy']} ({c['buy_completion']}%)\nSell: {c['sell']} ({c['sell_completion']}%)\nMissing buy: {', '.join(c['missing_buy'])}\nMissing sell: {', '.join(c['missing_sell'])}\nStatus: CHALLENGER / RESEARCH\nExecution: DISABLED"
    if command=="/signals":
        rare=state["rare_signal"];signal=rare["level_a"]
        return f"BITCOIN PRODUCTION SIGNAL\nCurrent: {signal['signal']}\nStrength: {signal['strength'] or 'N/A'}\nRare Buy: {rare['buy_state']}\nRare Sell: {rare['sell']['state']}\nHistorical: RESEARCH_ONLY\nForward BUY episodes: 0\nForward SELL episodes: 0\nModel: RARE_SIGNAL_CHALLENGER_1\nExecution: DISABLED"
    if command=="/master":return master_message(state)+"\n\n"+_history_block(state)
    if command in {"/history","/entryhistory"}:return _history_block(state,detail=True)+"\nResearch context only. Execution: DISABLED"
    if command=="/buy":
        s=state["master"]["state"]
        return f"BITCOIN BUY VIEW\nRare Buy: {s['rare_buy']}\nCandidate: {s['buy_candidate']}\nCompletion: {s['buy_completion']}% (not probability)\nBuy Zone 1: {_range(s['buy_zones'][0])}\nBuy Zone 2: {_range(s['buy_zones'][1])}\nSupport: {_range(s['nearest_support'])}\nTiming: {s['timing']}\nValue: {s['value_state']} {s['value_score']}\nDrawdown: {s['drawdown']:.1%}\nWeekly RSI: {s['weekly_rsi']}\n\n{_history_block(state)}\nExecution: DISABLED"
    if command=="/sell":
        s=state["master"]["state"]
        return f"BITCOIN SELL VIEW\nRare Sell: {s['rare_sell']}\nCandidate: {s['sell_candidate']}\nCompletion: {s['sell_completion']}% (not probability)\nDistribution: {s['distribution']}\nResistance: {_range(s['nearest_resistance'])}\nRisk: {s['risk']}\nWeekly RSI: {s['weekly_rsi']}\nMissing: {', '.join(state['rare_signal']['level_b']['missing_sell'])}\nRejected historical SELL proxy cannot trigger production.\nExecution: DISABLED"
    if command=="/levels":
        s=state["master"]["state"];invalid=state["decision"]["zones"]["invalidation"]
        return f"BITCOIN LEVELS\nBuy Zone 1: {_range(s['buy_zones'][0])}\nBuy Zone 2: {_range(s['buy_zones'][1])}\nMajor Support: {_range(s['nearest_support'])}\nMajor Resistance: {_range(s['nearest_resistance'])}\nDistribution Zone: {_range(s['sell_zones'][0]) if s['sell_zones'] else 'UNAVAILABLE'}\nBreakdown: below {money(invalid['below']) if invalid.get('below') else 'UNAVAILABLE'}\nExecution: DISABLED"
    if command=="/drawdown":
        s=state["master"]["state"];draw=state["advanced"]["drawdown"]
        return f"BITCOIN DRAWDOWN\nCurrent: {s['drawdown']:.1%}\nHistorical percentile: {s['drawdown_percentile']}\nMaximum: {draw['maximum_historical_drawdown']:.1%}\nDays under water: {draw['days_below_previous_ath']}\nRecovery: {draw['recovery_from_major_low']:.1%}\nState: {s['recovery_state']}\nExecution: DISABLED"
    return "Supported: /master /shadow /fusion /patterns /events /analyse /elliott /history /buy /sell /levels /drawdown /btc /decision /value /timing /risk /cycle /zones /why /health /candidates /signals"
