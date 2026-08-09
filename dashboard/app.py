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
from bitcoin_cycle_analyzer.master.replay import build_master_historical_signal_book

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
replay_enabled=st.sidebar.toggle("Historical PIT Replay",value=False)
replay_date=st.sidebar.date_input("Replay date",value=frame.index[-1].date(),min_value=frame.index[0].date(),max_value=frame.index[-1].date(),disabled=not replay_enabled)
analysis_cutoff=pd.Timestamp(replay_date,tz="UTC") if replay_enabled else frame.index[-1]
result = analyze(frame, config,as_of=analysis_cutoff)
external_store = ExternalMetricStore(Path(__file__).resolve().parents[1] / config["data"]["external_database"])
feeds = {"onchain_provider": StoreOnChainProvider(external_store),
         "four_hour": store.load("4h"),
         "funding": external_store.load("funding_rate_8h"),
         "open_interest": external_store.load("open_interest_usd"),
         "macro": {metric: external_store.load(metric) for metric in ("fed_funds","us_2y","us_10y","dxy","cpi","core_cpi","pce","nonfarm_payrolls","unemployment","gdp","fed_balance_sheet","m2","nasdaq","sp500","gold","oil")},
         "etf": external_store.load("etf_net_flow_usd")}
intelligence = analyze_intelligence(frame, config, as_of=analysis_cutoff,feeds=feeds)
decision=intelligence["decision"]
master=intelligence["master"];master_state=master["state"];master_decision=master["decision"]
provider = canonical.provider.iloc[-1] if not canonical.empty and "provider" in canonical else "uploaded/local"
last_update = canonical.import_timestamp.iloc[-1] if not canonical.empty and "import_timestamp" in canonical else "unknown"
st.sidebar.metric("Data provider", provider)
st.sidebar.metric("Last data timestamp", str(frame.index[-1]))
st.sidebar.caption(f"Last data update: {last_update}")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("BTC", f"${result['price']:,.0f}")
c2.metric("Regime", intelligence["precision"]["regime"]["current"])
c3.metric("Long-Term Value", f"{intelligence['precision']['value']['score']:.1f}/100")
c4.metric("Entry Timing", intelligence["precision"]["timing"]["state"])
c5.metric("Evidence 2.2", f"{intelligence['evidence_2_2']['score']:.1f}/100")
st.metric("30D Drawdown Risk", f"{intelligence['precision']['risk']['horizons']['30d']:.1f}/100 ({intelligence['precision']['risk']['tail_state']})")
st.caption(f"Confluence: {intelligence['confluence']['level']} | Independent groups: {intelligence['confluence']['independent_groups']}/8")
st.caption(f"Analysis mode: {'HISTORICAL_PIT_REPLAY' if replay_enabled else intelligence['precision']['analysis_mode']}")
st.header("₿ BITCOIN MASTER")
st.subheader("WHAT SHOULD I DO?")
d1,d2,d3,d4=st.columns(4);d1.metric("LONG TERM",master_decision["long_term_action"]);d2.metric("NEW ENTRY",master_decision["new_entry_action"]);d3.metric("EXISTING POSITION",master_decision["existing_position_action"]);d4.metric("RISK",master_decision["risk_action"])
st.metric("PRODUCTION SIGNAL",master_decision["production_signal"])
ca,cb=st.columns(2);ca.metric("BUY CANDIDATE",f"{master_state['buy_completion']}%",help="Completion, not probability");cb.metric("SELL CANDIDATE",f"{master_state['sell_completion']}%",help="Completion, not probability")
st.write("POSITIVE",master_decision["positive_drivers"]);st.write("NEGATIVE",master_decision["negative_drivers"]);st.write("UNCERTAIN / MISSING",master_decision["uncertain_drivers"])
st.write("WHAT ARE WE WAITING FOR?",master_decision["waiting_for"]);st.write("UPGRADE CONDITIONS",master_decision["upgrade_conditions"]);st.write("DOWNGRADE CONDITIONS",master_decision["downgrade_conditions"])
st.caption(f"Master confidence: {master_decision['confidence']} | Primary: {master['primary_analysis_model']} | Control: {master['control_model']} | {master_decision['model_disagreement']['state']} | Execution: DISABLED")
historical_quality=intelligence["historical_entry_quality"]
st.subheader("HISTORICAL ENTRY QUALITY")
h1,h2,h3,h4=st.columns(4);h1.metric("QUALITY",historical_quality["state"],f"{historical_quality.get('score')} / 100 (not probability)");h2.metric("ARCHETYPE",historical_quality["entry_archetype"]);h3.metric("ENTRY TIMING",master_state["timing"]);h4.metric("MASTER NEW ENTRY",master_decision["new_entry_action"])
st.caption(f"Based on {historical_quality['sample_size']} independent historical best-entry episodes. LIVE_RESEARCH_CONTEXT, not calibrated probability.")
factor_labels={"DEEP_DRAWDOWN":"Deep Drawdown","MAJOR_HISTORICAL_SUPPORT":"Major Support","HIGH_VALUE":"High Value","BELOW_200D":"Below 200D","BELOW_200W":"Below 200W","DAILY_RSI_WEAK":"Daily RSI Weak","WEEKLY_RSI_WEAK":"Weekly RSI Weak","CAPITULATION_STRESS":"Capitulation"}
st.dataframe(pd.DataFrame([{"factor":label,"status":"UNAVAILABLE" if historical_quality["factor_status"].get(key) is None else "YES" if historical_quality["factor_status"].get(key) else "NO"} for key,label in factor_labels.items()]),hide_index=True)
v1,v2,v3,v4=st.columns(4);v1.metric("Current Drawdown",f"{historical_quality['current_drawdown']:.1%}");v2.metric("Price vs 200D",f"{historical_quality['price_vs_200d_pct']:.1%}" if historical_quality['price_vs_200d_pct'] is not None else "UNAVAILABLE");v3.metric("Price vs 200W",f"{historical_quality['price_vs_200w_pct']:.1%}" if historical_quality['price_vs_200w_pct'] is not None else "UNAVAILABLE");v4.metric("Weekly RSI",master_state["weekly_rsi"])
st.dataframe(pd.DataFrame(historical_quality["closest_historical_entries"])[["date","archetype","similarity","historical_return_365d","historical_MAE_365d"]] if historical_quality["closest_historical_entries"] else pd.DataFrame())
st.caption("Historical result - not a forecast.")
if historical_quality.get("mae_context",{}).get("warning"):st.warning(f"HISTORICAL DOWNSIDE CONTEXT: similar entries had median {historical_quality['mae_context']['median']:.1%} and worst {historical_quality['mae_context']['worst']:.1%} further drawdown. High entry quality is not low risk.")
st.subheader("MARKET MAP")
map1,map2,map3=st.columns(3);map1.write({"MAJOR RESISTANCE":master_state["nearest_resistance"]});map2.metric("CURRENT BTC",f"${master_state['btc_price']:,.2f}");map3.write({"MAJOR SUPPORT":master_state["nearest_support"]})
st.write("BUY ZONES",master_state["buy_zones"]);st.write("DISTRIBUTION / SELL ZONES",master_state["sell_zones"])
with st.expander("MASTER FACTOR REGISTRY"):
    st.dataframe(pd.DataFrame(master_state["factor_registry"]));st.json({"evidence":master_state["evidence"],"confluence":master_state["confluence"],"data_quality":master_state["data_quality"],"uncertainty":master_state["uncertainty"]})
