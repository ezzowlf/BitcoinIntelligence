"""Cycle -> Elliott conditional context (Teil 7/8 of Auftrag 1).

IMPORTANT, documented limitation: `FullHistoryElliottEngine` (the existing,
untouched engine) only ever produces two structural hypothesis shapes —
a "wave 4 completion / recovery watch" primary and an "ABC / C-wave
continuation" alternative (see macro7/elliott.py). It does not yet
distinguish Wave 1/2/3 vs Wave 5-exhaustion structures. This module cannot
and does not invent that distinction — inventing new Elliott rules is
explicitly forbidden by the brief. What it DOES do, without adding a single
new price-derived number, is:

1. classify the current cycle into a descriptive bucket using only fields
   MACRO 7 already computed (phase, drawdown, days since ATH/halving)
2. look up, from a static (non-computed) textbook table, which wave
   hypotheses are conventionally relevant for that cycle bucket
3. compare that conventional expectation against the engine's *actual*
   primary/alternative names and flag CONSISTENT vs CONFLICT

This gives the "cycle prior -> Elliott hypothesis" reasoning chain the
brief asks for, without pretending the underlying engine has more
resolution than it actually has.
"""
from __future__ import annotations

CYCLE_BUCKETS = ("DEEP_BEAR_BOTTOM_SEARCH", "LATE_BEAR", "EARLY_BULL", "MID_BULL", "LATE_BULL_DISTRIBUTION", "TRANSITION")

# Static, textbook lookup — not derived from price data, never a new signal.
_CONVENTIONAL_HYPOTHESES = {
    "DEEP_BEAR_BOTTOM_SEARCH": ["ABC correction nearing completion", "Wave C exhaustion / capitulation structure", "possible ending diagonal"],
    "LATE_BEAR": ["ABC correction in progress", "Wave C development"],
    "EARLY_BULL": ["Wave 1 development", "Wave 2 retracement of a new impulse"],
    "MID_BULL": ["Wave 3 development (typically the extended wave)"],
    "LATE_BULL_DISTRIBUTION": ["Wave 5 exhaustion", "truncated fifth", "ending diagonal", "ABC reversal onset"],
    "TRANSITION": ["structure unresolved — insufficient confirmed pivots to prefer one hypothesis"],
}


def classify_cycle_bucket(macro7: dict, cycle_current: dict) -> dict:
    phase = macro7["cycle"]["phase"]
    drawdown = cycle_current.get("drawdown")
    days_since_ath = cycle_current.get("days_since_ath")
    if phase == "BEAR" and drawdown is not None and drawdown <= -0.55:
        bucket = "DEEP_BEAR_BOTTOM_SEARCH"
    elif phase == "BEAR":
        bucket = "LATE_BEAR"
    elif phase == "BULL" and days_since_ath is not None and days_since_ath < 180:
        bucket = "EARLY_BULL"
    elif phase == "BULL":
        bucket = "MID_BULL"
    elif phase in ("DISTRIBUTION", "LATE_BULL"):
        bucket = "LATE_BULL_DISTRIBUTION"
    else:
        bucket = "TRANSITION"
    return {"bucket": bucket, "phase": phase, "drawdown": drawdown, "days_since_ath": days_since_ath, "provenance": ["macro7.cycle.phase", "cycle_history.current.drawdown", "cycle_history.current.days_since_ath"]}


def elliott_cycle_context(macro7: dict, cycle_current: dict) -> dict:
    bucket_info = classify_cycle_bucket(macro7, cycle_current)
    bucket = bucket_info["bucket"]
    conventional = _CONVENTIONAL_HYPOTHESES[bucket]
    primary_name = (macro7["elliott"]["primary"].get("name") or "").lower()
    alt_name = ((macro7["elliott"]["alternatives"] or [{}])[0].get("name") or "").lower()
    keywords = {
        "DEEP_BEAR_BOTTOM_SEARCH": ("abc", "correction", "recovery", "c-wave", "c wave"),
        "LATE_BEAR": ("abc", "correction", "c-wave", "c wave"),
        "EARLY_BULL": ("wave 1", "wave 2", "impulse"),
        "MID_BULL": ("wave 3", "impulse"),
        "LATE_BULL_DISTRIBUTION": ("wave 5", "exhaustion", "diagonal", "reversal"),
        "TRANSITION": (),
    }[bucket]
    consistent = any(kw in primary_name or kw in alt_name for kw in keywords) if keywords else True
    return {
        "cycle_bucket": bucket,
        "cycle_context": bucket_info,
        "conventionally_relevant_hypotheses": conventional,
        "engine_primary": macro7["elliott"]["primary"].get("name"),
        "engine_alternative": (macro7["elliott"]["alternatives"] or [{}])[0].get("name"),
        "consistency": "CONSISTENT" if consistent else "CONFLICT",
        "note": ("Engine's actual Elliott hypothesis is consistent with what this cycle phase conventionally suggests."
                  if consistent else
                  "Price structure (Elliott primary/alternative) does NOT match the conventional expectation for this cycle phase — flagged as CONFLICT, not overridden."),
        "known_limitation": "FullHistoryElliottEngine only distinguishes wave-4/recovery vs ABC/C hypotheses; it cannot yet resolve Wave 1/2/3 vs Wave 5 structures. No new Elliott rule was added to work around this.",
    }
