"""Evidence Family model.

Groups existing engine outputs into a small number of INDEPENDENT evidence
families, so the Decision Engine can require agreement ACROSS families
rather than counting five correlated variants of the same underlying signal
(e.g. RSI + Momentum + Bollinger all measure similar price behaviour and
must not be treated as three independent confirmations).

Every fact quoted here already exists in `state` — this module does not
compute new technical indicators, it only classifies and labels existing
ones into SUPPORT / CONTRADICT / NEUTRAL / UNAVAILABLE.
"""
from __future__ import annotations

EVIDENCE_FAMILIES = ("CYCLE", "STRUCTURE", "VALUATION", "MOMENTUM", "HISTORICAL", "MACRO", "POSITIONING")

_STRENGTH_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2}


def _family(name, direction, strength, facts, provenance):
    return {"family": name, "direction": direction, "strength": strength, "facts": facts, "provenance": provenance}


def _cycle_family(macro7: dict) -> dict:
    action = macro7["actions"]["macro"]
    confidence = macro7["cycle"].get("confidence", "LOW")
    direction = "SUPPORT" if action == "ACCUMULATE" else "CONTRADICT" if action == "REDUCE" else "NEUTRAL"
    facts = [f"MACRO 7 cycle phase: {macro7['cycle']['phase']} ({confidence} confidence)", f"Macro action: {action}"]
    return _family("CYCLE", direction, confidence if confidence in _STRENGTH_ORDER else "LOW", facts, ["macro7.cycle", "macro7.actions.macro"])


def _structure_family(ms: dict, macro_e: dict, live_price: float) -> dict:
    supportive = ms.get("confluence", {}).get("supportive_groups", [])
    has_structure_support = "PRICE_STRUCTURE" in supportive
    primary = macro_e["primary"]
    invalidation = primary.get("invalidation_level")
    broken = invalidation is not None and live_price < invalidation
    if broken:
        direction, strength = "CONTRADICT", "HIGH"
        facts = [f"Price ${live_price:,.0f} is BELOW the Elliott primary-count invalidation level ${invalidation:,.0f}"]
    elif has_structure_support:
        direction, strength = "SUPPORT", "MODERATE"
        facts = ["CONTROL 3 confluence flags PRICE_STRUCTURE as a supportive group", f"Elliott primary count: {primary.get('name')}"]
    else:
        direction, strength = "NEUTRAL", "LOW"
        facts = ["No structural (support/resistance/Elliott) confluence flagged"]
    return _family("STRUCTURE", direction, strength, facts, ["master.state.confluence", "macro7.elliott.primary"])


def _valuation_family(ms: dict, hq: dict) -> dict:
    supportive = ms.get("confluence", {}).get("supportive_groups", [])
    long_term_value = "LONG_TERM_VALUE" in supportive
    drawdown_pct = ms.get("drawdown_percentile")
    if long_term_value:
        direction, strength = "SUPPORT", "MODERATE"
        facts = ["CONTROL 3 confluence flags LONG_TERM_VALUE as a supportive group"]
    elif drawdown_pct is not None and drawdown_pct >= 70:
        direction, strength = "SUPPORT", "LOW"
        facts = [f"Drawdown percentile {drawdown_pct:.0f} — deeper than most historical observations"]
    else:
        direction, strength = "NEUTRAL", "LOW"
        facts = ["No long-term valuation confluence flagged"]
    facts.append(f"Price vs 200D: {ms.get('price_vs_200d_pct')}, vs 200W: {ms.get('price_vs_200w_pct')}")
    return _family("VALUATION", direction, strength, facts, ["master.state.confluence", "master.state.drawdown_percentile"])


