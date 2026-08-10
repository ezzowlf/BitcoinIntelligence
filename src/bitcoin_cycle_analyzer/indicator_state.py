"""View-model layer for the UI.

Builds two read-only, JSON-serialisable snapshots out of the existing
`analyze_intelligence(...)` state tree. Neither function computes anything new —
they only select and reshape fields that CONTROL 3 / SPECIALIST 5 / FUSION 6 /
MACRO 7 already produced. Nothing here feeds back into any engine or into
execution. Both remain RESEARCH_ONLY / CONTEXT_ONLY exports.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone


def build_decision_state_v1(state: dict, macro7: dict, live_price: float, active_scenario: dict, timing_state: str) -> dict:
    """BitcoinDecisionStateV1 — the single object the 3-second header renders from."""
    md = state["master"]["decision"]
    return {
        "version": "BitcoinDecisionStateV1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "btc_price": live_price,
        "macro": macro7["actions"]["macro"],
        "long_swing": macro7["actions"]["long_swing"],
        "timing": timing_state,
        "risk": macro7["actions"]["risk"],
        "current_scenario": {"name": active_scenario["name"], "status": active_scenario["status"]},
        "why": macro7["why"],
        "waiting_for": md.get("waiting_for", []),
        "execution": "DISABLED",
        "role": "RESEARCH_ONLY / CONTEXT_ONLY",
    }


def build_indicator_state_v1(state: dict, macro7: dict, symbol: str = "BTCUSD", timeframe: str = "1D") -> dict:
    """BitcoinIndicatorStateV1 — the schema a future TradingView/Pine/MQL5/API/Telegram
    export would publish. This function only assembles the payload; it does not
    transmit, schedule, or execute anything."""
    active = next((x for x in macro7["scenarios"] if x["status"] == "ACTIVE"), macro7["scenarios"][0])
    zone = macro7["zones"].get("tactical_buy") or macro7["zones"].get("swing_buy")
    return {
        "version": "BitcoinIndicatorStateV1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe": timeframe,
        "signal_type": active["name"],
        "signal_state": active["status"],
        "entry_zone": None if zone is None else {"low": zone["low"], "high": zone["high"]},
        "risk_zone": macro7["zones"].get("extreme_cycle"),
        "invalidation": macro7["elliott"]["primary"].get("invalidation_level"),
        "evidence": "RESEARCH" if macro7["elliott"]["status"] == "RESEARCH_ONLY" else "VALIDATED",
        "historical_quality": state["historical_entry_quality"].get("score"),
        "cycle": state["fusion6"]["regime"],
        "regime": macro7["cycle"]["phase"],
        "execution": "DISABLED",
    }


def rule_registry(macro7: dict) -> dict:
    """Machine-readable export of the currently active scenario/zone rule set.
    Read-only reflection of MACRO 7 research state — does not alter it."""
    return {
        "version": "RuleRegistryV1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": [
            {
                "name": s["name"],
                "status": s["status"],
                "activation_conditions": s["activation_conditions"],
                "invalidation_conditions": s["invalidation_conditions"],
                "price_zone": s["price_zone"],
            }
            for s in macro7["scenarios"]
        ],
        "zones": {k: v for k, v in macro7["zones"].items() if v is not None},
        "execution": "DISABLED",
    }


PINE_MQL_CAPABILITY_MATRIX = [
    {"capability": "Macro/Swing zone levels (price bands)", "pine": "READY · hlines/boxes from entry_zone,risk_zone", "mql5": "READY · price levels from JSON/CSV export"},
    {"capability": "Scenario state (ACTIVE/WATCH/DORMANT/INVALIDATED)", "pine": "READY · label/plotchar from signal_state", "mql5": "READY · comment/label overlay"},
    {"capability": "Decision labels (MACRO/LONG SWING/TIMING/RISK)", "pine": "READY · table() overlay", "mql5": "READY · ObjectCreate OBJ_LABEL"},
    {"capability": "Elliott primary/alternative counts", "pine": "PARTIAL · static pivot markers only, no live recompute", "mql5": "PARTIAL · same limitation"},
    {"capability": "Rare signal markers (3-20/yr)", "pine": "READY · plotshape from signal_book export", "mql5": "READY · arrow objects"},
    {"capability": "Push/alert delivery", "pine": "READY · alertcondition()", "mql5": "READY · Alert()/SendNotification()"},
    {"capability": "Historical entry-quality score", "pine": "READY · numeric input series", "mql5": "READY · numeric input series"},
    {"capability": "Live order placement / execution", "pine": "NOT PLANNED · execution hard-disabled by design", "mql5": "NOT PLANNED · execution hard-disabled by design"},
]


def write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
