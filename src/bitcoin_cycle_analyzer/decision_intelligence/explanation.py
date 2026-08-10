"""Deterministic Explanation Facts (Teil 8/18/19/20/21/22 of Auftrag 1).

These templates are the AI FALLBACK: if the LLM is offline, this module
alone must still make the terminal fully usable. The pipeline is always
RAW DATA -> engines -> DecisionState -> explanation facts -> (optional) AI
gloss. The AI layer, wired in the dashboard, only rephrases these facts —
it never invents a decision.
"""
from __future__ import annotations


def build_explanation_facts(decision_state: dict) -> dict:
    d = decision_state
    supporting = d["evidence_agreement"]["supporting_families"]
    contradicting = d["evidence_agreement"]["contradicting_families"]
    unavailable = d["evidence_agreement"]["unavailable_families"]

    why_positive = [f"+ {fam}: {next(x['facts'][0] for x in d['evidence_families'] if x['family']==fam)}" for fam in supporting]
    why_negative = [f"- {fam}: {next(x['facts'][0] for x in d['evidence_families'] if x['family']==fam)}" for fam in contradicting]

    zone = d.get("active_zone")
    zone_text = f"{zone['label']} (${zone['lower']:,.0f}–${zone['upper']:,.0f})" if zone and zone.get("lower") else "no active structural zone"

    missing = [t["description"] for t in d["confirmation"]["triggers"].values() if not t["met"]]
    what_next = missing if d["decision"] in ("ACCUMULATE", "WATCH") else []
    why_not_buy_missing = missing if d["decision"] not in ("STRONG_BUY", "BUY") else []

    invalidation_text = (f"Below ${d['invalidation_level']:,.0f}: {d['invalidation_reason']}" if d.get("invalidation_level") else "No structural invalidation level available")

    conclusion = {
        "STRONG_BUY": "High-confluence confirmed entry.",
        "BUY": "Confirmed entry with acceptable evidence agreement.",
        "ACCUMULATE": "Interesting long-term region, but entry is not yet confirmed.",
        "WATCH": "Zone active, but no eligible entry playbook or confirmation yet — monitor only.",
        "WAIT": "No validated edge yet; standing aside is the correct outcome here.",
        "REDUCE": "Risk factors outweigh remaining upside evidence for existing exposure.",
        "TAKE_PROFIT": "Price is near a confirmed distribution/resistance reference.",
        "HIGH_RISK": "Active high-risk zone with elevated sell-off risk — no new exposure.",
        "SELL": "Distribution confirmed with contradicting evidence dominant.",
        "NO_EDGE": "No structural zone, no evidence edge — nothing actionable right now.",
    }.get(d["decision"], "")

    summary = (
        f"Bitcoin is in a {d['cycle_bucket'].replace('_', ' ').lower()} cycle phase. "
        f"Current price sits in {zone_text}. "
        f"{len(supporting)} independent evidence families support the current read"
        + (f", {len(contradicting)} contradict it" if contradicting else "")
        + (f", {len(unavailable)} unavailable" if unavailable else "")
        + f". Decision: {d['decision']} ({d['decision_confidence']['label']} confidence, {d['decision_confidence']['score']}/100)."
    )

    return {
        "summary": summary,
        "why_positive": why_positive,
        "why_negative": why_negative,
        "what_am_i_waiting_for": what_next,
        "what_invalidates_this": invalidation_text,
        "what_happens_next": d["next_expected_transition"],
        "conclusion": conclusion,
        "why_not_buy": why_negative + [f"Missing confirmation: {m}" for m in why_not_buy_missing],
        "targets": d["targets"],
        "rule_ids": d["reasons"]["rule_ids"],
        "role": "RESEARCH_ONLY / CONTEXT_ONLY — explanation of engine state, not investment advice",
    }
