"""Decision Engine (Teil 3/25 of Auftrag 1).

Produces one canonical DecisionState per run. States are assigned by
EXPLICIT RULES, never by summing an opaque score across an arbitrary
threshold — every branch below is auditable and traces back to Rule
Registry IDs in rules.py.
"""
from __future__ import annotations
import pandas as pd

from .evidence import assess_evidence_families, independent_agreement
from .cycle_elliott_context import elliott_cycle_context
from .zones import build_structural_zones, active_zone
from .confirmation import evaluate_confirmation
from .playbooks import match_playbooks

DECISION_STATES = ("STRONG_BUY", "BUY", "ACCUMULATE", "WATCH", "WAIT", "REDUCE", "TAKE_PROFIT", "HIGH_RISK", "SELL", "NO_EDGE")


def _confidence_label(supporting: int, contradicting: int, confirmation_met: int) -> tuple[str, int]:
    score = max(0, min(100, 30 + supporting * 12 - contradicting * 10 + confirmation_met * 8))
    label = "VERY HIGH" if score >= 80 else "HIGH" if score >= 62 else "MODERATE" if score >= 40 else "LOW"
    return label, score


def build_decision_state(state: dict, macro7: dict, frame: pd.DataFrame, live_price: float) -> dict:
    ms = state["master"]["state"]
    m5 = state["master5_challenger"]
    cycle_current = state["elliott_cycle"]["cycle_history"]["current"]

    families = assess_evidence_families(state, macro7, live_price)
    agreement = independent_agreement(families)
    elliott_ctx = elliott_cycle_context(macro7, cycle_current)
    zones = build_structural_zones(state, macro7, live_price, families)
    zone = active_zone(zones)
    confirmation = evaluate_confirmation(state, macro7, frame, live_price)
    supporting, contradicting = agreement["supporting_count"], agreement["contradicting_count"]
    playbooks = match_playbooks(elliott_ctx["cycle_bucket"], zone, supporting, confirmation) if zone else []

    primary = macro7["elliott"]["primary"]
    invalidation_level = primary.get("invalidation_level")
    hard_invalidation_breached = invalidation_level is not None and live_price < invalidation_level

    high_risk_active = any(z["zone_type"] == "HIGH_RISK_ZONE" and z.get("active") for z in zones)
    take_profit_active = any(z["zone_type"] == "TAKE_PROFIT_ZONE" and z.get("active") for z in zones)
    confirmed_playbooks = [p for p in playbooks if p["entry_status"] == "CONFIRMED"]

    reasons = {"rule_ids": [], "supporting_evidence": agreement["supporting_families"], "contradicting_evidence": agreement["contradicting_families"]}

    # RULE ORDER — explicit, auditable (Rule Registry DE-001..DE-006).
    if high_risk_active and m5["risk"]["sell_off_risk"] in ("HIGH", "ELEVATED"):
        decision = "HIGH_RISK"
        reasons["rule_ids"].append("DE-001: active HIGH_RISK_ZONE + SPECIALIST 5 sell_off_risk elevated")
        entry_status = "NOT_APPLICABLE"
    elif take_profit_active and m5["risk"]["distribution"] in ("DISTRIBUTION", "DISTRIBUTION_CONFIRMED"):
        decision = "TAKE_PROFIT"
        reasons["rule_ids"].append("DE-002: price at major resistance + distribution confirmed by SPECIALIST 5")
        entry_status = "NOT_APPLICABLE"
    elif zone is None:
        decision = "NO_EDGE" if not zones else "WAIT"
        reasons["rule_ids"].append("DE-003: no active structural zone at current price")
        entry_status = "NOT_APPLICABLE"
    elif confirmed_playbooks and not hard_invalidation_breached and contradicting < supporting:
        strong = (zone["zone_type"] == "STRONG_BUY_ZONE" and supporting >= 3 and contradicting == 0 and confirmation["met_count"] >= 4)
        decision = "STRONG_BUY" if strong else "BUY"
        reasons["rule_ids"].append(f"DE-004{'a' if strong else 'b'}: playbook confirmed ({confirmed_playbooks[0]['name']}), quality gates passed, invalidation intact")
        entry_status = "CONFIRMED"
    elif hard_invalidation_breached:
        decision = "WAIT"
        reasons["rule_ids"].append("DE-005: Elliott primary-count invalidation breached — thesis degraded, no entry regardless of zone")
        entry_status = "NOT_CONFIRMED"
    elif playbooks:
        decision = "ACCUMULATE" if zone["zone_type"] in ("STRONG_BUY_ZONE", "BUY_ZONE") else "WATCH"
        reasons["rule_ids"].append(f"DE-006: zone valid, playbook eligible ({playbooks[0]['name']}) but confirmation not yet met")
        entry_status = "WAITING_FOR_CONFIRMATION"
    else:
        decision = "WATCH" if zone["zone_type"] != "HIGH_RISK_ZONE" else "HIGH_RISK"
        reasons["rule_ids"].append("DE-007: zone active but no cycle-eligible entry playbook — interesting area only")
        entry_status = "NOT_CONFIRMED"

    confidence_label, confidence_score = _confidence_label(supporting, contradicting, confirmation["met_count"])
    if agreement["unavailable_families"]:
        # Data quality must reduce confidence, never silently pretend neutrality (Teil 26/27).
        confidence_score = max(0, confidence_score - 5 * len(agreement["unavailable_families"]))
        confidence_label = "VERY HIGH" if confidence_score >= 80 else "HIGH" if confidence_score >= 62 else "MODERATE" if confidence_score >= 40 else "LOW"

    resistance = ms.get("nearest_resistance")
    targets = []
    if resistance:
        targets.append({"id": "T1", "price": resistance["lower_bound"], "why": "Nearest confirmed resistance (CONTROL 3)"})
    if primary.get("confirmation_level"):
        targets.append({"id": "T2", "price": primary["confirmation_level"], "why": "Elliott primary-count confirmation level (MACRO 7)"})
    ath = macro7["indicators"].get("ath")
    if ath:
        targets.append({"id": "T3", "price": ath, "why": "Cycle all-time-high reference (MACRO 7)"})

    next_transition = {
        "becomes_buy_if": [t["description"] for t in confirmation["triggers"].values() if not t["met"]] if decision in ("ACCUMULATE", "WATCH") else [],
        "becomes_high_risk_if": [f"Weekly close below invalidation ${invalidation_level:,.0f}" if invalidation_level else "Structural invalidation undefined"],
    }

    return {
        "version": "DecisionStateV1",
        "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "current_price": live_price,
        "cycle_phase": macro7["cycle"]["phase"],
        "cycle_bucket": elliott_ctx["cycle_bucket"],
        "cycle_confidence": macro7["cycle"].get("confidence"),
        "regime": state["fusion6"]["regime"],
        "elliott_structure": elliott_ctx,
        "structural_context": {"nearest_support": ms.get("nearest_support"), "nearest_resistance": ms.get("nearest_resistance")},
        "zones": zones,
        "active_zone": zone,
        "decision": decision,
        "decision_confidence": {"label": confidence_label, "score": confidence_score},
        "entry_status": entry_status,
        "confirmation": confirmation,
        "invalidation_level": invalidation_level,
        "invalidation_reason": primary.get("invalidation_reason"),
        "hard_invalidation_breached": hard_invalidation_breached,
        "targets": targets,
        "evidence_families": families,
        "evidence_agreement": agreement,
        "playbooks_matched": playbooks,
        "historical_sample_size": state["historical_entry_quality"].get("sample_size"),
        "historical_success_rate": None,  # not computed without a dedicated backtest — never fabricated
        "historical_confidence": "LOW" if state["historical_entry_quality"].get("sample_size", 0) < 4 else "MODERATE",
        "risk_state": m5["risk"]["sell_off_risk"],
        "next_expected_transition": next_transition,
        "reasons": reasons,
        "execution": "DISABLED",
    }
