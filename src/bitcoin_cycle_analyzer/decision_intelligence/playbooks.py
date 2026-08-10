"""Entry Playbooks (Teil 6 of Auftrag 1).

Each playbook is an explicit, auditable rule set — not a score threshold.
A playbook is ELIGIBLE when the current cycle bucket, active zone type, and
minimum independent evidence-family agreement are all satisfied. Whether the
entry is CONFIRMED still depends entirely on the Confirmation Engine
(confirmation.py) — eligibility never implies confirmation (Teil 5).
"""
from __future__ import annotations

ENTRY_PLAYBOOKS = [
    {
        "id": "EP-001", "name": "CYCLE_BOTTOM_ENTRY",
        "allowed_cycle_buckets": ("DEEP_BEAR_BOTTOM_SEARCH",),
        "allowed_zone_types": ("STRONG_BUY_ZONE", "BUY_ZONE"),
        "min_supporting_families": 3,
        "required_triggers": ("swing_low_confirmed", "higher_low"),
        "risk_classification": "HIGH_REWARD_HIGH_UNCERTAINTY",
        "reasons_against": ["Historical sample of true cycle bottoms is small (N<=4) — confidence must stay bounded"],
    },
    {
        "id": "EP-002", "name": "RECOVERY_ENTRY",
        "allowed_cycle_buckets": ("DEEP_BEAR_BOTTOM_SEARCH", "LATE_BEAR"),
        "allowed_zone_types": ("BUY_ZONE", "WATCH_ZONE"),
        "min_supporting_families": 2,
        "required_triggers": ("weekly_reclaim", "momentum_recovery"),
        "risk_classification": "MODERATE",
        "reasons_against": ["Recovery attempts can fail and revisit lower structure"],
    },
    {
        "id": "EP-003", "name": "WAVE2_RETRACEMENT_ENTRY",
        "allowed_cycle_buckets": ("EARLY_BULL",),
        "allowed_zone_types": ("BUY_ZONE", "WATCH_ZONE"),
        "min_supporting_families": 2,
        "required_triggers": ("higher_low", "structure_reclaim"),
        "risk_classification": "MODERATE",
        "reasons_against": ["Requires a confirmed Wave 1 impulse, which the current engine cannot yet formally label"],
    },
    {
        "id": "EP-004", "name": "BREAKOUT_RECLAIM_ENTRY",
        "allowed_cycle_buckets": ("EARLY_BULL", "MID_BULL", "TRANSITION"),
        "allowed_zone_types": ("BUY_ZONE",),
        "min_supporting_families": 2,
        "required_triggers": ("structure_reclaim", "weekly_reclaim"),
        "risk_classification": "MODERATE",
        "reasons_against": ["False breakouts are common; needs weekly (not intraday) confirmation"],
    },
    {
        "id": "EP-005", "name": "DEEP_VALUE_ACCUMULATION",
        "allowed_cycle_buckets": ("DEEP_BEAR_BOTTOM_SEARCH", "LATE_BEAR"),
        "allowed_zone_types": ("STRONG_BUY_ZONE", "BUY_ZONE"),
        "min_supporting_families": 3,
        "required_triggers": (),  # accumulation does not require a confirmed reversal, only a valid zone
        "risk_classification": "LOW_TIMING_PRECISION",
        "reasons_against": ["No timing precision — position can be underwater for an extended period before recovery"],
    },
    {
        "id": "EP-006", "name": "MAJOR_SUPPORT_RETEST",
        "allowed_cycle_buckets": ("LATE_BEAR", "EARLY_BULL", "MID_BULL"),
        "allowed_zone_types": ("BUY_ZONE", "WATCH_ZONE"),
        "min_supporting_families": 2,
        "required_triggers": ("higher_low",),
        "risk_classification": "MODERATE",
        "reasons_against": ["Retest can fail on the second touch; support strength decays with repeated tests"],
    },
    {
        "id": "EP-007", "name": "POST_CAPITULATION_ENTRY",
        "allowed_cycle_buckets": ("DEEP_BEAR_BOTTOM_SEARCH",),
        "allowed_zone_types": ("STRONG_BUY_ZONE", "BUY_ZONE"),
        "min_supporting_families": 2,
        "required_triggers": ("swing_low_confirmed",),
        "risk_classification": "HIGH_REWARD_HIGH_UNCERTAINTY",
        "reasons_against": ["Capitulation can be followed by a deeper capitulation; no guaranteed single bottom"],
    },
]


def match_playbooks(cycle_bucket: str, zone: dict | None, supporting_count: int, confirmation: dict) -> list[dict]:
    if zone is None:
        return []
    matches = []
    for pb in ENTRY_PLAYBOOKS:
        if cycle_bucket not in pb["allowed_cycle_buckets"]:
            continue
        if zone["zone_type"] not in pb["allowed_zone_types"]:
            continue
        if supporting_count < pb["min_supporting_families"]:
            continue
        required_met = all(confirmation["triggers"].get(t, {}).get("met") for t in pb["required_triggers"])
        matches.append({
            **pb,
            "zone_id": zone["zone_id"],
            "entry_status": "CONFIRMED" if required_met and pb["required_triggers"] else ("WAITING_FOR_CONFIRMATION" if pb["required_triggers"] else "ZONE_VALID_NO_TIMING_TRIGGER"),
            "missing_triggers": [t for t in pb["required_triggers"] if not confirmation["triggers"].get(t, {}).get("met")],
        })
    return matches
