from __future__ import annotations
import pandas as pd

from .swing_detection import detect_swings, swings_as_of


def analyze_scenarios(swings: pd.DataFrame) -> list[dict]:
    """Heuristic scenarios, explicitly uncertain and rule-based."""
    scenarios = []
    if len(swings) >= 4:
        a, b, c = list(swings.iloc[-3:].itertuples())
        if a.kind == "low" and b.kind == "high" and c.kind == "low":
            retrace = (b.price - c.price) / max(b.price - a.price, 1e-9)
            confidence = 55 + (10 if 0.8 <= retrace <= 1.8 else 0)
            scenarios.append({"name": "Possible ABC correction / late C", "confidence": confidence, "invalidation": f"Close below {c.price:.2f} after confirmation or break above {b.price:.2f}", "evidence": ["high-low correction sequence", f"C/A proxy {retrace:.2f}"]})
    if len(swings) >= 5:
        recent = swings.iloc[-5:]
        alternating = all(recent.kind.iloc[i] != recent.kind.iloc[i - 1] for i in range(1, 5))
        if alternating:
            scenarios.append({"name": "Possible impulsive/wave-4 structure", "confidence": 35, "invalidation": f"Break of structural extreme {recent.price.min():.2f}", "evidence": ["five alternating confirmed pivots"]})
    if not scenarios:
        scenarios.append({"name": "Alternative / unresolved structure", "confidence": 100, "invalidation": "Reassess after next confirmed swing", "evidence": ["insufficient confirmed pivots"]})
    total = sum(x["confidence"] for x in scenarios)
    for item in scenarios:
        item["confidence"] = round(100 * item["confidence"] / total, 1)
    return scenarios


def analyze_elliott_intelligence(frame: pd.DataFrame, as_of=None, source="BITSTAMP historical dataset", timeframe="1D") -> dict:
    """Causal, explainable scenarios. Relative support is explicitly not probability."""
    cutoff = pd.Timestamp(as_of or frame.index[-1])
    swings = swings_as_of(detect_swings(frame.loc[:cutoff]), cutoff)
    base = analyze_scenarios(swings)
    scenarios=[]
    for rank,item in enumerate(base[:3],1):
        recent=swings.tail(5)
        low=float(recent.price.min()) if not recent.empty else None
        high=float(recent.price.max()) if not recent.empty else None
        scenarios.append({"rank":rank,"label":"PRIMARY" if rank==1 else f"ALTERNATIVE_{rank-1}","name":item["name"],
                          "degree":"INTERMEDIATE" if timeframe in {"1D","1W"} else "MINOR",
                          "relative_support":item["confidence"],"support_is_probability":False,
                          "invalidation_level":low,"invalidation_reason":item["invalidation"],"confirmation_level":high,
                          "rules_passed":["confirmed pivots alternate"] if len(recent)>1 else [],
                          "guidelines_matched":item["evidence"],"guidelines_missed":[],"status":"RESEARCH_ONLY"})
    evidence=[{"pivot_time":row.pivot_time,"confirmed_at":row.confirmed_at,"kind":row.kind,"price":row.price} for row in swings.tail(8).itertuples()]
    return {"status":"RESEARCH_ONLY","timeframe":timeframe,"wave_degree":"INTERMEDIATE" if timeframe in {"1D","1W"} else "MINOR",
            "primary":scenarios[0],"alternatives":scenarios[1:],"scenario_support_is_probability":False,
            "count_stability":{"30d":"INSUFFICIENT_REVISION_HISTORY","90d":"INSUFFICIENT_REVISION_HISTORY"},
            "evidence":{"confirmed_swings":evidence,"source":source,"cutoff":cutoff,"pit":"Only pivots with confirmed_at <= cutoff"}}
