from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.analyzer import analyze
from bitcoin_cycle_analyzer.similarity import evidence_label
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.seasonality.statistics import monthly_heatmap
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider

st.set_page_config(page_title="Bitcoin Cycle Analyzer", layout="wide")
st.title("Bitcoin Cycle Analyzer")
config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
store = OHLCVStore(Path(__file__).resolve().parents[1] / config["data"]["database"])
canonical = store.load_canonical("1d")
frame = canonical[["open", "high", "low", "close", "volume"]] if not canonical.empty else store.load("1d")
uploaded = st.sidebar.file_uploader("Optional: OHLCV CSV", type="csv")
if uploaded:
    frame = pd.read_csv(uploaded, parse_dates=["timestamp"]).set_index("timestamp")
if frame.empty:
    st.info("Noch keine 1D-Daten vorhanden. Lade eine CSV mit timestamp/open/high/low/close/volume hoch oder führe das Update-Skript aus.")
    st.stop()
result = analyze(frame, config)
external_store = ExternalMetricStore(Path(__file__).resolve().parents[1] / config["data"]["external_database"])
feeds = {"onchain_provider": StoreOnChainProvider(external_store),
         "funding": external_store.load("funding_rate_8h"),
         "open_interest": external_store.load("open_interest_usd"),
         "macro": {metric: external_store.load(metric) for metric in ("fed_funds","us_2y","us_10y","dxy","cpi","core_cpi","pce","nonfarm_payrolls","unemployment","gdp","fed_balance_sheet","m2","nasdaq","sp500","gold","oil")},
         "etf": external_store.load("etf_net_flow_usd")}
intelligence = analyze_intelligence(frame, config, feeds=feeds)
provider = canonical.provider.iloc[-1] if not canonical.empty and "provider" in canonical else "uploaded/local"
last_update = canonical.import_timestamp.iloc[-1] if not canonical.empty and "import_timestamp" in canonical else "unknown"
st.sidebar.metric("Data provider", provider)
st.sidebar.metric("Last data timestamp", str(frame.index[-1]))
st.sidebar.caption(f"Last data update: {last_update}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("BTC", f"${result['price']:,.0f}")
c2.metric("Cycle", intelligence["cycle"]["primary_regime"])
c3.metric("Long-Term Value", f"{result['score'].total:.0f}/100")
c4.metric("Entry Timing", intelligence["entry_timing"])
c5.metric("Evidence 2.2", f"{intelligence['evidence_2_2']['score']:.1f}/100")
st.metric("Drawdown Risk", f"{intelligence['drawdown_risk']['score']:.1f}/100 ({intelligence['drawdown_risk']['label']})")
st.caption(f"Confluence: {intelligence['confluence']['level']} | Independent groups: {intelligence['confluence']['independent_groups']}/8")
st.caption(result["score"].classification)
st.warning("Der Opportunity Score ist ein Analyse-Score, keine kalibrierte Eintrittswahrscheinlichkeit.")
st.subheader("Value / Confirmation / Risk")
st.write(result["states"])
tabs = st.tabs(["OVERVIEW", "CYCLE", "TECHNICAL", "ON-CHAIN", "DERIVATIVES", "ETF FLOWS", "MACRO", "SEASONALITY", "HISTORICAL", "NEWS", "BACKTEST", "DATA HEALTH"])
with tabs[0]:
    st.subheader("Bitcoin Market State Matrix")
    st.dataframe(pd.Series(intelligence["dimensions"], name="value"))
    st.subheader("Independent Confluence")
    st.json(intelligence["confluence"])
    st.subheader("Main Drivers and State Changes")
    st.json(intelligence["explainability"])
    st.bar_chart(pd.Series(result["score"].components))
with tabs[1]:
    st.json(intelligence["cycle"])
with tabs[2]:
    data = result["data"]
    fig = go.Figure(go.Candlestick(x=data.index, open=data.open, high=data.high, low=data.low, close=data.close))
    for zone in result["confluence_zones"][:5]:
        fig.add_hrect(y0=zone["low"], y1=zone["high"], opacity=.15, line_width=0)
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("Elliott scenarios")
    st.dataframe(pd.DataFrame(result["elliott_scenarios"]))
with tabs[3]:
    st.json(intelligence["modules"]["onchain"])
with tabs[4]:
    st.json(intelligence["modules"]["derivatives"])
with tabs[5]:
    st.json(intelligence["modules"]["etf"])
with tabs[6]:
    st.subheader("Macro State")
    st.json(intelligence["modules"]["macro"].get("state", {}))
    st.dataframe(pd.DataFrame(intelligence["modules"]["macro"].get("metrics", {})).T)
with tabs[7]:
    heatmap = monthly_heatmap(frame)
    heatmap_fig = go.Figure(data=go.Heatmap(z=heatmap.values, x=[str(x) for x in heatmap.columns], y=[str(x) for x in heatmap.index], colorscale="RdYlGn", zmid=0))
    st.plotly_chart(heatmap_fig, use_container_width=True)
    st.json(intelligence["modules"]["seasonality"])
with tabs[8]:
    st.dataframe(result["similar_cases"])
    sample_n = result["forward_summary_365d"].get("count", 0)
    st.caption(f"Historical sample size: n={sample_n} – {evidence_label(sample_n)}")
    if sample_n:
        positive = result["forward_summary_365d"]["positive"]
        st.write(f"{positive} von {sample_n} ähnlichen Situationen waren nach 365 Tagen positiv ({positive/sample_n:.0%}).")
    st.json(result["forward_summary_365d"])
with tabs[9]:
    st.json(intelligence["modules"]["news"])
with tabs[10]:
    report_path = Path(__file__).resolve().parents[1] / "data" / "reports" / "real_validation.json"
    if report_path.exists():
        import json
        validation = json.loads(report_path.read_text(encoding="utf-8"))
        summary = pd.DataFrame({threshold: {"signals": value["signal_count"], "365d median": value.get("365d", {}).get("median"), "365d positive rate": value.get("365d", {}).get("positive_rate"), "worst drawdown": value["drawdown"]["worst"]} for threshold, value in validation["thresholds"].items()}).T
        st.dataframe(summary)
    else:
        st.info("Noch kein echter Validierungsbericht vorhanden.")
with tabs[11]:
    st.dataframe(pd.DataFrame(intelligence["data_status"]).T)
    st.subheader("External source coverage")
    coverage = external_store.coverage()
    st.dataframe(coverage if not coverage.empty else pd.DataFrame([{"status": "UNAVAILABLE", "note": "Run scripts/update_external_data.py"}]))
    health_path = Path(__file__).resolve().parents[1] / "data" / "reports" / "external_data_health.json"
    if health_path.exists():
        import json
        st.json(json.loads(health_path.read_text(encoding="utf-8")))
    quality_path = Path(__file__).resolve().parents[1] / "data" / "reports" / "data_quality.json"
    if quality_path.exists():
        import json
        st.json(json.loads(quality_path.read_text(encoding="utf-8")))
