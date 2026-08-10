"""UI-only state model for the dashboard.

Deliberately separate from ENGINE STATE (analyze_intelligence output) and
DECISION STATE (decision_intelligence.build_decision_state output). Nothing
in this module computes analysis — it only describes what the *chart/view*
currently looks like, so Streamlit's session_state doesn't turn into an
undifferentiated dict of unrelated concerns.

Four state categories, kept explicitly distinct per the brief:
  ENGINE STATE       -> analyze_intelligence(...) output (untouched, upstream)
  DECISION STATE      -> decision_intelligence.build_decision_state(...) output (upstream)
  CHART VIEW STATE    -> this module: timeframe, layers, scale, preset, mode
  EXPLANATION STATE   -> decision_intelligence.build_explanation_facts(...) output (upstream)
"""
from __future__ import annotations

CHART_VIEW_STATE_KEY = "chart_view_state"

LAYER_PRESETS = {
    "CLEAN": [],
    "SWING": ["200D/200W", "Swing Zones", "Signals"],
    "MACRO": ["Macro Zones", "200D/200W", "Elliott", "Historical Entries"],
    "RESEARCH": ["Macro Zones", "Swing Zones", "200D/200W", "Bollinger", "Fib", "Elliott", "Historical Entries", "Events", "Signals"],
}

VIEW_MODES = ("SIMPLE", "RESEARCH")


def default_chart_view_state(preset: str = "SWING") -> dict:
    return {"timeframe": "ALL", "scale": None, "preset": preset, "layers": LAYER_PRESETS.get(preset, []), "mode": "RESEARCH"}


def get_chart_view_state(session_state: dict, query_params) -> dict:
    if CHART_VIEW_STATE_KEY not in session_state:
        preset = query_params.get("preset", "SWING")
        mode = query_params.get("mode", "RESEARCH")
        state = default_chart_view_state(preset)
        state["mode"] = mode if mode in VIEW_MODES else "RESEARCH"
        state["timeframe"] = query_params.get("tf", "ALL")
        session_state[CHART_VIEW_STATE_KEY] = state
    return session_state[CHART_VIEW_STATE_KEY]
