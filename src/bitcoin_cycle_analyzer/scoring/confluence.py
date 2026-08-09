from __future__ import annotations


def confluence_score(factors: list[dict]) -> dict:
    """Counts at most one strongest factor per redundancy group."""
    selected = {}
    unavailable = []
    seen_evidence = set()
    for factor in factors:
        if factor.get("status", "AVAILABLE") != "AVAILABLE":
            unavailable.append(factor.get("name", "unknown"))
            continue
        group = factor.get("group", factor["name"])
        evidence_key = (factor.get("source_id"), factor.get("event_id"))
        if evidence_key != (None, None) and evidence_key in seen_evidence:
            continue
        seen_evidence.add(evidence_key)
        strength = max(-1, min(1, float(factor.get("strength", 0))))
        if group not in selected or abs(strength) > abs(selected[group]["strength"]):
            selected[group] = {**factor, "strength": strength}
    if not selected:
        return {"score": None, "level": "UNAVAILABLE", "selected": [], "unavailable": unavailable}
    directional = sum(item["strength"] for item in selected.values()) / len(selected)
    magnitude = sum(abs(item["strength"]) for item in selected.values()) / len(selected)
    level = "VERY HIGH" if magnitude >= .8 and len(selected) >= 5 else "HIGH" if magnitude >= .65 else "MEDIUM" if magnitude >= .4 else "LOW"
    return {"score": round((directional + 1) * 50, 1), "level": level, "independent_groups": len(selected), "selected": list(selected.values()), "unavailable": unavailable, "note": "Correlated factors in one group are counted once."}
