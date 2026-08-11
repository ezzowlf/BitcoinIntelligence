"""Event Intelligence (Master-Auftrag 3).

Sits on top of the existing, pre-existing `PointInTimeEventDatabase`
(event_evidence.py) exactly the way `decision_intelligence/` sits on top of
CONTROL 3 / MACRO 7 — a pure consumer, no parallel event store, no second
reaction engine. This module only adds:

  1. a causality-language guard (never claim "X caused Y")
  2. expected-vs-observed comparison (never assume good news -> price up)
  3. a lightweight event-candidate dedup helper (cluster near-duplicate
     headlines about the same real-world event before they would be
     inserted — the append() hash already prevents exact duplicates, this
     catches near-duplicates from different sources)
  4. an EVENT_CONTEXT evidence family for the Decision Engine, wired as
     INFORMATIVE / SECONDARY ONLY — it never enters the STRONG_BUY/BUY
     quality gates in decision_engine.py (see event_evidence_family() docstring)
"""
from __future__ import annotations
import difflib
import pandas as pd

from .event_evidence import CAUSALITY_LEVELS, EXPECTED_DIRECTION


def classify_causality(n_plausible_contributors: int, has_strong_temporal_link: bool, has_confirmed_mechanism: bool) -> dict:
    """Never returns a certainty claim. `has_confirmed_mechanism` should only be
    True when there is a well-documented, direct transmission mechanism (e.g. an
    exchange halting BTC withdrawals during its own event) — not inferred from
    price behaviour alone."""
    if has_confirmed_mechanism and n_plausible_contributors <= 1:
        level = "STRONG_EVIDENCE"
    elif n_plausible_contributors >= 3:
        level = "MULTIPLE_PLAUSIBLE_CONTRIBUTORS"
    elif n_plausible_contributors == 1 and has_strong_temporal_link:
        level = "PLAUSIBLE_CONTRIBUTOR"
    elif has_strong_temporal_link:
        level = "TEMPORAL_ASSOCIATION"
    else:
        level = "UNKNOWN"
    assert level in CAUSALITY_LEVELS
    return {"causality_level": level, "note": "Correlation/co-occurrence in time is not proof of causation. This label describes evidential strength, not certainty."}


def expected_vs_observed(expected_direction: str | None, observed_return_24h: float | None) -> dict:
    """Explicit mismatch detector — the brief's core anti-naive-sentiment guard."""
    if expected_direction is None or observed_return_24h is None:
        return {"comparison": "UNAVAILABLE", "note": "Expected direction or observed reaction missing."}
    if expected_direction not in EXPECTED_DIRECTION:
        raise ValueError(f"expected_direction must be one of {EXPECTED_DIRECTION}")
    observed_direction = "BULLISH" if observed_return_24h > 0.005 else "BEARISH" if observed_return_24h < -0.005 else "NEUTRAL"
    if expected_direction == "UNCERTAIN":
        match = "N/A"
    else:
        match = "MATCH" if expected_direction == observed_direction else "MISMATCH"
    return {
        "comparison": match,
        "expected_direction": expected_direction,
        "observed_direction": observed_direction,
        "observed_return_24h": observed_return_24h,
        "note": (
            "Expected direction did not match the observed 24h reaction — a reminder that a single news event rarely determines price on its own."
            if match == "MISMATCH" else
            "Observed reaction matched the expected direction — still only one data point, not a rule."
        ),
    }


def dedupe_candidates(candidates: list[dict], similarity_threshold: float = 0.72, time_window_hours: float = 6.0) -> list[list[dict]]:
    """Clusters candidate source items (each with `headline` and `event_time`)
    that likely describe the same real-world event, so only one canonical
    BitcoinEvent is created per cluster. Pure text+time heuristic — no LLM
    call, deterministic and testable."""
    remaining = list(candidates)
    clusters: list[list[dict]] = []
    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]
        seed_time = pd.Timestamp(seed["event_time"])
        still_remaining = []
        for cand in remaining:
            close_in_time = abs((pd.Timestamp(cand["event_time"]) - seed_time).total_seconds()) <= time_window_hours * 3600
            similar_text = difflib.SequenceMatcher(None, seed["headline"].lower(), cand["headline"].lower()).ratio() >= similarity_threshold
            if close_in_time and similar_text:
                cluster.append(cand)
            else:
                still_remaining.append(cand)
        remaining = still_remaining
        clusters.append(cluster)
    return clusters


def event_evidence_family(event_rows: pd.DataFrame) -> dict:
    """EVENT_CONTEXT evidence family — INFORMATIVE / SECONDARY ONLY.

    Deliberately NOT wired into `decision_intelligence.evidence.assess_evidence_families`
    or into `independent_agreement()` in this pass. Reasons, per the brief's own Phase 12/13:
      - only 11 events exist in the database right now (4 halvings + 7 pre-existing) —
        far too few for a meaningful ablation study (Phase 13 explicitly requires
        comparing WITH vs WITHOUT before giving Event Context real decision weight)
      - the brief is explicit: "News darf nicht dominieren" and "zuerst Event Context
        nur INFORMATIVE / SECONDARY EVIDENCE"

    This function exists so the *shape* of an EVENT_CONTEXT family is ready (matches
    the same {family, direction, strength, facts, provenance} contract as the other
    7 families in decision_intelligence/evidence.py) but it is surfaced to the UI as
    read-only context, not fed into any BUY/STRONG_BUY gate. Wiring it into the gates
    is the natural next step, gated behind an actual ablation study — not done here.
    """
    if event_rows is None or event_rows.empty:
        return {"family": "EVENT_CONTEXT", "direction": "UNAVAILABLE", "strength": "LOW", "facts": ["No historical events available at this point in time"], "provenance": ["event_evidence.PointInTimeEventDatabase"], "decision_weight": "NONE — informative only, not ablation-tested"}
    recent = event_rows[event_rows.importance.isin(["HIGH", "CRITICAL"])] if "importance" in event_rows else event_rows.iloc[0:0]
    facts = [f"{len(event_rows)} events on record as of this point in time", f"{len(recent)} of HIGH/CRITICAL importance"]
    return {"family": "EVENT_CONTEXT", "direction": "NEUTRAL", "strength": "LOW", "facts": facts, "provenance": ["event_evidence.PointInTimeEventDatabase"], "decision_weight": "NONE — informative only, not ablation-tested"}
