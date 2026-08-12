from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from ..analyzer import analyze as analyze_technical
from .cycle_engine import analyze_cycle
from .market_state import build_market_state
from ..seasonality.statistics import monthly_statistics
from ..seasonality.event_windows import event_window_statistics
from ..onchain import UnavailableOnChainProvider, analyze_onchain
from ..derivatives import analyze_derivatives
from ..flows.etf import analyze_etf_flows
from ..macro import analyze_macro
from ..scoring import evidence_score, evidence_score_v22, confluence_score
from ..risk import drawdown_risk
from ..entry_timing import entry_timing_state
from ..explainability import explain_state
from ..precision import analyze_precision
from ..decision import build_decision
from ..advanced import HistoricalZoneEngine,DrawdownCycleEngine,multi_timeframe_indicators
from ..rare_signals import RareSignalEngine
from ..master import BitcoinMasterEngine
from ..master.historical_entry_quality import evaluate_historical_entry_quality
from ..elliott_wave import analyze_elliott_intelligence
from ..cycles import analyze_cycle_history
from ..master5 import Master5Challenger
from ..fusion6 import BitcoinFusionEngine
from ..macro7 import MacroSwingEngine


def _seasonality(frame: pd.DataFrame, as_of) -> dict:
    monthly = monthly_statistics(frame, as_of=as_of)
    month = str(pd.Timestamp(as_of).month)
    current = monthly.get(month, {})
    median = current.get("median_return")
    win = current.get("win_rate")
    score = None if median is None or win is None else round(max(0, min(100, 50 + median * 100 + (win - .5) * 40)), 2)
    events = {name: event_window_statistics(frame, name, as_of=as_of) for name in ("thanksgiving", "black_friday", "christmas", "new_year")}
    return {"status": "AVAILABLE", "score": score, "current_month": current, "events": events, "provider": "derived from canonical BTC/USD", "last_update": as_of}


