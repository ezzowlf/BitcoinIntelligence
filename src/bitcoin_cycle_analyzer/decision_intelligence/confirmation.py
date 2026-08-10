"""Confirmation Engine (Teil 5/22 of Auftrag 1).

Confirmation triggers are derived exclusively from facts the existing
engines already expose (confirmed swings, Elliott confirmation/invalidation
levels, weekly closes already present in the canonical OHLCV frame). No new
indicator is introduced — this module only asks yes/no questions about
data that already exists.
"""
from __future__ import annotations
import pandas as pd


def _weekly_closes(frame: pd.DataFrame) -> pd.Series:
    return frame.close.resample("W-MON").last().dropna()


def evaluate_confirmation(state: dict, macro7: dict, frame: pd.DataFrame, live_price: float) -> dict:
    primary = macro7["elliott"]["primary"]
    elliott = state["elliott_cycle"]["elliott"]
    swings = pd.DataFrame(elliott["evidence"]["confirmed_swings"])
    weekly = _weekly_closes(frame)

    confirmation_level = primary.get("confirmation_level")
    weekly_reclaim = bool(confirmation_level is not None and len(weekly) and float(weekly.iloc[-1]) > confirmation_level)

    higher_low = False
    if len(swings) and "kind" in swings.columns:
        lows = swings[swings.kind == "low"]
        if len(lows) >= 2:
            higher_low = float(lows.price.iloc[-1]) > float(lows.price.iloc[-2])

    resistance = state["master"]["state"].get("nearest_resistance")
    structure_reclaim = bool(resistance and live_price > resistance["lower_bound"])

    weekly_rsi = state["advanced"]["momentum"].get("weekly", {}).get("rsi")
    momentum_recovery = bool(weekly_rsi is not None and weekly_rsi > 45)

    swing_low_confirmed = bool(len(swings) and swings.iloc[-1].get("kind") == "low")

    triggers = {
        "weekly_reclaim": {"met": weekly_reclaim, "description": f"Weekly close > Elliott confirmation level (${confirmation_level:,.0f})" if confirmation_level else "Confirmation level unavailable"},
        "structure_reclaim": {"met": structure_reclaim, "description": f"Price > nearest resistance lower bound (${resistance['lower_bound']:,.0f})" if resistance else "Resistance reference unavailable"},
        "higher_low": {"met": higher_low, "description": "Last confirmed swing low is higher than the previous confirmed swing low"},
        "momentum_recovery": {"met": momentum_recovery, "description": f"Weekly RSI {weekly_rsi} > 45"},
        "swing_low_confirmed": {"met": swing_low_confirmed, "description": "Most recent confirmed swing is a LOW (structure not yet reversed)"},
    }
    met_count = sum(1 for t in triggers.values() if t["met"])
    if met_count >= 3:
        state_label = "CONFIRMED"
    elif met_count >= 1:
        state_label = "PARTIAL"
    else:
        state_label = "NOT_CONFIRMED"
    return {"confirmation_state": state_label, "triggers": triggers, "met_count": met_count, "provenance": ["macro7.elliott.primary.confirmation_level", "elliott_cycle.elliott.evidence.confirmed_swings", "master.state.nearest_resistance", "advanced.momentum.weekly.rsi"]}
