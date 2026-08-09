from __future__ import annotations
import numpy as np


def drawdown_risk(technical: dict, derivatives: dict | None = None, macro: dict | None = None, onchain: dict | None = None) -> dict:
    dd = abs(float(technical.get("drawdown_from_ath", 0)))
    historical = technical.get("forward_summary_365d", {})
    worst = historical.get("worst_drawdown")
    analog_risk = min(1, abs(worst)) if worst is not None else .5
    structure = technical.get("structure", {}).get("trend", "unknown")
    score = .35 * min(1, dd / .7) + .4 * analog_risk + .25 * (1 if structure == "bearish" else .5 if structure == "corrective" else .2)
    used = ["ath_distance", "historical_analogues", "market_structure"]
    if derivatives and derivatives.get("risk_score") is not None:
        score = score * .8 + derivatives["risk_score"] / 100 * .2; used.append("derivatives")
    score = round(max(0, min(100, score * 100)), 1)
    returns = technical.get("similar_cases")
    return {"score":score,"label":"HIGH" if score>=70 else "MEDIUM" if score>=40 else "LOW","historical_similar_episodes":{"sample_size":historical.get("count",0),"worst_further_drawdown":worst},"inputs_used":used,"note":"Risk score is not a calibrated probability."}