def _momentum_family(mom: dict) -> dict:
    weekly_rsi = mom.get("weekly", {}).get("rsi")
    daily_rsi = mom.get("daily", {}).get("rsi")
    if weekly_rsi is None:
        return _family("MOMENTUM", "UNAVAILABLE", "LOW", ["Weekly RSI unavailable"], ["advanced.momentum.weekly"])
    if weekly_rsi < 35:
        direction, strength = "CONTRADICT", "MODERATE"
        facts = [f"Weekly RSI {weekly_rsi:.1f} — still in negative-momentum territory, no recovery confirmed"]
    elif weekly_rsi > 50:
        direction, strength = "SUPPORT", "LOW"
        facts = [f"Weekly RSI {weekly_rsi:.1f} — momentum neutral-to-positive"]
    else:
        direction, strength = "NEUTRAL", "LOW"
        facts = [f"Weekly RSI {weekly_rsi:.1f} — no clear momentum edge"]
    facts.append(f"Daily RSI: {daily_rsi}")
    return _family("MOMENTUM", direction, strength, facts, ["advanced.momentum.weekly.rsi", "advanced.momentum.daily.rsi"])


def _historical_family(hq: dict) -> dict:
    n = hq.get("sample_size", 0)
    score = hq.get("score")
    if score is None:
        return _family("HISTORICAL", "UNAVAILABLE", "LOW", ["Historical entry-quality score unavailable"], ["historical_entry_quality"])
    direction = "SUPPORT" if score >= 55 else "CONTRADICT" if score < 35 else "NEUTRAL"
    # Never let a thin sample masquerade as strong evidence (Teil 12 / Auftrag 1).
    strength = "LOW" if n < 4 else "MODERATE" if n < 8 else "HIGH"
    facts = [f"Historical entry-quality score {score:.0f}/100 ({hq.get('state')})", f"N = {n} comparable historical episodes"]
    return _family("HISTORICAL", direction, strength, facts, ["historical_entry_quality.score", "historical_entry_quality.sample_size"])


def _macro_family(data_status: dict) -> dict:
    macro_status = data_status.get("macro", {}).get("status", "UNAVAILABLE")
    if macro_status != "AVAILABLE":
        return _family("MACRO", "UNAVAILABLE", "LOW", ["Macro data provider not configured/available — never treated as neutral-bearish"], ["data_status.macro"])
    return _family("MACRO", "NEUTRAL", "LOW", ["Macro data available; no directional macro model computed in this build"], ["data_status.macro"])


def _positioning_family(data_status: dict) -> dict:
    onchain = data_status.get("onchain", {}).get("status", "UNAVAILABLE")
    derivatives = data_status.get("derivatives", {}).get("status", "UNAVAILABLE")
    if onchain != "AVAILABLE" and derivatives != "AVAILABLE":
        return _family("POSITIONING", "UNAVAILABLE", "LOW", ["Onchain and derivatives data unavailable"], ["data_status.onchain", "data_status.derivatives"])
    return _family("POSITIONING", "NEUTRAL", "LOW", [f"Onchain: {onchain}, Derivatives: {derivatives} — data present, no directional positioning model computed in this build"], ["data_status.onchain", "data_status.derivatives"])


def assess_evidence_families(state: dict, macro7: dict, live_price: float) -> list[dict]:
    ms = state["master"]["state"]
    mom = state["advanced"]["momentum"]
    hq = state["historical_entry_quality"]
    data_status = state["data_status"]
    macro_e = macro7["elliott"]
    return [
        _cycle_family(macro7),
        _structure_family(ms, macro_e, live_price),
        _valuation_family(ms, hq),
        _momentum_family(mom),
        _historical_family(hq),
        _macro_family(data_status),
        _positioning_family(data_status),
    ]


def independent_agreement(families: list[dict]) -> dict:
    """Counts INDEPENDENT (cross-family) support/contradiction — never sums
    correlated sub-indicators as if they were separate confirmations."""
    supporting = [f for f in families if f["direction"] == "SUPPORT"]
    contradicting = [f for f in families if f["direction"] == "CONTRADICT"]
    unavailable = [f for f in families if f["direction"] == "UNAVAILABLE"]
    return {
        "supporting_families": [f["family"] for f in supporting],
        "contradicting_families": [f["family"] for f in contradicting],
        "unavailable_families": [f["family"] for f in unavailable],
        "supporting_count": len(supporting),
        "contradicting_count": len(contradicting),
        "conflict_level": (
            "HIGH" if supporting and contradicting and len(contradicting) >= len(supporting)
            else "MODERATE" if supporting and contradicting
            else "LOW" if supporting or contradicting
            else "NONE"
        ),
    }