def analyze_intelligence(frame: pd.DataFrame, config: dict, as_of=None, feeds: dict | None = None, quality_score: float = 1.0, oos_quality: float = .5) -> dict:
    feeds = feeds or {}
    cutoff = frame.index[-1] if as_of is None else pd.Timestamp(as_of)
    if getattr(frame.index,"tz",None) is not None and cutoff.tzinfo is None:
        cutoff=cutoff.tz_localize(frame.index.tz)
    technical = analyze_technical(frame, config, as_of=cutoff)
    cycle = analyze_cycle(frame, as_of=cutoff)
    modules = {
        "onchain": analyze_onchain(feeds.get("onchain_provider", UnavailableOnChainProvider()), cutoff),
        "etf": analyze_etf_flows(feeds.get("etf"), cutoff),
        "derivatives": analyze_derivatives(cutoff, funding=feeds.get("funding"), open_interest=feeds.get("open_interest"), basis=feeds.get("basis"), liquidations=feeds.get("liquidations"), options=feeds.get("options")),
        "macro": analyze_macro(feeds.get("macro"), cutoff),
        "seasonality": _seasonality(frame, cutoff),
        "news": feeds.get("news_summary", {"status": "UNAVAILABLE", "reason":"NO_REAL_MEANPULSE_EVENTS", "risk": None, "score": None}),
    }
    available_scores = [module["score"] for module in modules.values() if isinstance(module, dict) and module.get("score") is not None]
    technical_direction = technical["score"].total / 100
    agreement_values = [technical_direction] + [score / 100 for score in available_scores]
    agreement = 1 - (max(agreement_values) - min(agreement_values)) if len(agreement_values) > 1 else .5
    available_modules = sum(module.get("status") == "AVAILABLE" for module in modules.values())
    evidence = evidence_score(technical["forward_summary_365d"].get("count", 0), quality_score, agreement, oos_quality, available_modules / len(modules))
    factors = [
        {"name": "technical_value", "group": "price_technical", "strength": technical_direction * 2 - 1},
        {"name": "cycle", "group": "cycle", "strength": (cycle.get("confidence", 50) / 50 - 1) if cycle.get("confidence") is not None else 0},
        {"name": "seasonality", "group": "calendar", "strength": (modules["seasonality"]["score"] / 50 - 1) if modules["seasonality"]["score"] is not None else 0},
    ]
    for name in ("onchain", "etf", "derivatives", "macro"):
        factors.append({"name": name, "group": name, "status": modules[name]["status"], "strength": 0 if modules[name].get("score") is None else modules[name]["score"] / 50 - 1})
    factors.append({"name":"news","group":"news","status":modules["news"].get("status","UNAVAILABLE"),
                    "strength":0 if modules["news"].get("score") is None else modules["news"]["score"]/50-1})
    state = build_market_state(technical, cycle, modules, evidence)
    state["confluence"] = confluence_score(factors)
    independent=state["confluence"].get("independent_groups",0)
    evidence22=evidence_score_v22(independent,quality_score,available_modules/len(modules),
                                  technical["forward_summary_365d"].get("count",0),oos_quality,.5,.8,.5)
    state["evidence_2_2"]=evidence22
    state["dimensions"]["evidence"]=evidence22["score"]
    state["group_confidence"]={factor["name"]:{"status":factor.get("status","AVAILABLE"),
        "score":round((factor.get("strength",0)+1)*50,1) if factor.get("status","AVAILABLE")=="AVAILABLE" else None,
        "confidence":100 if factor["name"] in {"technical_value","cycle"} else 40 if factor["name"]=="derivatives" else 20,
        "data_quality":"HIGH" if factor["name"] in {"technical_value","cycle"} else "MIXED",
        "coverage":modules.get(factor["name"],{}).get("coverage"),
        "oos_value":"RISK_ONLY" if factor["name"]=="derivatives" else "RESEARCH"} for factor in factors}
    state["drawdown_risk"] = drawdown_risk(technical, modules["derivatives"], modules["macro"], modules["onchain"])
    rsi = technical.get("indicators", {}).get("rsi")
    state["entry_timing_detail"] = entry_timing_state(technical.get("structure", {}).get("trend", "unknown"), technical["states"]["confirmation"], rsi, modules["derivatives"])
    state["entry_timing"] = state["entry_timing_detail"]["state"]
    state["data_status"] = {name: {"status": module.get("status", "UNAVAILABLE"), "provider": module.get("provider"), "last_update": module.get("last_update")} for name, module in modules.items()}
    state["data_status"]["price"] = {"status": "AVAILABLE", "provider": feeds.get("price_provider", "canonical BTC/USD"), "last_update": cutoff, "data_delay": str(pd.Timestamp.now(tz="UTC") - pd.Timestamp(cutoff))}
    state["explainability"] = explain_state(state)
    state["precision"] = analyze_precision(frame,technical,cycle,modules,evidence22,state["confluence"],state["data_status"],config,cutoff)
    state["decision"] = build_decision(state,technical)
    state["advanced"]={"historical_zones":HistoricalZoneEngine().analyze(frame,cutoff),"drawdown":DrawdownCycleEngine().analyze(frame,cutoff),"momentum":multi_timeframe_indicators(frame,cutoff,feeds.get("four_hour"))}
    state["rare_signal"]=RareSignalEngine().evaluate(state,technical,state["advanced"])
    state["historical_entry_quality"]=evaluate_historical_entry_quality(frame,state,technical,feeds.get("project_root"))
    state["elliott_cycle"]={"elliott":analyze_elliott_intelligence(frame,cutoff,feeds.get("price_provider","BITSTAMP historical dataset")),
                            "cycle_history":analyze_cycle_history(frame,cutoff)}
    state["live_market"]=feeds.get("live_market",{"status":"UNAVAILABLE","reason":"NO_LIVE_PROVIDER","provenance":{"historical_provider":"BITSTAMP","execution":"DISABLED"}})
    state["precision"]["live_timing_gate"]=state["live_market"].get("timing_confirmation","BLOCKED")
    state["master"]=BitcoinMasterEngine().analyze(state,technical)
    live_tick=state["live_market"].get("tick",{});live_price=live_tick.get("mid") if live_tick.get("freshness") in {"LIVE","DELAYED"} else None
    state["master5_challenger"]=Master5Challenger().evaluate(state,frame.loc[:cutoff],live_price)
    state["fusion6"]=BitcoinFusionEngine().evaluate(state,feeds.get("fusion_discovery"))
    state["macro7"]=MacroSwingEngine().analyze(frame.loc[:cutoff],state["master"],state["master5_challenger"],state["fusion6"],feeds.get("four_hour"))
    return state


def public_payload(state: dict) -> dict:
    dimensions = state["dimensions"]
    return {"service": "bitcoin-cycle", "timestamp": state["timestamp"], "symbol": "BTCUSD", "cycle_state": state["cycle"]["primary_regime"].lower(), "long_term_value": dimensions["long_term_value"], "timing": dimensions["technical_timing"], "risk": dimensions["risk"], "evidence": dimensions["evidence"], "entry_timing": state["entry_timing"]}
