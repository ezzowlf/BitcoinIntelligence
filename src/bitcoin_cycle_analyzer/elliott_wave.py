from __future__ import annotations
import pandas as pd


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

