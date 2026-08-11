from pathlib import Path
import sys
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from bitcoin_cycle_analyzer.ai import BitcoinAIRouter
from bitcoin_cycle_analyzer.runtime import env_values
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.live import MT5MarketDataProvider
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase
from bitcoin_cycle_analyzer.fusion_live import Fusion6ForwardLedger
from bitcoin_cycle_analyzer.indicator_state import build_decision_state_v1,build_indicator_state_v1,rule_registry,write_json,PINE_MQL_CAPABILITY_MATRIX
from bitcoin_cycle_analyzer.decision_intelligence import build_decision_state as build_decision_intelligence,build_explanation_facts,RULE_REGISTRY as DECISION_RULE_REGISTRY
from bitcoin_cycle_analyzer.ui_state import LAYER_PRESETS,get_chart_view_state
from bitcoin_cycle_analyzer.glossary import GLOSSARY
from bitcoin_cycle_analyzer.event_intelligence import classify_causality,expected_vs_observed,event_evidence_family

ROOT=Path(__file__).resolve().parents[1]
st.set_page_config(page_title="BTC Intelligence Terminal",page_icon="₿",layout="wide",initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--bg:#070b12;--panel:#0d1420;--panel2:#111a28;--line:#223047;--text:#e6edf7;--muted:#7f8ea3;--green:#26c281;--amber:#f0b44d;--red:#ee5a67;--blue:#4da3ff}
.stApp{background:var(--bg);color:var(--text)}header[data-testid="stHeader"],div[data-testid="stToolbar"],.stDeployButton{display:none!important}.block-container{max-width:1900px;padding:1rem 1.35rem 2rem}
h1,h2,h3{letter-spacing:.02em}.terminal-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:.15rem 0 .8rem;margin-bottom:.65rem}.ticker{font-size:1rem;color:var(--muted);font-weight:700}.price{font-size:2.35rem;font-weight:750;line-height:1.05}.micro{font-size:.75rem;color:var(--muted);margin-top:.25rem}.badge{display:inline-block;padding:.2rem .5rem;border:1px solid var(--line);border-radius:3px;font-size:.7rem;margin-left:.35rem}.live{color:var(--green);border-color:#1d634a}.engine{display:inline-flex;gap:.45rem;align-items:center;margin-left:.7rem}.dot{height:7px;width:7px;border-radius:50%;background:var(--green);display:inline-block}
.decision{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);background:var(--panel);margin:.4rem 0 .6rem}.decision>div{padding:.55rem .8rem;border-right:1px solid var(--line)}.decision>div:last-child{border:0}.decision label,.kpi label{display:block;color:var(--muted);font-size:.66rem;letter-spacing:.12em}.decision strong{font-size:.95rem}.viewbar{border-left:3px solid var(--amber);background:#101722;padding:.5rem .8rem;font-size:.92rem;margin-bottom:.7rem}.viewbar b{color:var(--amber)}
.sidepanel{background:var(--panel);border:1px solid var(--line);padding:.7rem;margin-bottom:.55rem}.sidepanel h4{font-size:.67rem;color:var(--muted);letter-spacing:.12em;margin:0 0 .35rem}.bigstate{font-size:1.2rem;font-weight:750}.score{color:var(--amber)}.positive{color:var(--green)}.negative{color:var(--red)}.neutral{color:var(--muted)}.levelrow{display:flex;justify-content:space-between;border-top:1px solid #182438;padding:.28rem 0;font-size:.76rem}.compactlist{font-size:.74rem;line-height:1.55;color:#c3cfdd}.compactlist span{display:block}
.bottomcard{background:var(--panel);border-top:2px solid var(--line);padding:.55rem .7rem;min-height:132px}.bottomcard h4{font-size:.67rem;letter-spacing:.12em;color:var(--muted);margin:0 0 .35rem}.bottomgrid{display:grid;grid-template-columns:1fr 1fr;gap:.25rem .7rem;font-size:.75rem}.bottomgrid b{text-align:right}.stTabs [data-baseweb="tab-list"]{gap:.15rem;border-bottom:1px solid var(--line)}.stTabs [data-baseweb="tab"]{height:2.2rem;font-size:.72rem;background:transparent}.stButton button{border-radius:3px;border:1px solid var(--line);background:var(--panel2)}
div[data-baseweb="select"]>div{background:var(--panel)!important;border-color:var(--line)!important;color:var(--text)!important;min-height:2.35rem}div[data-baseweb="select"] input{color:var(--text)!important}[data-baseweb="tag"],[data-tag]{background:#1b2a3e!important;color:#cbd5e1!important;border-color:#30435e!important}[role="group"][aria-label="Selected values"]{background:var(--panel)!important}div[data-testid="stButtonGroup"] button{background:var(--panel)!important;border-color:var(--line)!important;color:#aebbd0!important}div[data-testid="stButtonGroup"] button[aria-pressed="true"]{background:#19304a!important;color:#f4f8ff!important;border-color:#356da2!important}
div[data-testid="stMetric"]{background:transparent;border:0;padding:0}div[data-testid="stMetricLabel"]{font-size:.7rem;color:var(--muted)}
.simplecard{background:var(--panel);border:1px solid var(--line);padding:1rem 1.1rem;margin-bottom:.6rem}.simplecard .bigstate{font-size:1.6rem}.simplerow{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.6rem;margin-top:.6rem}.simplerow>div{background:var(--panel2);border:1px solid var(--line);padding:.5rem .65rem}.simplerow label{display:block;color:var(--muted);font-size:.65rem;letter-spacing:.1em;margin-bottom:.2rem}
div[data-testid="stButtonGroup"] button{min-height:44px}div[role="radiogroup"] label{min-height:44px}
@media(max-width:700px){.block-container{padding:.65rem}.terminal-head{display:block}.price{font-size:1.85rem}.engines{margin-top:.5rem}.decision{grid-template-columns:1fr 1fr}.decision>div:nth-child(2){border-right:0}.decision>div{border-bottom:1px solid var(--line)}.decision label{font-size:.55rem;overflow-wrap:anywhere}.decision strong{font-size:.82rem}.viewbar{overflow-wrap:anywhere}.bottomcard{min-height:auto}.simplerow{grid-template-columns:1fr 1fr}}
</style>""",unsafe_allow_html=True)

config=load_config(ROOT/"config.yaml");store=OHLCVStore(ROOT/config["data"]["database"]);canonical=store.load_canonical("1d");frame=canonical[["open","high","low","close","volume"]] if not canonical.empty else store.load("1d")
if frame.empty:st.error("Keine BTC-Daten verfügbar.");st.stop()
external=ExternalMetricStore(ROOT/config["data"]["external_database"]);mt5=MT5MarketDataProvider(values=env_values(ROOT/".env"));mh=mt5.connect();tick=mt5.tick() if mh.status=="ONLINE" else {"status":"UNAVAILABLE","reason":mh.reason};h4=mt5.confirmed_candles("4h",1000) if mh.status=="ONLINE" else store.load("4h");d1=mt5.confirmed_candles("1d",700) if mh.status=="ONLINE" else frame.iloc[0:0];w1=mt5.confirmed_candles("1w",260) if mh.status=="ONLINE" else frame.iloc[0:0];m1=mt5.confirmed_candles("1mo",180) if mh.status=="ONLINE" else frame.iloc[0:0];div=MT5MarketDataProvider.divergence(tick.get("mid"),float(frame.close.iloc[-1]));usable=mh.status=="ONLINE" and tick.get("freshness") in {"LIVE","DELAYED"} and not d1.empty and div.get("status")!="CRITICAL"
if usable:frame=pd.concat([frame.loc[frame.index<d1.index[0]],d1]).sort_index();frame=frame[~frame.index.duplicated(keep="last")]
live={"status":"ONLINE" if usable else mh.status,"health":mh.__dict__,"tick":tick,"divergence":div,"last_confirmed_h4":None if mh.status!="ONLINE" or h4.empty else h4.index[-1],"last_confirmed_d1":None if mh.status!="ONLINE" or d1.empty else d1.index[-1],"last_confirmed_w1":None if mh.status!="ONLINE" or w1.empty else w1.index[-1],"last_confirmed_1m":None if mh.status!="ONLINE" or m1.empty else m1.index[-1],"timing_confirmation":"ENABLED" if usable else "BLOCKED","provenance":mt5.provenance()};mt5.close()
@st.cache_data(show_spinner=False)
def discovery(data):return HistoricalPatternDiscoveryEngine().discover(data)
feeds={"onchain_provider":StoreOnChainProvider(external),"four_hour":h4,"funding":external.load("funding_rate_8h"),"open_interest":external.load("open_interest_usd"),"etf":external.load("etf_net_flow_usd"),"macro":{},"live_market":live,"price_provider":"MT5 confirmed D1 + BITSTAMP historical" if usable else "BITSTAMP historical dataset","project_root":ROOT,"fusion_discovery":discovery(frame)}
state=analyze_intelligence(frame,config,feeds=feeds);m3=state["master"];ms=m3["state"];md=m3["decision"];m5=state["master5_challenger"];fusion=state["fusion6"];macro7=state["macro7"];hq=state["historical_entry_quality"];cycles=state["elliott_cycle"]["cycle_history"];elliott=state["elliott_cycle"]["elliott"];mom=state["advanced"]["momentum"]
event_db=PointInTimeEventDatabase(ROOT/"database"/"historical_event_evidence.db");event_health=event_db.health();event_rows=event_db.as_of(pd.Timestamp.now(tz="UTC"));fusion_live=Fusion6ForwardLedger(ROOT/"database"/"fusion6_live.db",json.loads((ROOT/"frozen"/"fusion_6_research_frozen.json").read_text(encoding="utf-8"))["forward_start"]);fusion_health=fusion_live.health()
live_price=tick.get("mid") if usable else ms["btc_price"];spread=tick.get("spread");day_change=float(frame.close.iloc[-1]/frame.close.iloc[-2]-1) if len(frame)>1 else 0
status_class="live" if usable else "";tick_label=str(tick.get("timestamp","UNAVAILABLE"))[11:19];confirmed=str(live.get("last_confirmed_h4") or "UNAVAILABLE")[:16]
st.markdown(f"""<div class='terminal-head'><div><div class='ticker'>₿ BTCUSD <span class='badge {status_class}'>{'MT5 LIVE' if usable else str(mh.status)}</span></div><div class='price'>${live_price:,.2f}</div><div class='micro'><span class='{'positive' if day_change>=0 else 'negative'}'>{day_change:+.2%} D1</span> · Bid {'—' if tick.get('bid') is None else f'${tick["bid"]:,.2f}'} · Ask {'—' if tick.get('ask') is None else f'${tick["ask"]:,.2f}'} · Spread {'—' if spread is None else f'${spread:.2f}'} · Tick {tick_label} UTC · Age {tick.get('age_seconds','—')}s · Confirmed H4 {confirmed} · D1 {str(live.get('last_confirmed_d1') or '—')[:16]} · W1 {str(live.get('last_confirmed_w1') or '—')[:16]}</div></div><div class='engines'><span class='engine'><i class='dot'></i>CONTROL 3</span><span class='engine'><i class='dot'></i>SPECIALIST 5</span><span class='engine'><i class='dot' style='background:var(--amber)'></i>FUSION 6 RESEARCH</span></div></div>""",unsafe_allow_html=True)
macro_e=macro7["elliott"];active_scenario=next((x for x in macro7["scenarios"] if x["status"]=="ACTIVE"),macro7["scenarios"][0])
timing_state="CONFIRMED" if md.get("state")=="CONFIRMED" else "CONFIRMING" if md.get("waiting_for") and len(md.get("waiting_for"))<=1 else "EARLY" if md.get("waiting_for") else "WAIT"
decision_state=build_decision_state_v1(state,macro7,live_price,active_scenario,timing_state)
decision_intel=build_decision_intelligence(state,macro7,frame,live_price)
decision_explanation=build_explanation_facts(decision_intel)
risk_state=decision_state["risk"]
st.markdown(f"""<div class='decision'><div><label>MACRO</label><strong class='positive'>{decision_state['macro']}</strong></div><div><label>LONG SWING</label><strong class='score'>{decision_state['long_swing']}</strong></div><div><label>TIMING</label><strong>{decision_state['timing']}</strong></div><div><label>RISK</label><strong class='{"negative" if risk_state=="HIGH" else "score" if risk_state=="CAUTION" else "positive"}'>{risk_state}</strong></div><div><label>CURRENT SCENARIO</label><strong>{decision_state['current_scenario']['name']}</strong></div></div><div class='viewbar'><b>MACRO VIEW</b> · {decision_state['why'][0]} · {decision_state['why'][1]} · Long-Swing BUY bleibt ohne validierten Edge gesperrt.</div>""",unsafe_allow_html=True)
status_color={"ACTIVE":"var(--green)","WATCH":"var(--amber)","DORMANT":"var(--muted)","INVALIDATED":"var(--red)"}
scenario_chips="".join(f"<span class='badge' style='border-color:{status_color.get(s['status'],'var(--line)')};color:{status_color.get(s['status'],'var(--muted)')}'>{s['name']} · {s['status']}</span>" for s in macro7["scenarios"])
st.markdown(f"<div style='margin:-.35rem 0 .6rem;line-height:2.1'>{scenario_chips}</div>",unsafe_allow_html=True)

di=decision_intel;dz=di["active_zone"];dec_color={"STRONG_BUY":"var(--green)","BUY":"var(--green)","ACCUMULATE":"var(--amber)","WATCH":"var(--amber)","WAIT":"var(--muted)","REDUCE":"var(--red)","TAKE_PROFIT":"var(--amber)","HIGH_RISK":"var(--red)","SELL":"var(--red)","NO_EDGE":"var(--muted)"}.get(di["decision"],"var(--muted)")
zone_line="No active structural zone" if dz is None or dz.get("lower") is None else f"{dz['label']} · ${dz['lower']:,.0f} – ${dz['upper']:,.0f}"
qp=st.query_params;view_state=get_chart_view_state(st.session_state,qp)
mode_col,_=st.columns([1,4])
mode=mode_col.segmented_control("VIEW",["SIMPLE","RESEARCH"],default=view_state["mode"],label_visibility="collapsed")
view_state["mode"]=mode;qp["mode"]=mode
simple=mode=="SIMPLE"

if simple:
    missing_conf=[t["description"] for t in di["confirmation"]["triggers"].values() if not t["met"]]
    st.markdown(f"""<div class='simplecard'><div class='micro'>CURRENT VIEW</div><div class='bigstate' style='color:{dec_color}'>{di['decision']}</div><div class='simplerow'>
    <div><label>GOOD AREA</label><b>{zone_line}</b></div>
    <div><label>ENTRY</label><b>{di['entry_status'].replace('_',' ')}</b></div>
    <div><label>WAITING FOR</label><b>{missing_conf[0] if missing_conf else '—'}</b></div>
    <div><label>WRONG IF BELOW</label><b>{'—' if di['invalidation_level'] is None else f"${di['invalidation_level']:,.0f}"}</b></div>
    </div><div class='micro' style='margin-top:.6rem'><b>WHY?</b> {len(di['evidence_agreement']['supporting_families'])} positive factors, {len(di['evidence_agreement']['contradicting_families'])} against — {decision_explanation['conclusion']}</div></div>""",unsafe_allow_html=True)
    with st.expander("Explain the terms used above"):
        for term in ("Cycle","Invalidation","Confirmation","Reclaim"):
            st.markdown(f"**{term}** — {GLOSSARY.get(term,'')}")
    recent_events=event_rows[pd.to_datetime(event_rows.event_time,utc=True)>=pd.Timestamp.now(tz="UTC")-pd.Timedelta(days=90)] if not event_rows.empty else event_rows
    with st.expander(f"WHAT MATTERS FOR BITCOIN NOW ({len(recent_events)} recent events)"):
        if recent_events.empty:
            st.markdown("No sourced events on record in the last 90 days.")
        else:
            for _,ev in recent_events.sort_values("event_time",ascending=False).iterrows():
                st.markdown(f"**{ev.get('importance') or 'UNCLASSIFIED'}** — {ev.headline} ({str(ev.event_time)[:10]})")
        st.caption("IMPACT ON CURRENT DECISION: event context is informative only in this build — it does not change the decision above (see EVENT_CONTEXT evidence family, not yet weighted pending an ablation study).")
    layers=[];tf=st.segmented_control("TIMEFRAME",["1D","1W","1M","1Y","ALL"],default="ALL",label_visibility="collapsed");scale="LOG" if tf in {"ALL","1Y"} else "LIN"
else:
    preset_row=st.columns([1,1,1,1,3])
    for idx,pname in enumerate(LAYER_PRESETS):
        if preset_row[idx].button(pname,key=f"preset_{pname}",use_container_width=True):st.session_state["layers"]=LAYER_PRESETS[pname];qp["preset"]=pname
    if "layers" not in st.session_state:st.session_state["layers"]=LAYER_PRESETS.get(qp.get("preset","SWING"),LAYER_PRESETS["SWING"])
    controls=st.columns([1,2.15,.85]);tf=controls[0].segmented_control("TIMEFRAME",["4H","1D","1W","1M","1Y","ALL"],default=qp.get("tf","ALL"),label_visibility="collapsed");layers=controls[1].multiselect("LAYERS",["Macro Zones","Swing Zones","200D/200W","Bollinger","Fib","Elliott","Historical Entries","Events","Signals"],key="layers",label_visibility="collapsed");scale=controls[2].segmented_control("SCALE",["LOG","LIN"],default=qp.get("scale") or ("LOG" if tf in {"ALL","1Y"} else "LIN"),label_visibility="collapsed")
qp["tf"]=tf;qp["scale"]=scale

chart_frame=h4 if tf=="4H" and not h4.empty else frame.resample("W-MON").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1W" else frame.resample("ME").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1M" else frame.resample("YE").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1Y" else frame
visible=chart_frame if tf in {"ALL","1Y"} else chart_frame.tail(450 if tf in {"4H","1D"} else 220);fig=go.Figure(go.Candlestick(x=visible.index,open=visible.open,high=visible.high,low=visible.low,close=visible.close,increasing_line_color="#26c281",decreasing_line_color="#ee5a67",name="BTC"))
support=ms.get("nearest_support");resistance=ms.get("nearest_resistance")
# Decision Intelligence zone/invalidation/targets ALWAYS render — highest chart-layer priority, never gated behind a layer toggle.
if dz is not None and dz.get("lower") is not None:
    zone_fill={"STRONG_BUY_ZONE":"rgba(38,194,129,.18)","BUY_ZONE":"rgba(38,194,129,.12)","WATCH_ZONE":"rgba(240,180,77,.10)","TAKE_PROFIT_ZONE":"rgba(240,180,77,.10)","HIGH_RISK_ZONE":"rgba(238,90,103,.12)"}.get(dz["zone_type"],"rgba(240,180,77,.10)")
    fig.add_hrect(y0=dz["lower"],y1=dz["upper"],fillcolor=zone_fill,line_width=1.5,line_color=dec_color,annotation_text=f"{dz['zone_type'].replace('_',' ')} · {di['entry_status'].replace('_',' ')}",annotation_position="top left",annotation_font_color=dec_color)
if di.get("invalidation_level") is not None:
    fig.add_hline(y=di["invalidation_level"],line_color="#ee5a67",line_dash="dash",line_width=1.3,annotation_text=f"INVALIDATION ${di['invalidation_level']:,.0f}",annotation_position="bottom right")
for t in di.get("targets",[]):
    fig.add_hline(y=t["price"],line_color="#4da3ff",line_dash="dot",line_width=1,annotation_text=f"{t['id']} ${t['price']:,.0f}",annotation_position="top right")
if "200D/200W" in layers and tf!="4H":
    ma200=frame.close.rolling(200).mean().reindex(visible.index,method="ffill");ma200w=frame.close.rolling(1400).mean().reindex(visible.index,method="ffill");fig.add_trace(go.Scatter(x=visible.index,y=ma200,name="200D",line={"color":"#4da3ff","width":1.3}));fig.add_trace(go.Scatter(x=visible.index,y=ma200w,name="200W",line={"color":"#9b7bff","width":1.3}))
if "Bollinger" in layers:
    mid=visible.close.rolling(20).mean();std=visible.close.rolling(20).std();fig.add_trace(go.Scatter(x=visible.index,y=mid+2*std,name="BB+",line={"color":"#46566c","width":1,"dash":"dot"}));fig.add_trace(go.Scatter(x=visible.index,y=mid-2*std,name="BB-",line={"color":"#46566c","width":1,"dash":"dot"}))
if "Swing Zones" in layers:
    for z,color,name in ((ms["buy_zones"][0],"rgba(38,194,129,.13)","BUY ZONE 1"),(ms["buy_zones"][1],"rgba(38,194,129,.07)","BUY ZONE 2")):
        if z.get("status")=="AVAILABLE":fig.add_hrect(y0=z["low"],y1=z["high"],fillcolor=color,line_width=0,annotation_text=name,annotation_position="top left")
    if support:fig.add_hrect(y0=support["lower_bound"],y1=support["upper_bound"],fillcolor="rgba(77,163,255,.07)",line_width=0)
    if resistance:fig.add_hrect(y0=resistance["lower_bound"],y1=resistance["upper_bound"],fillcolor="rgba(238,90,103,.06)",line_width=0)
if "Macro Zones" in layers:
    for key,color in (("tactical_buy","rgba(77,163,255,.09)"),("macro_accumulation","rgba(38,194,129,.10)"),("deep_value","rgba(240,180,77,.08)"),("extreme_cycle","rgba(238,90,103,.07)")):
        z=macro7["zones"].get(key)
        if z:fig.add_hrect(y0=z["low"],y1=z["high"],fillcolor=color,line_width=0,annotation_text=key.replace("_"," ").upper(),annotation_position="top left")
if "Elliott" in layers:
    swings=pd.DataFrame(elliott["evidence"]["confirmed_swings"])
    if not swings.empty:fig.add_trace(go.Scatter(x=pd.to_datetime(swings.pivot_time),y=swings.price,mode="markers+text",text=[str(i+1) for i in range(len(swings))],textposition="top center",marker={"size":6,"color":"#f0b44d"},name="Confirmed swings"))
SIGNAL_STYLE={"STRONG_BUY_CANDIDATE":{"symbol":"triangle-up","color":"#26c281"},"HISTORICAL_EXTREME":{"symbol":"star","color":"#f0b44d"},"HIGH_RISK_DISTRIBUTION":{"symbol":"triangle-down","color":"#ee5a67"}}
if "Signals" in layers:
    path=ROOT/"data"/"reports"/"master5_signal_book.csv"
    if path.exists():
        sig=pd.read_csv(path,parse_dates=["timestamp"]);sig=sig[sig.signal.isin(SIGNAL_STYLE) & (sig.false_signal==False)]
        for kind,style in SIGNAL_STYLE.items():
            rows=sig[sig.signal==kind]
            if not rows.empty:fig.add_trace(go.Scatter(x=rows.timestamp,y=rows.price,mode="markers",marker={"size":10,"symbol":style["symbol"],"color":style["color"],"line":{"width":1,"color":"#070b12"}},name=kind.replace("_"," ").title()))
if "Events" in layers and not event_rows.empty:
    # Standard view (ALL/1Y): only HIGH/CRITICAL or HALVING to avoid marker flood. Shorter
    # timeframes show everything in range — at 11 events total this is still sparse.
    ev=event_rows if tf not in {"ALL","1Y"} else event_rows[event_rows.importance.isin(["HIGH","CRITICAL"]) | (event_rows.category=="HALVING")]
    ev_times=pd.to_datetime(ev.available_at,utc=True)
    ev_prices=frame.close.reindex(ev_times,method="ffill")
    if not ev.empty:fig.add_trace(go.Scatter(x=ev_times,y=ev_prices,mode="markers",text=ev.headline,customdata=ev.category,hovertemplate="%{customdata}<br>%{text}<extra></extra>",marker={"size":9,"symbol":"diamond-open","color":"#f0b44d","line":{"width":2}},name="Events"))
fig.add_hline(y=live_price,line_color="#f0b44d",line_width=1,annotation_text=f"LIVE ${live_price:,.0f}",annotation_position="top right")
fig.update_layout(height=620 if simple else 555,margin={"l":8,"r":8,"t":15,"b":8},paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0","size":10},dragmode="pan",newshape={"line":{"color":"#f0b44d","width":1.5}},xaxis={"rangeslider":{"visible":False},"gridcolor":"#142033","showspikes":True,"spikemode":"across","spikesnap":"cursor","spikecolor":"#4da3ff","spikethickness":1},yaxis={"side":"right","gridcolor":"#142033","tickformat":",.0f","type":"log" if scale=="LOG" else "linear","showspikes":True,"spikemode":"across","spikesnap":"cursor","spikecolor":"#4da3ff","spikethickness":1},legend={"orientation":"h","y":1.02,"x":0},hovermode="x unified")
st.plotly_chart(fig,width="stretch",config={"displaylogo":False,"scrollZoom":True,"displayModeBar":True,"modeBarButtonsToAdd":["v1hovermode","toggleSpikelines","drawline","drawopenpath","drawrect","drawcircle","eraseshape"],"modeBarButtonsToRemove":["lasso2d","select2d"]})
st.caption("Green/amber/red band = active decision zone · dashed red = invalidation · dotted blue = targets · your own drawings are independent annotations, not saved across sessions in this build")

if simple:
    st.stop()

with st.expander("WHY?"):
    st.markdown("**Supporting**  \n"+("\n".join(decision_explanation["why_positive"]) or "—"))
    st.markdown("**Contradicting / missing**  \n"+("\n".join(decision_explanation["why_not_buy"]) or "—"))
    if di["targets"]:st.markdown("**Targets**  \n"+"  \n".join(f"{t['id']}: ${t['price']:,.0f} — {t['why']}" for t in di["targets"]))
    st.caption(decision_explanation["role"]+" · rules: "+", ".join(r.split(":")[0] for r in decision_explanation["rule_ids"]))

zone=m5["buy"]["zone"] or {};zl=zone.get("low");zh=zone.get("high")
wait_labels={"no_confirmed_lower_low":"Kein neues bestätigtes tieferes Tief","structure_reclaim":"Struktur zurückerobern","h4_or_d1_confirmation":"H4/D1-Bestätigung"};waiting="".join(f"<span>○ {wait_labels.get(x,x)}</span>" for x in md["waiting_for"])
macro_primary=macro_e["primary"];macro_alt=(macro_e["alternatives"] or [{}])[0]
st.markdown(f"""<div class='simplerow' style='margin:.3rem 0 .8rem'>
<div class='sidepanel' style='margin:0'><h4>BITCOIN DECISION <span class='micro'>research synthesis</span></h4><div class='bigstate' style='color:{dec_color}'>{di['decision']}</div><div class='micro'>{decision_explanation['conclusion']}</div><div class='levelrow'><span>ZONE</span><b>{zone_line}</b></div><div class='levelrow'><span>CONFIDENCE</span><b>{di['decision_confidence']['label']} ({di['decision_confidence']['score']}/100)</b></div></div>
<div class='sidepanel' style='margin:0'><h4>BUY OPPORTUNITY</h4><div class='bigstate score'>{m5['buy']['quality']:.0f} / 100</div><div>{m5['buy']['state']} · {m5['buy']['zone_lifecycle']['state']}</div><div class='micro'>Historical setup quality · keine Wahrscheinlichkeit</div></div>
<div class='sidepanel' style='margin:0'><h4>SELL-OFF RISK</h4><div class='bigstate'>{m5['risk']['sell_off_risk']}</div><div class='micro'>{m5['risk']['distribution']} · {m5['risk']['existing_position_action']}</div></div>
<div class='sidepanel' style='margin:0'><h4>NEXT BUY ZONE</h4><div class='bigstate'>{'UNAVAILABLE' if zl is None else f'${zl:,.0f} – ${zh:,.0f}'}</div><div class='micro'>Distance {m5['buy']['zone_lifecycle']['distance_pct'] if m5['buy']['zone_lifecycle']['distance_pct'] is not None else '—'} %</div><div class='levelrow'><span>MAJOR SUPPORT</span><b>{'—' if not support else f'${support["upper_bound"]:,.0f}'}</b></div><div class='levelrow'><span>MAJOR RESISTANCE</span><b>{'—' if not resistance else f'${resistance["lower_bound"]:,.0f}'}</b></div></div>
<div class='sidepanel' style='margin:0'><h4>WAITING FOR</h4><div class='compactlist'>{waiting}</div></div>
<div class='sidepanel' style='margin:0'><h4>INTELLIGENCE</h4><div class='compactlist'><span><b>CYCLE</b> {fusion['regime']} · {cycles['current']['drawdown']:.1%} from ATH</span><span><b>ELLIOTT PRIMARY</b> {macro_primary.get('name','Unresolved')}</span><span><b>SCENARIO</b> {active_scenario['name']} · {active_scenario['status']}</span></div></div>
</div>""",unsafe_allow_html=True)

cycle=cycles["current"];closest=hq.get("closest_historical_entries",[]);rsi_d=mom["daily"]["rsi"];rsi_w=mom["weekly"]["rsi"];rsi_m=mom["monthly"]["rsi"];ma200=float(frame.close.rolling(200).mean().iloc[-1]);ma200w=float(frame.close.rolling(1400).mean().iloc[-1]);data_status=state["data_status"]
b1,b2,b3,b4=st.columns(4,gap="small")
with b1:st.markdown(f"<div class='bottomcard'><h4>CYCLE</h4><div class='bottomgrid'><span>REGIME</span><b>{fusion['regime']}</b><span>ELLIOTT</span><b>{elliott['primary']['name'].replace('Possible ','')[:20]}</b><span>DRAWDOWN</span><b>{cycle['drawdown']:.1%}</b><span>SINCE ATH</span><b>{cycle['days_since_ath']}d</b><span>SINCE HALVING</span><b>{cycles['days_since_halving']}d</b></div></div>",unsafe_allow_html=True)
with b2:st.markdown(f"<div class='bottomcard'><h4>HISTORICAL</h4><div class='bottomgrid'><span>ENTRY QUALITY</span><b>{hq['score']:.0f} / 100</b><span>STATE</span><b>{hq['state']}</b><span>ARCHETYPE</span><b>{m5['buy']['archetype'].replace('_',' ')}</b><span>CLOSEST</span><b>{' · '.join(str(pd.Timestamp(x['date']).year) for x in closest[:3]) or '—'}</b><span>ACTIVE PATTERNS</span><b>{len(fusion['active_historical_patterns'])}</b></div></div>",unsafe_allow_html=True)
with b3:st.markdown(f"<div class='bottomcard'><h4>MOMENTUM</h4><div class='bottomgrid'><span>RSI D</span><b>{rsi_d or '—'}</b><span>RSI W</span><b>{rsi_w or '—'}</b><span>RSI M</span><b>{rsi_m or '—'}</b><span>VS 200D</span><b>{live_price/ma200-1:+.1%}</b><span>VS 200W</span><b>{live_price/ma200w-1:+.1%}</b></div></div>",unsafe_allow_html=True)
with b4:st.markdown(f"<div class='bottomcard'><h4>DATA</h4><div class='bottomgrid'><span>MT5</span><b class='{'positive' if usable else 'negative'}'>{'LIVE' if usable else 'OFFLINE'}</b><span>ONCHAIN</span><b>{data_status['onchain']['status']}</b><span>DERIVATIVES</span><b>{data_status['derivatives']['status']}</b><span>MACRO</span><b>{data_status['macro']['status']}</b><span>NEWS</span><b>{data_status['news']['status']}</b></div></div>",unsafe_allow_html=True)

tabs=st.tabs(["CHART","CYCLES","HISTORY","EVENTS","RESEARCH","SYSTEM"])
with tabs[0]:
    st.subheader("Macro scenario map")
    scenario_rows=[{"Scenario":x["name"],"Status":x["status"],"Why this zone exists":x["price_zone"]["support"],"Zone":f"${x['price_zone']['low']:,.0f} – ${x['price_zone']['high']:,.0f}","Support":x["confidence_state"],"Activates if":" · ".join(x["activation_conditions"]),"Invalidated if":" · ".join(x["invalidation_conditions"]),"Historical context":" · ".join(x["historical_analogues"]) or "UNAVAILABLE","Elliott context":x["elliott_context"]} for x in macro7["scenarios"]]
    st.dataframe(pd.DataFrame(scenario_rows),hide_index=True)
    detail_name=st.selectbox("SCENARIO DETAILS",[s["name"] for s in macro7["scenarios"]])
    detail=next(s for s in macro7["scenarios"] if s["name"]==detail_name)
    dleft,dright=st.columns(2)
    dleft.markdown(f"""**WHY THIS SCENARIO EXISTS**  \n{detail['price_zone']['support']}  \n\n**ACTIVATES IF**  \n{' · '.join(detail['activation_conditions'])}  \n\n**INVALIDATED IF**  \n{' · '.join(detail['invalidation_conditions'])}""")
    dright.markdown(f"""**TARGET / PRICE REGION**  \n${detail['price_zone']['low']:,.0f} – ${detail['price_zone']['high']:,.0f}  \n\n**HISTORICAL ANALOGUES**  \n{' · '.join(detail['historical_analogues']) or 'UNAVAILABLE'}  \n\n**ELLIOTT CONTEXT**  \n{detail['elliott_context']}  \n\n**DRAWDOWN CONTEXT**  \n{detail['drawdown_context']:.1%}""" if isinstance(detail['drawdown_context'],float) else f"**DRAWDOWN CONTEXT**  \n{detail['drawdown_context']}")
    st.divider()
    z=macro7["zones"];zone_rows=[{"Horizon":name.replace("_"," ").title(),"Zone":"UNAVAILABLE" if zone is None else f"${zone['low']:,.0f} – ${zone['high']:,.0f}","Support":"UNAVAILABLE" if zone is None else zone["support"]} for name,zone in (("tactical",z["tactical_buy"]),("swing",z["swing_buy"]),("macro accumulation",z["macro_accumulation"]),("deep value",z["deep_value"]),("extreme cycle",z["extreme_cycle"]))];st.dataframe(pd.DataFrame(zone_rows),hide_index=True)
    st.subheader("Macro price map · 50k / 40k / 30k conditional context")
    level_rows=[]
    for target in (50000,40000,30000):
        closest_level=min(macro7["drawdown_ladder"]["levels"],key=lambda x:abs(x["price"]-target));level_rows.append({"BTC level":f"${target:,.0f}","ATH drawdown":f"{target/macro7['indicators']['ath']-1:.1%}","Distance to 200W":f"{target/macro7['indicators']['ma200w']-1:.1%}","Historical context":"Deep-cycle band" if target<macro7['indicators']['ma200w'] else "200W vicinity","Currently active":"NO","Scenario":"DORMANT — NOT AN ACTIVE TARGET · conditional context only","Nearest historical ladder":f"{closest_level['drawdown']:.0%}"})
    st.dataframe(pd.DataFrame(level_rows),hide_index=True);st.caption("These levels are conditional context, never a forecast · CONTROL 3 remains Champion · MACRO SWING 7 remains Research Challenger · Execution DISABLED")
with tabs[1]:
    cyc_tabs=st.tabs(["ELLIOTT","CYCLE LAB"])
    with cyc_tabs[1]:
        st.subheader("Historical Bitcoin cycle laboratory")
        view=st.segmented_control("CYCLE VIEW",["Full BTC History","Halving Cycles","ATH Drawdowns","Bottom Recoveries","Yearly Candles"],default="Full BTC History")
        halvings=[pd.Timestamp("2012-11-28",tz="UTC"),pd.Timestamp("2016-07-09",tz="UTC"),pd.Timestamp("2020-05-11",tz="UTC"),pd.Timestamp("2024-04-20",tz="UTC")]
        if view=="Yearly Candles":
            yearly=frame.resample("YE").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna();yf=go.Figure(go.Candlestick(x=yearly.index,open=yearly.open,high=yearly.high,low=yearly.low,close=yearly.close));yf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log");st.plotly_chart(yf,width="stretch")
            annual=yearly.assign(year=yearly.index.year,ret=yearly.close/yearly.open-1,max_drawdown=yearly.low/yearly.open-1)[["year","open","high","low","close","ret","max_drawdown"]].rename(columns={"ret":"Return","max_drawdown":"Max Drawdown"})
            st.dataframe(annual,hide_index=True)
        elif view=="Halving Cycles":
            cf=go.Figure();hn=cycles.get("halving_normalized",[])
            for i,cycle_item in enumerate(hn):
                pts=pd.DataFrame(cycle_item["points"]);is_current=i==len(hn)-1
                cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized,name=str(cycle_item["halving"])[:10]+(" · CURRENT" if is_current else ""),line={"width":3 if is_current else 1.4,"color":"#f0b44d" if is_current else None}))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Days from halving",yaxis_title="Halving price = 1.0");st.plotly_chart(cf,width="stretch");st.caption("Research context only. No mechanical four-year-cycle assumption. Current cycle highlighted, not extrapolated.")
        elif view=="ATH Drawdowns":
            cf=go.Figure()
            for item in cycles.get("ath_normalized",[]):
                pts=pd.DataFrame(item["points"]);cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized-1,name=f"Cycle {item['cycle']}"))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Days from ATH",yaxis_title="Drawdown");st.plotly_chart(cf,width="stretch")
        elif view=="Bottom Recoveries":
            cf=go.Figure()
            for item in cycles.get("bottom_recovery_normalized",[]):
                pts=pd.DataFrame(item["points"]);cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized,name=f"Cycle {item['cycle']}"))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Days from major low",yaxis_title="Low price = 1.0");st.plotly_chart(cf,width="stretch")
        else:
            cyclefig=go.Figure(go.Scatter(x=frame.index,y=frame.close,line={"color":"#4da3ff","width":1},name="BTC"))
            ath_running=frame.close.cummax();ath_points=frame[frame.close>=ath_running.shift(1).fillna(0)]
            cyclefig.add_trace(go.Scatter(x=ath_points.index,y=ath_points.close,mode="markers",marker={"size":5,"color":"#26c281"},name="New ATH"))
            for h in halvings:
                if h>=frame.index.min() and h<=frame.index.max():cyclefig.add_vline(x=h,line_color="#7f8ea3",line_dash="dot",annotation_text="HALVING",annotation_position="top")
            cycle_rows=cycles.get("cycles",[])
            if cycle_rows:latest_cycle=cycle_rows[-1];cyclefig.add_trace(go.Scatter(x=[pd.Timestamp(latest_cycle["major_low"])],y=[latest_cycle["trough_price"]],mode="markers",marker={"size":11,"color":"#ee5a67","symbol":"x"},name="Most recent major low"))
            cyclefig.add_trace(go.Scatter(x=[frame.index[-1]],y=[live_price],mode="markers+text",text=["NOW"],textposition="top center",marker={"size":9,"color":"#f0b44d"},name="Current drawdown path"))
            cyclefig.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log",legend={"orientation":"h","y":1.02,"x":0});st.plotly_chart(cyclefig,width="stretch",key="cycles_full_history")
            st.caption("New ATHs, halvings and the current cycle low are structural markers, not predictions of the next one.")
    with cyc_tabs[0]:
        st.subheader("Elliott · full BTC history · RESEARCH_ONLY / CONTEXT_ONLY — not a trading signal")
        degree_labels=["MACRO","PRIMARY","INTERMEDIATE"];degree_key={"MACRO":"MACRO_CYCLE","PRIMARY":"PRIMARY","INTERMEDIATE":"INTERMEDIATE"};degree_color={"MACRO":"#f0b44d","PRIMARY":"#4da3ff","INTERMEDIATE":"#9b7bff"}
        degrees=st.multiselect("DEGREES",degree_labels,default=["MACRO","PRIMARY"],label_visibility="collapsed")
        show_alt=st.toggle("Show Alternative count overlay",False)
        piv=pd.DataFrame(macro_e["macro_pivots"]);primary=macro_e["primary"];alt=(macro_e["alternatives"] or [{}])[0];ex=macro_e["explanation"]
        efig=go.Figure(go.Scatter(x=frame.index,y=frame.close,line={"color":"#33475f","width":1},name="BTC"))
        if "MACRO" in degrees and not piv.empty:
            efig.add_trace(go.Scatter(x=piv.timestamp,y=piv.price,mode="markers+text",text=piv.algorithmic_label,textposition="top center",marker={"size":9,"color":degree_color["MACRO"],"symbol":"diamond"},name="MACRO confirmed pivots"))
            last_piv=piv.iloc[-1];efig.add_trace(go.Scatter(x=[last_piv.timestamp,frame.index[-1]],y=[last_piv.price,live_price],mode="lines",line={"color":degree_color["MACRO"],"width":2,"dash":"dot"},name="Current wave · unconfirmed"))
        for key in ("PRIMARY","INTERMEDIATE"):
            if key in degrees:
                sw=pd.DataFrame(macro_e["hierarchy"][degree_key[key]]["evidence"]["confirmed_swings"])
                if not sw.empty:efig.add_trace(go.Scatter(x=pd.to_datetime(sw.pivot_time),y=sw.price,mode="markers",marker={"size":6,"color":degree_color[key]},name=f"{key} confirmed swings"))
        if primary.get("invalidation_level") is not None:efig.add_hline(y=primary["invalidation_level"],line_color="#ee5a67",line_dash="dash",annotation_text=f"INVALIDATES PRIMARY · ${primary['invalidation_level']:,.0f}",annotation_position="bottom right")
        if primary.get("confirmation_level") is not None:efig.add_hline(y=primary["confirmation_level"],line_color="#26c281",line_dash="dash",annotation_text=f"CONFIRMS NEXT PHASE · ${primary['confirmation_level']:,.0f}",annotation_position="top right")
        if show_alt:
            if alt.get("invalidation_level") is not None:efig.add_hline(y=alt["invalidation_level"],line_color="#9b7bff",line_dash="dot",annotation_text=f"ALT INVALIDATION · ${alt['invalidation_level']:,.0f}",annotation_position="bottom left")
            if alt.get("confirmation_level") is not None:efig.add_hline(y=alt["confirmation_level"],line_color="#9b7bff",line_dash="dot",annotation_text=f"ALT CONFIRMATION · ${alt['confirmation_level']:,.0f}",annotation_position="top left")
        efig.update_layout(height=600,margin={"l":8,"r":8,"t":15,"b":8},paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0","size":10},xaxis={"gridcolor":"#142033"},yaxis={"gridcolor":"#142033","type":"log","side":"right","tickformat":",.0f"},legend={"orientation":"h","y":1.02,"x":0},hovermode="x unified")
        e1,e2=st.columns([3,1])
        with e1:st.plotly_chart(efig,width="stretch",key="elliott_full_history",config={"displaylogo":False,"scrollZoom":True})
        with e2:
            revision_rate=macro_e["quality"].get("historical_revision_rate");revision_text="UNAVAILABLE" if revision_rate is None else str(revision_rate)
            st.markdown(f"""**PRIMARY COUNT**  \n{primary.get('name','Unresolved')}  \n\n**ALTERNATIVE COUNT**  \n{alt.get('name',ex['abc_alternative'])}  \n\n**WAVE ANCHOR / START**  \n{str(ex['wave_start'])[:10]} · {'—' if ex['wave_start_price'] is None else f"${ex['wave_start_price']:,.0f}"}  \n\n**INVALIDATION**  \n{'—' if primary.get('invalidation_level') is None else f"${primary['invalidation_level']:,.0f}"} · {primary.get('invalidation_reason','—')}  \n\n**CONFIRMATION**  \n{'—' if primary.get('confirmation_level') is None else f"${primary['confirmation_level']:,.0f}"}  \n\n**COUNT STABILITY**  \n{macro_e['quality']['count_stability']}  \n\n**HISTORICAL REVISION RATE**  \n{revision_text}  \n\n**STATUS**  \n{macro_e['status']} · {macro_e['production_role']}""")
            with st.expander("WHY THIS COUNT?"):
                st.markdown(f"""**Rules passed**  \n{' · '.join(primary.get('rules_passed',[])) or '—'}  \n\n**Guidelines matched**  \n{' · '.join(primary.get('guidelines_matched',[])) or '—'}  \n\n**Guidelines missed**  \n{' · '.join(primary.get('guidelines_missed',[])) or '—'}  \n\n**Fibonacci alignment**  \n{macro_e['quality'].get('fib_alignment','UNAVAILABLE')}  \n\n**Structural validity**  \n{macro_e['quality'].get('structural_validity','UNAVAILABLE')}  \n\n**What would destroy this count**  \n{ex['why']}  \n\n**Alternative interpretation**  \n{ex['abc_alternative']}""")
            st.caption("Elliott remains RESEARCH_ONLY / CONTEXT_ONLY · never a production or execution driver · labels are revisable")
with tabs[2]:
    hist_tabs=st.tabs(["ENTRY LAB","RISK / TOP LAB"])
    with hist_tabs[0]:
        st.subheader("Historical analogues · normalized comparison")
        compare=go.Figure()
        for item in closest[:3]:
            date=pd.Timestamp(item["date"]);date=date.tz_localize("UTC") if date.tzinfo is None else date;path=frame.loc[date-pd.Timedelta(days=90):date+pd.Timedelta(days=365)].close
            if not path.empty:compare.add_trace(go.Scatter(x=[(x-date).days for x in path.index],y=path/path.loc[date],name=str(date.date())))
        compare.update_layout(height=460,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Days from entry",yaxis_title="Normalized price");st.plotly_chart(compare,width="stretch");st.caption("Historical outcome – not forecast.")
        signal_book_path=ROOT/"data"/"reports"/"master5_signal_book.csv"
        if signal_book_path.exists():
            book=pd.read_csv(signal_book_path,parse_dates=["timestamp"]);buy_book=book[book.direction=="BUY"] if "direction" in book else book[book.signal.isin(SIGNAL_STYLE)]
            show_failures=st.toggle("SHOW FAILURES",False,key="entry_show_failures")
            entry_view=buy_book if show_failures else buy_book[buy_book.get("false_signal",False)==False]
            st.dataframe(entry_view[[c for c in ("timestamp","signal","price","archetype","return_365d","MAE","false_signal","status") if c in entry_view.columns]].sort_values("timestamp",ascending=False),hide_index=True)
            st.caption(f"{(~buy_book.get('false_signal',pd.Series(dtype=bool))).sum() if 'false_signal' in buy_book else len(buy_book)} historically successful · {buy_book.get('false_signal',pd.Series(dtype=bool)).sum() if 'false_signal' in buy_book else 0} failed candidates · toggle SHOW FAILURES to include both")
        else:
            st.info("Signal book not available in this environment.")
    with hist_tabs[1]:
        st.subheader("Historical Top / Risk episodes")
        if signal_book_path.exists():
            risk_book=book[book.direction=="RISK"] if "direction" in book else book.iloc[0:0]
            show_risk_failures=st.toggle("SHOW FAILURES",False,key="risk_show_failures")
            risk_view=risk_book if show_risk_failures else risk_book[risk_book.get("false_signal",False)==False]
            st.dataframe(risk_view[[c for c in ("timestamp","signal","price","archetype","return_365d","MAE","false_signal","status") if c in risk_view.columns]].sort_values("timestamp",ascending=False),hide_index=True)
            st.caption("Historical distribution / top-risk research episodes · outcomes only, never a prediction of the next top.")
        else:
            st.info("Signal book not available in this environment.")
with tabs[3]:
    st.subheader("Point-in-time Event Explorer");categories=sorted(event_rows.category.unique()) if not event_rows.empty else [];selected=st.multiselect("EVENT FILTER",categories,default=categories);shown=event_rows[event_rows.category.isin(selected)] if selected else event_rows.iloc[0:0];st.caption(f"{event_health['events']} verified sourced events · {event_health['reactions']} matured BTC reactions · {event_health['from']} to {event_health['to']}")
    if not shown.empty:
        event_times=pd.to_datetime(shown.available_at,utc=True);event_prices=frame.close.reindex(event_times,method="ffill");event_fig=go.Figure(go.Scatter(x=frame.index,y=frame.close,name="BTC",line={"color":"#4da3ff","width":1.2}));event_fig.add_trace(go.Scatter(x=event_times,y=event_prices,mode="markers",text=shown.headline,customdata=shown.category,hovertemplate="%{customdata}<br>%{text}<extra></extra>",marker={"color":"#f0b44d","size":9,"symbol":"diamond"},name="PIT events"));event_fig.update_layout(height=460,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log");st.plotly_chart(event_fig,width="stretch")
        selected_event=st.selectbox("EVENT DETAILS",shown.event_id,format_func=lambda eid:shown.loc[shown.event_id==eid,"headline"].iloc[0]);detail=shown.loc[shown.event_id==selected_event].iloc[0];reactions=event_db.reactions(selected_event);eleft,eright=st.columns([1,2])
        eleft.markdown(f"**EVENT**  \n{detail.headline}  \n\n**DATE**  \n{detail.event_time}  \n\n**REGIME INPUT TIME**  \n{detail.available_at}  \n\n**CATEGORY / IMPORTANCE**  \n{detail.category} · {detail.get('importance') or 'NOT CLASSIFIED'}  \n\n**STATUS**  \n{detail.get('status') or 'NOT CLASSIFIED'}  \n\n**SOURCE QUALITY**  \n{detail.source_quality}  \n\n[SOURCE]({detail.source_url})")
        reaction_24h=reactions.loc[reactions.horizon=="24H","return"].iloc[0] if not reactions.empty and "24H" in reactions.get("horizon",pd.Series()).values else None
        evo=expected_vs_observed(detail.get("expected_direction"),reaction_24h)
        causality=classify_causality(1,True,False)
        eright.dataframe(reactions[[x for x in ("horizon","asset","return","max_drawdown","resolution") if x in reactions]],hide_index=True)
        eright.markdown(f"**EXPECTED VS OBSERVED (24H)**  \n{evo['comparison']} — {evo['note']}  \n\n**CAUSALITY CONFIDENCE**  \n{causality['causality_level']} — {causality['note']}")
    st.dataframe(shown[["event_time","available_at","category","headline","source_quality","source_name","source_url"]],hide_index=True,column_config={"source_url":st.column_config.LinkColumn("SOURCE")});st.write("Calendar context",state["modules"]["seasonality"]);st.caption("Only information known by available_at is eligible. Missing historical cases remain unresolved, never invented.")
with tabs[4]:
    res_tabs=st.tabs(["PATTERNS","SIGNAL BOOK","DATA QUALITY","BACKTEST","AI COPILOT"])
    with res_tabs[0]:
        disc=feeds["fusion_discovery"];patterns_df=pd.DataFrame(disc["patterns"]);stable=patterns_df[patterns_df.longevity=="STABLE"];st.subheader("Stable historical patterns");st.dataframe(stable[["pattern_id","hypothesis","sample_size","effect_lift","era_coverage","longevity","status"]],hide_index=True);st.metric("Hypotheses tested",disc["hypotheses_tested"]);show_rejected=st.toggle("Show rejected patterns",False);visible_patterns=patterns_df if show_rejected else patterns_df[(patterns_df.status.isin(["PROMISING","DISCOVERED"]))|(patterns_df.longevity=="STABLE")];st.dataframe(visible_patterns[["pattern_id","hypothesis","sample_size","effect_lift","era_coverage","longevity","status"]],hide_index=True);st.caption("Exploratory multiple-testing risk: HIGH. RESEARCH_NEXT cannot affect the live decision.")
    with res_tabs[1]:
        p=ROOT/"data"/"reports"/"master5_signal_book.csv";st.dataframe(pd.read_csv(p) if p.exists() else pd.DataFrame(),hide_index=True)
    with res_tabs[2]:st.dataframe(pd.DataFrame(data_status).T)
    with res_tabs[3]:st.info("Research reports remain available under data/reports. Champion rules are unchanged.")
    with res_tabs[4]:
        ai=BitcoinAIRouter(values=env_values(ROOT/".env"),cache_dir=ROOT/"runtime"/"ai_cache");st.caption("AI Copilot explains engine state only · never decides · OpenAI is optional and explanation-only · execution DISABLED.")
        nano_button,deep_button=st.columns(2)
        if nano_button.button("AKTUELLE KURZFASSUNG",use_container_width=True):st.session_state["p8_nano"]=ai.explain("NANO",state)
        if deep_button.button("DEEP ANALYSIS",use_container_width=True):st.session_state["p8_analysis"]=ai.explain("ANALYSIS",state,deep=True)
        for key,title in (("p8_nano","KURZFASSUNG"),("p8_analysis","DEEP ANALYSIS")):
            result=st.session_state.get(key)
            if result:
                st.subheader(title);st.write(result.text);st.caption(f"{result.model or 'deterministic fallback'} · {result.status} · cache={'HIT' if result.cached else 'MISS'} · contradiction={result.contradiction_guard} · hallucination={result.hallucination_guard}")
with tabs[5]:
    st.subheader("SYSTEM HEALTH")
    heartbeat=ROOT/"runtime"/"production8"/"heartbeat.json";watcher_age=None if not heartbeat.exists() else pd.Timestamp.now(tz="UTC").timestamp()-heartbeat.stat().st_mtime
    ai=ai if "ai" in dir() else BitcoinAIRouter(values=env_values(ROOT/".env"),cache_dir=ROOT/"runtime"/"ai_cache")
    usage=ai.usage_today();health_rows=[
        {"Component":"MT5 / BTC Tick","Status":f"{live['status']} / {tick.get('freshness','OFFLINE')}","Provenance":"MetaTrader 5"},
        {"Component":"Confirmed H4 / D1 / W1","Status":" / ".join("FRESH" if live.get(key) is not None else "UNAVAILABLE" for key in ("last_confirmed_h4","last_confirmed_d1","last_confirmed_w1")),"Provenance":"MT5, closed candles only"},
        {"Component":"Production 8 Watcher","Status":"ONLINE" if watcher_age is not None and watcher_age<180 else "OFFLINE","Provenance":"runtime/production8/heartbeat.json"},
        {"Component":"Event DB","Status":"ONLINE" if event_health.get('events',0)>0 else "INSUFFICIENT DATA","Provenance":"Primary-source PIT database"},
        {"Component":"Forward Ledger","Status":"ONLINE","Provenance":"Append-only SQLite"},
        {"Component":"OpenAI","Status":"ENABLED" if ai.enabled else "DISABLED","Provenance":f"{ai.models['NANO']} / {ai.models['ANALYSIS']}"},
        {"Component":"Execution","Status":"DISABLED","Provenance":"Hard lock"},
    ];st.dataframe(pd.DataFrame(health_rows),hide_index=True,use_container_width=True)
    st.subheader("AI HEUTE");u1,u2,u3,u4,u5=st.columns(5);u1.metric("Requests",usage["calls"]);u2.metric("Nano",usage["nano_requests"]);u3.metric("Deep",usage["deep_requests"]);u4.metric("Cache Hits",usage["cache_hits"]);u5.metric("Kosten",f"${usage['estimated_cost_usd']:.4f}")
    st.caption(f"Tokens: {usage['input_tokens']:,} input · {usage['output_tokens']:,} output · Fallbacks: {usage['fallbacks']} · Frozen engines unchanged")
    st.divider();st.subheader("Machine-readable state · RESEARCH_ONLY exports")
    registry=rule_registry(macro7);indicator_state=build_indicator_state_v1(state,macro7)
    reg_col,ind_col=st.columns(2)
    with reg_col:
        st.markdown("**Rule Registry**");st.caption(f"{len(registry['scenarios'])} scenario rules · {len(registry['zones'])} zone definitions")
        st.download_button("Download rule_registry.json",json.dumps(registry,indent=2,default=str),file_name="rule_registry.json",mime="application/json")
    with ind_col:
        st.markdown("**BitcoinIndicatorStateV1**");st.caption(f"signal_state={indicator_state['signal_state']} · evidence={indicator_state['evidence']}")
        st.download_button("Download indicator_state.json",json.dumps(indicator_state,indent=2,default=str),file_name="indicator_state.json",mime="application/json")
    st.markdown("**Pine / MQL5 export capability matrix**")
    st.dataframe(pd.DataFrame(PINE_MQL_CAPABILITY_MATRIX),hide_index=True)
    st.caption("Capability matrix only — no Pine Script or MQL5 code is generated by this build. Execution remains DISABLED in all cases.")
    st.divider();st.subheader("Decision Rule Registry")
    st.dataframe(pd.DataFrame(DECISION_RULE_REGISTRY),hide_index=True,use_container_width=True)
    st.download_button("Download decision_state.json",json.dumps(decision_intel,indent=2,default=str),file_name="decision_state.json",mime="application/json")
    st.caption(f"{len(DECISION_RULE_REGISTRY)} auditable decision rules · every DecisionState traces back to a rule_id here · Elliott remains RESEARCH_ONLY / CONTEXT_ONLY")
