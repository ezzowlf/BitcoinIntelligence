from __future__ import annotations


def build_alert(state: dict, min_value: float = 75, min_evidence: float = 50) -> dict | None:
    dimensions = state["dimensions"]
    if dimensions["long_term_value"] < min_value or dimensions["evidence"] < min_evidence:
        return None
    return {"type": "BITCOIN_CONFLUENCE_ALERT", "timestamp": state["timestamp"], "long_term_value": dimensions["long_term_value"], "evidence": dimensions["evidence"], "confluence": state["confluence"], "entry_confirmation": state["entry_timing"], "risk": dimensions["risk"], "action": "WATCH FOR CONFIRMATION", "execution": "DISABLED"}