rare=intelligence["rare_signal"];advanced=intelligence["advanced"]
st.subheader("RARE SIGNAL CHALLENGER")
r1,r2,r3=st.columns(3);r1.metric("PRODUCTION",rare["level_a"]["signal"]);r2.metric("BUY CANDIDATE",f"{rare['level_b']['buy_completion']}%");r3.metric("SELL CANDIDATE",f"{rare['level_b']['sell_completion']}%")
st.caption(f"Buy: {rare['buy_state']} | Sell: {rare['sell']['state']} | Distribution: {rare['sell']['distribution']} | RARE_SIGNAL_CHALLENGER_1 | Execution DISABLED")
dd=advanced["drawdown"];mom=advanced["momentum"]
with st.expander("Historical zones, drawdown, RSI and Bollinger",expanded=True):
    a,b,c,d=st.columns(4);a.metric("Current drawdown",f"{dd['current_drawdown']:.1%}");b.metric("Drawdown percentile",f"{dd['historical_severity_percentile']:.1f}");c.metric("Weekly RSI",mom['weekly']['rsi']);d.metric("Monthly RSI",mom['monthly']['rsi'])
    st.write({"drawdown_state":dd["state"],"recovery":dd["recovery_from_major_low"],"rsi_365d":mom["rsi_365d"],"bollinger":{"daily":mom["daily"]["bollinger"]["state"],"weekly":mom["weekly"]["bollinger"]["state"],"monthly":mom["monthly"]["bollinger"]["state"]}})
