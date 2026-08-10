"""Structural Zone Engine (Teil 4/5/16 of Auftrag 1).

Builds a small set of labelled, explainable price zones purely from fields
MACRO 7 / CONTROL 3 / SPECIALIST 5 already computed (macro7["zones"],
ms["buy_zones"], ms["nearest_support"/"nearest_resistance"], m5["risk"]).
No new price geometry (Fib, pivots, support clustering) is computed here —
that already happens inside the existing, untouched engines. This module
only labels/classifies those existing zones and attaches evidence-family
confluence so the UI/Decision Engine can distinguish INTERESTING AREA from
CONFIRMED ENTRY (Teil 2).
"""
from __future__ import annotations
from .evidence import independent_agreement

ZONE_TYPES = ("STRONG_BUY_ZONE", "BUY_ZONE", "WATCH_ZONE", "TAKE_PROFIT_ZONE", "HIGH_RISK_ZONE")


def _confidence_tier(confluence_count: int | None, control3_confidence: str | None) -> str:
    if control3_confidence == "HIGH" or (confluence_count or 0) >= 6:
        return "HIGH"
    if control3_confidence == "MODERATE" or (confluence_count or 0) >= 3:
        return "MODERATE"
    return "LOW"


def build_structural_zones(state: dict, macro7: dict, live_price: float, evidence_families: list[dict]) -> list[dict]:
    ms = state["master"]["state"]
    m5 = state["master5_challenger"]
    agreement = independent_agreement(evidence_families)
    zones = []

    # Buy-side zones: CONTROL 3's own buy_zones already carry a confluence_count
    # and confidence tier — reused verbatim, not recomputed.
    for i, z in enumerate(ms.get("buy_zones", [])):
        if z.get("status") != "AVAILABLE":
            continue
        tier = _confidence_tier(z.get("confluence_count"), z.get("confidence"))
        cycle_supportive = macro7["actions"]["macro"] == "ACCUMULATE"
        zone_type = "STRONG_BUY_ZONE" if (tier == "HIGH" and cycle_supportive and agreement["supporting_count"] >= 3) else "BUY_ZONE" if tier in ("HIGH", "MODERATE") else "WATCH_ZONE"
        zones.append({
            "zone_id": f"DZ-BUY-{i+1}",
            "zone_type": zone_type,
            "label": z.get("label"),
            "lower": z["low"], "upper": z["high"],
            "active": z["low"] <= live_price <= z["high"],
            "confidence": tier,
            "supporting_families": agreement["supporting_families"],
            "contradicting_families": agreement["contradicting_families"],
            "why": f"CONTROL 3 buy zone, confluence_count={z.get('confluence_count')}, confidence={z.get('confidence')}; MACRO 7 action={macro7['actions']['macro']}",
            "provenance": ["master.state.buy_zones", "macro7.actions.macro", "evidence_families"],
        })

    # Macro accumulation / deep-value / extreme-cycle zones from MACRO 7.
    macro_zone_labels = {"tactical_buy": "TACTICAL BUY", "macro_accumulation": "MACRO ACCUMULATION", "deep_value": "DEEP VALUE", "extreme_cycle": "EXTREME CYCLE"}
    for key, label in macro_zone_labels.items():
        z = macro7["zones"].get(key)
        if not z:
            continue
        zone_type = "HIGH_RISK_ZONE" if key == "extreme_cycle" else "WATCH_ZONE" if z.get("support") == "LOW" else "BUY_ZONE"
        zones.append({
            "zone_id": f"DZ-{key.upper()}",
            "zone_type": zone_type,
            "label": label,
            "lower": z["low"], "upper": z["high"],
            "active": z["low"] <= live_price <= z["high"],
            "confidence": z.get("support", "LOW"),
            "supporting_families": agreement["supporting_families"],
            "contradicting_families": agreement["contradicting_families"],
            "why": f"MACRO 7 {key} zone, support={z.get('support')}",
            "provenance": [f"macro7.zones.{key}"],
        })

    # Distribution / take-profit reference from nearest resistance.
    resistance = ms.get("nearest_resistance")
    if resistance:
        zones.append({
            "zone_id": "DZ-TAKE-PROFIT",
            "zone_type": "TAKE_PROFIT_ZONE",
            "label": "MAJOR RESISTANCE / DISTRIBUTION REFERENCE",
            "lower": resistance["lower_bound"], "upper": resistance["upper_bound"],
            "active": resistance["lower_bound"] <= live_price <= resistance["upper_bound"],
            "confidence": resistance.get("confidence", "LOW"),
            "supporting_families": [], "contradicting_families": [],
            "why": f"CONTROL 3 nearest_resistance, confidence={resistance.get('confidence')}, {resistance.get('touch_count')} historical touches",
            "provenance": ["master.state.nearest_resistance"],
        })

    # High-risk / sell-off reference from SPECIALIST 5's own risk read.
    if m5["risk"]["sell_off_risk"] in ("HIGH", "ELEVATED") or m5["risk"]["distribution"] in ("DISTRIBUTION", "DISTRIBUTION_CONFIRMED"):
        zones.append({
            "zone_id": "DZ-HIGH-RISK",
            "zone_type": "HIGH_RISK_ZONE",
            "label": "SELL-OFF / DISTRIBUTION RISK",
            "lower": None, "upper": None, "active": True,
            "confidence": m5["risk"]["sell_off_risk"],
            "supporting_families": [], "contradicting_families": [],
            "why": f"SPECIALIST 5 sell_off_risk={m5['risk']['sell_off_risk']}, distribution={m5['risk']['distribution']}",
            "provenance": ["master5_challenger.risk"],
        })

    return zones


def active_zone(zones: list[dict]) -> dict | None:
    """The zone the current price is actually inside, preferring the
    highest-priority type if several overlap (STRONG_BUY > BUY > WATCH >
    TAKE_PROFIT > HIGH_RISK for display purposes — HIGH_RISK is still
    reported separately by the Decision Engine regardless of this pick)."""
    priority = {"STRONG_BUY_ZONE": 0, "BUY_ZONE": 1, "WATCH_ZONE": 2, "TAKE_PROFIT_ZONE": 3, "HIGH_RISK_ZONE": 4}
    candidates = [z for z in zones if z.get("active") and z.get("lower") is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda z: priority.get(z["zone_type"], 9))
