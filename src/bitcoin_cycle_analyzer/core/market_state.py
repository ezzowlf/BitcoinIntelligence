from __future__ import annotations
from dataclasses import asdict


def build_market_state(technical: dict, cycle: dict, modules: dict, evidence: dict) -> dict:
    score = technical["score"]
    states = technical["states"]
    dimensions = {
        "long_term_value": score.total,
        "swing_opportunity": score.total,
        "technical_timing": 75 if states["confirmation"] == "HIGH" else 50 if states["confirmation"] == "MEDIUM" else 25,
        "risk": 75 if states["risk"] == "HIGH" else 50 if states["risk"] == "MEDIUM" else 25,
        "onchain": modules.get("onchain", {}).get("score"),
        "institutional_flows": modules.get("etf", {}).get("score"),
        "derivatives": modules.get("derivatives", {}).get("score"),
        "macro": modules.get("macro", {}).get("score"),
        "seasonality": modules.get("seasonality", {}).get("score"),
        "news_risk": modules.get("news", {}).get("risk"),
        "evidence": evidence["score"],
    }
    return {"timestamp": technical["timestamp"], "symbol": "BTCUSD", "cycle": cycle, "dimensions": dimensions, "entry_timing": "CONFIRMED" if states["confirmation"] == "HIGH" else "WATCH" if states["confirmation"] == "MEDIUM" else "WAIT", "technical": {"opportunity_score": asdict(score), "states": states}, "modules": modules, "evidence": evidence, "disclaimer": "Research output; no calibrated probability and no investment advice."}

