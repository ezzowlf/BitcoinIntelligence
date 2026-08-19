from __future__ import annotations

import json
from pathlib import Path


def load_snapshot(path: str | Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def research_dashboard_rows(report: dict, diagnostics: dict) -> dict[str, list[dict]]:
    horizons = []
    for item in report.get("screening", []):
        if item.get("model") != "logistic":
            continue
        cell = next((row for row in item["validation"]["coverage_curve"] if row["coverage"] == 0.01), None)
        if cell:
            horizons.append({"Horizon": f"{item['horizon_seconds']}s", "Precision": cell["precision"],
                             "Net EV": cell["net_ev"], "Signals": cell["signals"]})
    ablations = [{"Feature set": row["label"], "Validation precision": row["validation"]["precision"],
                  "Walk-forward precision": row["walk_forward_combined"]["precision"],
                  "Walk-forward Net EV": row["walk_forward_combined"]["net_ev"]}
                 for row in diagnostics.get("ablation_walk_forward", [])]
    return {"horizons": horizons, "coverage": next((item["validation"]["coverage_curve"] for item in report.get("screening", [])
                                                     if item.get("model") == "logistic" and item.get("horizon_seconds") == 300), []),
            "ablations": ablations, "regimes": diagnostics.get("by_regime", []),
            "time_of_day": diagnostics.get("by_utc_hour", [])}


def render_panel(path: str | Path, research_path: str | Path | None = None,
                 diagnostics_path: str | Path | None = None) -> None:
    """Render a DTO-only panel inside the existing Bitcoin Intelligence UI."""
    import streamlit as st

    snapshot = load_snapshot(path)
    st.markdown("## WAVERUN SHORT TERM")
    if snapshot is None:
        st.warning("WAVERUN: OFFLINE — kein LIVE-Snapshot vorhanden. Start: scripts\\waverun_live.py")
        return
    st.caption(f"MODE: {snapshot.get('mode', 'UNKNOWN')} · EXECUTION: {snapshot.get('execution', 'DISABLED')} · DATA AGE: {snapshot.get('data_age_seconds', '—')}s")
    state = snapshot.get("state", "NEUTRAL")
    st.metric("CURRENT STATE", state)
    rows = []
    for item in snapshot.get("forecasts", []):
        seconds = int(item["horizon_seconds"])
        label = f"{seconds}s" if seconds < 60 else f"{seconds // 60}m"
        rows.append({"Horizon": label, "UP": f"{item['p_up']:.1%}", "DOWN": f"{item['p_down']:.1%}", "Expected Move": f"{item['expected_move']:+.3%}", "Confidence": f"{item['confidence']:.1%}", "Quality": item["quality"]})
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    feeds = snapshot.get("feeds", {})
    if feeds:
        st.json(feeds, expanded=False)
    research = load_snapshot(research_path) if research_path else None
    diagnostics = load_snapshot(diagnostics_path) if diagnostics_path else None
    if research and diagnostics:
        rows = research_dashboard_rows(research, diagnostics)
        with st.expander("WAVERUN ADVANCED RESEARCH", expanded=False):
            st.caption("RESEARCH_ONLY · FINAL HOLDOUT LOCKED · EXECUTION DISABLED")
            horizon_tab, coverage_tab, feature_tab, regime_tab, time_tab = st.tabs(
                ["Horizons", "Precision/Coverage", "Feature Value", "Regime", "Time of Day"]
            )
            horizon_tab.dataframe(rows["horizons"], width="stretch", hide_index=True)
            coverage_tab.dataframe(rows["coverage"], width="stretch", hide_index=True)
            feature_tab.dataframe(rows["ablations"], width="stretch", hide_index=True)
            regime_tab.dataframe(rows["regimes"], width="stretch", hide_index=True)
            time_tab.dataframe(rows["time_of_day"], width="stretch", hide_index=True)
