"""Canonical Streamlit WAVERUN live cockpit."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from bitcoin_cycle_analyzer.short_term.product import (
    EXECUTION,
    HYPOTHESIS_SHA256,
    PaperLedger,
    alert_transition,
    performance_summary,
    price_frame,
    runtime_state,
)

CSS = """
<style>
:root{--bg:#060a11;--card:#0d1521;--line:#223149;--text:#e7eef8;--muted:#8190a7;--green:#27d39b;--yellow:#f4bb55;--red:#ff6272;--blue:#4fa8ff}
.stApp{background:var(--bg);color:var(--text)}.block-container{max-width:1800px;padding:.5rem 1rem 2rem}
header[data-testid=stHeader],div[data-testid=stToolbar],.stDeployButton{display:none!important}
.mode{background:#49131b;color:#ffd7dc;text-align:center;font-weight:800;letter-spacing:.12em;padding:.36rem;border:1px solid #8d2937}
.top{display:grid;grid-template-columns:1.35fr repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:.45rem 0}.top>div,.card{background:var(--card);padding:.65rem .8rem}.label{font-size:.65rem;color:var(--muted);letter-spacing:.1em}.value{font-size:1.12rem;font-weight:750}.price{font-size:2rem;font-weight:800}.green{color:var(--green)}.yellow{color:var(--yellow)}.red{color:var(--red)}
.decision-card{border:1px solid var(--line);border-left:5px solid var(--yellow);background:var(--card);padding:.8rem 1rem}.decision-main{font-size:2.1rem;font-weight:850}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.55rem;margin:.55rem 0}.card{border:1px solid var(--line);min-height:110px}.row{display:flex;justify-content:space-between;border-top:1px solid #18243a;padding:.25rem 0;font-size:.78rem}.pill{display:inline-block;border:1px solid var(--line);padding:.14rem .38rem;margin:.1rem;border-radius:12px;font-size:.68rem}.health{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:.3rem}.small{font-size:.75rem;color:var(--muted)}
div[data-testid=stMetric]{background:var(--card);border:1px solid var(--line);padding:.5rem}.stButton button{min-height:44px;background:#152238;border:1px solid #324663}.stTabs [data-baseweb=tab-list]{gap:.25rem}.stTabs [data-baseweb=tab]{height:2.5rem}
@media(max-width:900px){.top{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr 1fr}.price{font-size:1.6rem}.decision-main{font-size:1.55rem}}
@media(max-width:560px){.block-container{padding:.35rem}.top,.grid{grid-template-columns:1fr}.top>div{padding:.45rem}.card{min-height:auto}.decision-main{font-size:1.35rem}}
</style>
"""


def _authenticate(st) -> bool:
    """Environment-only password gate; local trusted mode is explicit."""
    if os.environ.get("WAVERUN_LOCAL_TRUSTED", "false").lower() == "true":
        return True
    expected = os.environ.get("WAVERUN_DASHBOARD_PASSWORD_SHA256")
    if not expected:
        st.error("Dashboard locked: configure WAVERUN_DASHBOARD_PASSWORD_SHA256.")
        return False
    authenticated_at = st.session_state.get("waverun_authenticated_at", 0.0)
    if time.time() - authenticated_at < 8 * 3600:
        return True
    with st.form("waverun_login"):
        password = st.text_input("WAVERUN password", type="password")
        submitted = st.form_submit_button("Secure login")
    if submitted:
        actual = hashlib.sha256(password.encode()).hexdigest()
        if hmac.compare_digest(actual, expected):
            st.session_state["waverun_authenticated_at"] = time.time()
            st.rerun()
        else:
            st.error("Login failed.")
    return False


def _status_color(status: str) -> str:
    return "green" if status in {"LIVE", "ONLINE", "CONNECTED", "AVAILABLE", "RUNNING"} else "yellow" if status in {"STALE", "DELAYED", "PROVISIONAL"} else "red"


def _fmt(value: object, fallback: str = "—") -> str:
    return fallback if value is None else str(value)


def _decision(state: dict) -> tuple[str, str, list[str], list[str]]:
    row = state["latest_decision"]
    direction = row.get("direction_bias", "NO TRADE")
    final = row.get("final_decision", "BLOCKED")
    if final == "BLOCKED":
        direction = "NO TRADE" if direction not in {"LONG", "SHORT"} else direction
    reasons = []
    risks = list(row.get("contradictions", []))
    for signal in row.get("signals", []):
        if signal.get("available"):
            reasons.append(f"{signal.get('group')}: {signal.get('direction')} — {signal.get('explanation')}")
    return direction, final, reasons[:5], risks[:5]


def _render_chart(st, state: dict) -> None:
    timeframe = st.segmented_control("TIMEFRAME", ["1m", "3m", "5m", "15m", "1h"], default="1m")
    overlays = st.multiselect("OVERLAYS", ["VWAP", "SIGNAL MARKERS", "SWING HIGH/LOW", "FVG", "SUPPLY/DEMAND", "LIQUIDITY"], default=["SIGNAL MARKERS"])
    frame = price_frame(state["ticks"], timeframe or "1m")
    if frame.empty:
        st.info("Live chart is warming up from persisted Vantage ticks.")
        return
    figure = go.Figure(go.Candlestick(x=frame.index, open=frame.open, high=frame.high, low=frame.low, close=frame.close, name="BTCUSD"))
    if "VWAP" in overlays:
        figure.add_trace(go.Scatter(x=frame.index, y=frame.close.expanding().mean(), name="Research VWAP proxy", line={"color": "#f4bb55"}))
    if "SIGNAL MARKERS" in overlays:
        for candidate in state["candidates"][-30:]:
            figure.add_vline(x=pd.Timestamp(candidate["timestamp"]).timestamp() * 1000, line_color="#ff6272" if candidate["accepted"] else "#8190a7", opacity=.55)
    unavailable = set(overlays) & {"FVG", "SUPPLY/DEMAND", "LIQUIDITY", "SWING HIGH/LOW"}
    if unavailable:
        st.caption("RESEARCH ZONE overlays not plotted: no causal live contract currently supplies " + ", ".join(sorted(unavailable)) + ".")
    figure.update_layout(height=480, margin={"l": 10, "r": 10, "t": 20, "b": 10}, template="plotly_dark", paper_bgcolor="#0d1521", plot_bgcolor="#0d1521", xaxis_rangeslider_visible=False, legend={"orientation": "h"})
    st.plotly_chart(figure, width="stretch", config={"displaylogo": False, "scrollZoom": True})


def _render_paper(st, ledger: PaperLedger, state: dict) -> None:
    tick = state["latest_tick"]
    ledger.update(tick)
    note = st.text_input("ADD NOTE", placeholder="MACD looked strong, FVG, news …")
    left, right = st.columns(2)
    if left.button("MARK PAPER LONG", width="stretch", disabled=not bool(tick)):
        st.session_state["paper_id"] = ledger.open("LONG", note, state); st.rerun()
    if right.button("MARK PAPER SHORT", width="stretch", disabled=not bool(tick)):
        st.session_state["paper_id"] = ledger.open("SHORT", note, state); st.rerun()
    rows = ledger.rows()
    opens = [row for row in rows if row["status"] == "OPEN"]
    for row in opens:
        pnl = ledger.live_pnl(row, tick)
        elapsed = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(row["timestamp"])).total_seconds()
        st.markdown(f"### PAPER {row['direction']} · #{row['id']}")
        metrics = st.columns(5)
        metrics[0].metric("ENTRY", f"${row['entry']:,.2f}")
        metrics[1].metric("CURRENT PNL", "—" if pnl is None else f"${pnl:+,.2f}")
        metrics[2].metric("MFE", f"${row['mfe']:,.2f}")
        metrics[3].metric("MAE", f"${row['mae']:,.2f}")
        metrics[4].metric("TIME ACTIVE", f"{elapsed:.0f}s")
        if st.button(f"MANUAL EXIT #{row['id']}"):
            ledger.close(row["id"], tick); st.rerun()
    if rows:
        display = pd.DataFrame(rows).drop(columns=["features_json"], errors="ignore")
        st.dataframe(display, width="stretch", hide_index=True)
        st.download_button("EXPORT MANUAL HISTORY CSV", ledger.csv_bytes(), "waverun_manual_history.csv", "text/csv", width="stretch")
    else:
        st.caption("No manual paper positions yet.")


def render_cockpit(root: Path) -> None:
    import streamlit as st

    if not st.session_state.get("_waverun_live_fragment"):
        @st.fragment(run_every=0.75)
        def live_fragment() -> None:
            st.session_state["_waverun_live_fragment"] = True
            try:
                render_cockpit(root)
            finally:
                st.session_state["_waverun_live_fragment"] = False

        live_fragment()
        return
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("<div class='mode'>RESEARCH / SHADOW MODE · NO REAL TRADING</div>", unsafe_allow_html=True)
    if not _authenticate(st):
        st.stop()
    state = runtime_state(root)
    tick, validation = state["latest_tick"], state["validation"]
    health = validation.get("source_health", {}).get("feeds", {})
    vantage = validation.get("source_health", {}).get("vantage", "OFFLINE")
    bid, ask, spread = tick.get("bid"), tick.get("ask"), tick.get("spread")
    live = state["live_state"]
    boxes = [("WAVERUN · BTCUSD", f"<span class='{_status_color(live)}'>{live}</span>"),
             ("VANTAGE BID", "—" if bid is None else f"${bid:,.2f}"),
             ("VANTAGE ASK", "—" if ask is None else f"${ask:,.2f}"),
             ("SPREAD", "—" if spread is None else f"${spread:.2f}"),
             ("MARKET AGE", "—" if state['age_seconds'] is None else f"{state['age_seconds']:.2f}s"),
             ("SERVER UTC", state["server_time"][11:19])]
    st.markdown("<div class='top'>" + "".join(f"<div><div class='label'>{a}</div><div class='value'>{b}</div></div>" for a,b in boxes) + "</div>", unsafe_allow_html=True)
    source_items = [("MT5", vantage), ("BINANCE SPOT", health.get("spot", {}).get("state", "OFFLINE")), ("BINANCE FUTURES", health.get("futures", {}).get("state", "OFFLINE")), ("L2", health.get("spot", {}).get("state", "OFFLINE")), ("FORWARD VALIDATOR", validation.get("recorder_health", "OFFLINE"))]
    st.markdown(" ".join(f"<span class='pill'><i class='health' style='background:var(--{_status_color(v)})'></i>{k}: {v}</span>" for k,v in source_items), unsafe_allow_html=True)
    direction, final, reasons, risks = _decision(state)
    latest_candidate = state["candidates"][-1] if state["candidates"] else None
    latest_outcome_ids = {row["candidate_id"] for row in state["outcomes"]}
    alert_state = "SHADOW SIGNAL" if latest_candidate and latest_candidate.get("accepted") and latest_candidate["candidate_id"] not in latest_outcome_ids else final
    st.markdown(f"<div class='decision-card'><div class='label'>MAIN DECISION</div><div class='decision-main'>{direction} — {final}</div><div class='small'>Research interpretation only. No approved execution state exists.</div></div>", unsafe_allow_html=True)
    tabs = st.tabs(["LIVE COCKPIT", "FORWARD VALIDATION", "RESEARCH HISTORY", "MANUAL PAPER", "MANUAL PERFORMANCE", "SOURCE HEALTH"])
    with tabs[0]:
        _render_chart(st, state)
        decision = state["latest_decision"]
        momentum = decision.get("momentum_pressure_state") or {}
        long_score, short_score = decision.get("long_pressure_score", 0), decision.get("short_pressure_score", 0)
        spot = next((s for s in decision.get("signals", []) if s.get("name") == "spot_flow_10s"), {})
        futures = next((s for s in decision.get("signals", []) if s.get("name") == "futures_flow_10s"), {})
        cards = [
          ("PRESSURE SCORE", [("LONG", f"{long_score:.0f}"), ("SHORT", f"{short_score:.0f}")]),
          ("MOMENTUM", [("PRICE", _fmt(momentum.get("price_response_efficiency"), "WARMING UP")), ("EXPANSION", _fmt(momentum.get("range_expansion"), "UNAVAILABLE")), ("FLOW", f"{momentum.get('flow_pressure', 0):.1f}")]),
          ("ORDER FLOW", [("SPOT", spot.get("direction", "UNAVAILABLE")), ("FUTURES", futures.get("direction", "UNAVAILABLE")), ("AGREEMENT", "CONFIRMED" if spot.get("direction") == futures.get("direction") and spot else "DIVERGENT/NEUTRAL")]),
          ("L2", [("L10 IMBALANCE", _fmt(momentum.get("l2_imbalance"), "UNAVAILABLE")), ("ABSORPTION", "UNAVAILABLE"), ("MICROPRICE", "UNAVAILABLE")]),
        ]
        st.markdown("<div class='grid'>" + "".join("<div class='card'><div class='label'>"+title+"</div>"+"".join(f"<div class='row'><span>{a}</span><b>{b}</b></div>" for a,b in rows)+"</div>" for title,rows in cards) + "</div>", unsafe_allow_html=True)
        why, risk = st.columns(2)
        with why:
            st.markdown("### WHY?")
            for item in reasons: st.markdown(f"✓ {item}")
        with risk:
            st.markdown("### RISKS")
            if risks:
                for item in risks: st.warning(item)
            else: st.caption("No current contradiction recorded.")
    with tabs[1]:
        st.error("PROVISIONAL — NOT VERIFIED")
        metrics = st.columns(5)
        metrics[0].metric("PROGRESS", validation.get("progress_to_100", "0/100"))
        metrics[1].metric("ACCEPTED", validation.get("accepted_signals", 0))
        metrics[2].metric("RESOLVED", validation.get("resolved_signals", 0))
        metrics[3].metric("VETO BLOCKED", validation.get("veto_blocked_signals", 0))
        metrics[4].metric("$100/5m WINS", validation.get("successes_100_5m", 0))
        st.markdown(f"**FAST SHORT SETUP**  \nOriginal V5.3 condition: live evaluated  \n10s Spot-pressure veto: `<= 0.15022509`  \nResearch target: **$100 / 5 min**  \nDiscovery evidence: **69.05%**  \nForward OOS: **{validation.get('successes_100_5m',0)}/{validation.get('resolved_signals',0)}**  \nHypothesis: `{HYPOTHESIS_SHA256}`")
    with tabs[2]:
        rows = []
        outcomes = {row["candidate_id"]: row for row in state["outcomes"]}
        for candidate in reversed(state["candidates"]):
            outcome = outcomes.get(candidate["candidate_id"], {})
            rows.append({"timestamp": candidate["timestamp"], "direction": "SHORT", "entry": candidate.get("vantage_bid"), "veto": "PASS" if candidate["accepted"] else "BLOCK", "outcome": outcome.get("target_hits", {}).get("100"), "MFE": outcome.get("mfe"), "MAE": outcome.get("mae"), "time_to_green": outcome.get("time_to_first_positive_s"), "time_to_100": outcome.get("target_times_s", {}).get("100")})
        st.dataframe(rows, width="stretch", hide_index=True)
    with tabs[3]:
        _render_paper(st, PaperLedger(root / "database/waverun_product.db"), state)
    with tabs[4]:
        ledger = PaperLedger(root / "database/waverun_product.db")
        summary = performance_summary(ledger.rows(), state["outcomes"])
        st.caption("USER PAPER TRADES vs WAVERUN SHADOW SIGNALS · research only")
        for direction in ("LONG", "SHORT"):
            st.subheader(direction)
            columns = st.columns(2)
            for column, label in zip(columns, ("USER PAPER TRADES", "WAVERUN SHADOW SIGNALS")):
                item = summary["paper" if label.startswith("USER") else "shadow"][direction]
                with column:
                    st.markdown(f"**{label}**")
                    st.write({"trades": item["trades"], "win rate": item["win_rate"], "net-positive rate": item["net_positive_rate"], "$25/$50/$75/$100 reach": item["targets"], "average MFE": item["average_mfe"], "average MAE": item["average_mae"], "median time to green": item["median_time_to_green"], "median time to $100": item["median_time_to_100"], "average hold time": item["average_hold_time"]})
        st.subheader("OVERLAP")
        st.dataframe([{"category": key, "trades": value} for key, value in summary["overlap"].items()], width="stretch", hide_index=True)
        st.download_button("EXPORT PAPER + SHADOW SUMMARY CSV", pd.DataFrame([{"side": side, "paper_trades": summary["paper"][side]["trades"], "paper_win_rate": summary["paper"][side]["win_rate"], "shadow_trades": summary["shadow"][side]["trades"], "shadow_win_rate": summary["shadow"][side]["win_rate"]} for side in ("LONG", "SHORT")]).to_csv(index=False).encode(), "waverun_performance.csv", "text/csv", width="stretch")
    with tabs[5]:
        st.subheader("SOURCE HEALTH")
        st.json({"Vantage": vantage, "Binance Spot": health.get("spot", {}), "Binance Futures": health.get("futures", {}), "Forward Validator": {k: validation.get(k) for k in ("recorder_health", "updated_at", "progress_to_100")}}, expanded=True)
        counts = {"Vantage ticks": len(state["ticks"]), "Signals": len(state["candidates"]), "Outcomes": len(state["outcomes"])}
        st.write(counts)
        st.caption(f"Hypothesis hash {HYPOTHESIS_SHA256} · execution {EXECUTION}")
    audio = st.toggle("Audio alerts", value=False, key="audio_alerts")
    test_audio = st.button("TEST AUDIO", key="test_audio")
    transition = f"{direction}:{alert_state}"
    previous = st.session_state.get("waverun_transition")
    if test_audio or alert_transition(previous, alert_state, audio):
        st.components.v1.html("""<script>
        const C=window.AudioContext||window.webkitAudioContext; if(C){const c=new C(),o=c.createOscillator(),g=c.createGain();o.frequency.value=740;g.gain.value=.06;o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.16)}
        </script>""", height=0)
    st.session_state["waverun_transition"] = transition