st.caption(result["score"].classification)
st.warning("Der Opportunity Score ist ein Analyse-Score, keine kalibrierte Eintrittswahrscheinlichkeit.")
st.subheader("Value / Confirmation / Risk")
st.write(result["states"])
tabs = st.tabs(["OVERVIEW", "CYCLE", "TECHNICAL", "ON-CHAIN", "DERIVATIVES", "ETF FLOWS", "MACRO", "SEASONALITY", "HISTORICAL", "NEWS", "BACKTEST", "DATA HEALTH", "SIGNAL BOOK", "HISTORICAL LEVELS", "BEST HISTORICAL ENTRIES"])
with tabs[0]:
    st.subheader("Precision Engine 2.3")
    st.json({key:intelligence["precision"].get(key) for key in ("market_state","system_conclusion","value","regime","timing","risk","uncertainty","data_health")})
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
with tabs[12]:
    signal_book,master_errors=build_master_historical_signal_book(frame.loc[:analysis_cutoff]);st.caption("MASTER HISTORICAL RESEARCH - never mixed with forward validation")
    st.dataframe(signal_book[[c for c in ("date","master_signal","price","regime","return_30d","return_90d","return_365d","MAE_90d","MFE_90d") if c in signal_book]])
    if not signal_book.empty:st.bar_chart(signal_book.assign(year=pd.to_datetime(signal_book.date).dt.year).groupby(["year","master_signal"]).size().unstack(fill_value=0))
    st.subheader("ERROR TAXONOMY / REJECTED SELLS");st.dataframe(master_errors)
with tabs[13]:
    st.caption("PIT-formed historical zones; later touches create new versions")
    st.dataframe(pd.DataFrame(advanced["historical_zones"]))
with tabs[14]:
    st.caption("RESEARCH_ONLY - future prices label outcomes; production logic is unchanged")
    root=Path(__file__).resolve().parents[1];episode_path=root/"BITCOIN_ENTRY_EPISODES.csv";factor_path=root/"BITCOIN_ENTRY_FACTOR_MATRIX.csv"
    if not episode_path.exists():
        st.info("Run scripts/run_best_entry_study.py to generate the historical explorer.")
    else:
        episodes=pd.read_csv(episode_path,parse_dates=["date","start","end"]);factors=pd.read_csv(factor_path)
        st.subheader("Ranked independent entry episodes")
        st.dataframe(episodes[[c for c in ("rank","date","entry_price","return_365d","return_730d","MAE_365d","entry_archetype","recognized_master") if c in episodes]])
        chart=go.Figure(go.Candlestick(x=frame.index,open=frame.open,high=frame.high,low=frame.low,close=frame.close,name="BTC"))
        chart.add_trace(go.Scatter(x=episodes.date,y=episodes.entry_price,mode="markers",name="Top historical entry",marker={"size":10,"color":"green","symbol":"triangle-up"}))
        st.plotly_chart(chart,use_container_width=True)
        labels={f"#{int(row['rank'])} {pd.Timestamp(row['date']).date()}":int(i) for i,row in episodes.iterrows()};choices=st.multiselect("Compare two episodes",list(labels),default=list(labels)[:2],max_selections=2)
        if choices:
            detail_cols=[c for c in ("date","entry_price","drawdown","distance_200d","distance_200w","rsi_daily","rsi_weekly","rsi_monthly","bollinger_daily_position","bollinger_weekly_position","bollinger_monthly_position","major_support","zone_strength","zone_distance","fib_confluence","regime","cycle","capitulation_state","recovery_state","mvrv","funding","open_interest","recognized_2_3","recognized_2_5","recognized_master") if c in episodes]
            st.dataframe(episodes.loc[[labels[x] for x in choices],detail_cols].set_index("date").T.astype(str))
        st.subheader("Research factor ranking");st.dataframe(factors)
