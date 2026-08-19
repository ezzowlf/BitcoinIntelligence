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


def render_panel(path: str | Path) -> None:
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
