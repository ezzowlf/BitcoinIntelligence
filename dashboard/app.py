from pathlib import Path
import sys
import json
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from bitcoin_cycle_analyzer.ai import BitcoinAIRouter
from bitcoin_cycle_analyzer.runtime import env_values
from bitcoin_cycle_analyzer.telegram import SignalProgressStore,config_from_env
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.live import MT5MarketDataProvider
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.macro import load_macro_series
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase
from bitcoin_cycle_analyzer.fusion_live import Fusion6ForwardLedger
from bitcoin_cycle_analyzer.indicator_state import build_decision_state_v1,build_indicator_state_v1,rule_registry,write_json,PINE_MQL_CAPABILITY_MATRIX
from bitcoin_cycle_analyzer.decision_intelligence import build_decision_state as build_decision_intelligence,build_explanation_facts,RULE_REGISTRY as DECISION_RULE_REGISTRY
from bitcoin_cycle_analyzer.ui_state import LAYER_PRESETS,get_chart_view_state
from bitcoin_cycle_analyzer.glossary import GLOSSARY
from bitcoin_cycle_analyzer.event_intelligence import classify_causality,expected_vs_observed,event_evidence_family
from bitcoin_cycle_analyzer.drawing_state import UserDrawingStore,compute_fib_levels
from bitcoin_cycle_analyzer.action_story import translate_decision,translate_macro_action,translate_entry_status,translate_timing,translate_risk,translate_scenario_status,translate_scenario_name,translate_why_fact,translate_freshness,translate_regime,zone_message_de,what_must_happen_de,why_text_de,why_not_now_de,buy_playbook_de,elliott_roadmap_de,event_relevance_de,ELLIOTT_BASICS_DE

ROOT=Path(__file__).resolve().parents[1]
drawing_store=UserDrawingStore(ROOT,"BTCUSD")
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
.block-container{touch-action:pan-y}div[data-testid="stPlotlyChart"]{touch-action:none}
@media(max-width:700px){.block-container{padding:.65rem}.terminal-head{display:block}.price{font-size:1.85rem}.engines{margin-top:.5rem}.decision{grid-template-columns:1fr 1fr}.decision>div:nth-child(2){border-right:0}.decision>div{border-bottom:1px solid var(--line)}.decision label{font-size:.55rem;overflow-wrap:anywhere}.decision strong{font-size:.82rem}.viewbar{overflow-wrap:anywhere}.bottomcard{min-height:auto}.simplerow{grid-template-columns:1fr 1fr}}
</style>""",unsafe_allow_html=True)

config=load_config(ROOT/"config.yaml");store=OHLCVStore(ROOT/config["data"]["database"]);canonical=store.load_canonical("1d");frame=canonical[["open","high","low","close","volume"]] if not canonical.empty else store.load("1d")
if frame.empty:st.error("Keine BTC-Daten verfügbar.");st.stop()
env=env_values(ROOT/".env")
_progress_cfg_preview=config_from_env(env)
if not _progress_cfg_preview.enabled:telegram_progress_status,telegram_progress_source="DISABLED","TELEGRAM_PROGRESS_ENABLED=false"
elif env.get("TELEGRAM_DRY_RUN","true").strip().lower() not in {"0","false","no","off"}:telegram_progress_status,telegram_progress_source="DRY RUN","TELEGRAM_DRY_RUN=true"
else:
    _last_alert=SignalProgressStore(Path(env.get("BITCOIN_DATA_DIR",ROOT/"data"))/"signal_progress.db").last_alert_summary()
    telegram_progress_status="ACTIVE";telegram_progress_source="Letzter Alert: "+(str(_last_alert["last_sent_at"])[:16] if _last_alert else "noch keiner")
external=ExternalMetricStore(ROOT/config["data"]["external_database"]);mt5=MT5MarketDataProvider(values=env);mh=mt5.connect();tick=mt5.tick() if mh.status=="ONLINE" else {"status":"UNAVAILABLE","reason":mh.reason};h4=mt5.confirmed_candles("4h",1000) if mh.status=="ONLINE" else store.load("4h");d1=mt5.confirmed_candles("1d",700) if mh.status=="ONLINE" else frame.iloc[0:0];w1=mt5.confirmed_candles("1w",260) if mh.status=="ONLINE" else frame.iloc[0:0];m1=mt5.confirmed_candles("1mo",180) if mh.status=="ONLINE" else frame.iloc[0:0];div=MT5MarketDataProvider.divergence(tick.get("mid"),float(frame.close.iloc[-1]));usable=mh.status=="ONLINE" and tick.get("freshness") in {"LIVE","DELAYED"} and not d1.empty and div.get("status")!="CRITICAL"
if usable:frame=pd.concat([frame.loc[frame.index<d1.index[0]],d1]).sort_index();frame=frame[~frame.index.duplicated(keep="last")]
live={"status":"ONLINE" if usable else mh.status,"health":mh.__dict__,"tick":tick,"divergence":div,"last_confirmed_h4":None if mh.status!="ONLINE" or h4.empty else h4.index[-1],"last_confirmed_d1":None if mh.status!="ONLINE" or d1.empty else d1.index[-1],"last_confirmed_w1":None if mh.status!="ONLINE" or w1.empty else w1.index[-1],"last_confirmed_1m":None if mh.status!="ONLINE" or m1.empty else m1.index[-1],"timing_confirmation":"ENABLED" if usable else "BLOCKED","provenance":mt5.provenance()};mt5.close()
@st.cache_data(show_spinner=False)
def discovery(data):return HistoricalPatternDiscoveryEngine().discover(data)
event_db=PointInTimeEventDatabase(ROOT/"database"/"historical_event_evidence.db");event_health=event_db.health();event_rows=event_db.as_of(pd.Timestamp.now(tz="UTC"));fusion_live=Fusion6ForwardLedger(ROOT/"database"/"fusion6_live.db",json.loads((ROOT/"frozen"/"fusion_6_research_frozen.json").read_text(encoding="utf-8"))["forward_start"]);fusion_health=fusion_live.health()
try:macro_series=load_macro_series(env.get("FRED_API_KEY"),ROOT/"database"/"macro.db",frame.index[-1])
except Exception:macro_series={}
news_status="AVAILABLE" if event_health["status"]=="AVAILABLE" else "UNAVAILABLE"
news_summary={"status":news_status,"reason":None if news_status=="AVAILABLE" else "NO_EVENTS_IN_DATABASE","risk":None,"score":None,"source":"event_evidence.PointInTimeEventDatabase","records":event_health.get("events",0),"last_updated":event_health.get("to")}
feeds={"onchain_provider":StoreOnChainProvider(external),"four_hour":h4,"funding":external.load("funding_rate_8h"),"open_interest":external.load("open_interest_usd"),"etf":external.load("etf_net_flow_usd"),"macro":macro_series,"news_summary":news_summary,"live_market":live,"price_provider":"MT5 confirmed D1 + BITSTAMP historical" if usable else "BITSTAMP historical dataset","project_root":ROOT,"fusion_discovery":discovery(frame)}
state=analyze_intelligence(frame,config,feeds=feeds);m3=state["master"];ms=m3["state"];md=m3["decision"];m5=state["master5_challenger"];fusion=state["fusion6"];macro7=state["macro7"];hq=state["historical_entry_quality"];cycles=state["elliott_cycle"]["cycle_history"];elliott=state["elliott_cycle"]["elliott"];mom=state["advanced"]["momentum"]
live_price=tick.get("mid") if usable else ms["btc_price"];spread=tick.get("spread");day_change=float(frame.close.iloc[-1]/frame.close.iloc[-2]-1) if len(frame)>1 else 0
status_class="live" if usable else "";tick_label=str(tick.get("timestamp","—"))[11:19];confirmed=str(live.get("last_confirmed_h4") or "—")[:16]
feed_label="LIVE-KURSDATEN: AKTIV" if usable and tick.get("freshness")=="LIVE" else "LIVE-KURSDATEN: VERZÖGERT" if usable else "LIVE-KURSDATEN: NICHT VERFÜGBAR"
price_note="" if usable else f"<div class='micro'>Live-Kurs derzeit nicht verfügbar — letzter bestätigter Tageskurs: ${ms['btc_price']:,.2f} (Stand: {frame.index[-1].date()})</div>"
st.markdown(f"""<div class='terminal-head'><div><div class='ticker'>₿ BTCUSD <span class='badge {status_class}'>{feed_label}</span></div><div class='price'>${live_price:,.2f}</div>{price_note}<div class='micro'><span class='{'positive' if day_change>=0 else 'negative'}'>{day_change:+.2%} Tag</span> · Geldkurs {'—' if tick.get('bid') is None else f'${tick["bid"]:,.2f}'} · Briefkurs {'—' if tick.get('ask') is None else f'${tick["ask"]:,.2f}'} · Spanne {'—' if spread is None else f'${spread:.2f}'} · Tick {tick_label} UTC · Alter {tick.get('age_seconds','—')}s · Bestätigt H4 {confirmed} · D1 {str(live.get('last_confirmed_d1') or '—')[:16]} · W1 {str(live.get('last_confirmed_w1') or '—')[:16]}</div></div><div class='engines'><span class='engine' title='Leitmodell — steuert das aktuelle Entscheidungssignal oben.'><i class='dot'></i>CONTROL 3</span><span class='engine' title='Vergleichsmodell — prüft historische Setup-Qualität, steuert nicht direkt das Leitsignal.'><i class='dot'></i>SPECIALIST 5</span><span class='engine' title='Forschungsmodell — liefert zusätzliche Hinweise, steuert aber nicht das aktuelle Leitsignal.'><i class='dot' style='background:var(--amber)'></i>FUSION 6 · FORSCHUNG</span></div></div>""",unsafe_allow_html=True)
macro_e=macro7["elliott"];active_scenario=next((x for x in macro7["scenarios"] if x["status"]=="ACTIVE"),macro7["scenarios"][0])
timing_state="CONFIRMED" if md.get("state")=="CONFIRMED" else "CONFIRMING" if md.get("waiting_for") and len(md.get("waiting_for"))<=1 else "EARLY" if md.get("waiting_for") else "WAIT"
decision_state=build_decision_state_v1(state,macro7,live_price,active_scenario,timing_state)
decision_intel=build_decision_intelligence(state,macro7,frame,live_price)
decision_explanation=build_explanation_facts(decision_intel)
risk_state=decision_state["risk"]
st.markdown(f"""<div class='decision'><div><label>MAKRO</label><strong class='positive'>{translate_macro_action(decision_state['macro'])}</strong></div><div><label>LANGFRISTIG</label><strong class='score'>{translate_macro_action(decision_state['long_swing'])}</strong></div><div><label>TIMING</label><strong>{translate_timing(decision_state['timing'])}</strong></div><div><label>RISIKO</label><strong class='{"negative" if risk_state=="HIGH" else "score" if risk_state=="CAUTION" else "positive"}'>{translate_risk(risk_state)}</strong></div><div><label>AKTUELLES SZENARIO</label><strong>{translate_scenario_name(decision_state['current_scenario']['name'])}</strong></div></div><div class='viewbar'><b>LEITSIGNAL (CONTROL 3 / MACRO 7)</b> · {translate_why_fact(decision_state['why'][0])} · {translate_why_fact(decision_state['why'][1])} · Ein langfristiges Kaufsignal bleibt gesperrt, solange noch keine ausreichend bestätigte Kaufgelegenheit vorliegt — Details siehe ENTSCHEIDUNGSBEGRÜNDUNG unten.</div>""",unsafe_allow_html=True)
status_color={"ACTIVE":"var(--green)","WATCH":"var(--amber)","DORMANT":"var(--muted)","INVALIDATED":"var(--red)"}
scenario_chips="".join(f"<span class='badge' style='border-color:{status_color.get(s['status'],'var(--line)')};color:{status_color.get(s['status'],'var(--muted)')}'>{translate_scenario_name(s['name'])} · {translate_scenario_status(s['status'])}</span>" for s in macro7["scenarios"])
st.markdown(f"<div style='margin:-.35rem 0 .6rem;line-height:2.1'>{scenario_chips}</div>",unsafe_allow_html=True)

di=decision_intel;dz=di["active_zone"];dec_color={"STRONG_BUY":"var(--green)","BUY":"var(--green)","ACCUMULATE":"var(--amber)","WATCH":"var(--amber)","WAIT":"var(--muted)","REDUCE":"var(--red)","TAKE_PROFIT":"var(--amber)","HIGH_RISK":"var(--red)","SELL":"var(--red)","NO_EDGE":"var(--muted)"}.get(di["decision"],"var(--muted)")
zone_line="Keine aktive strukturelle Zone" if dz is None or dz.get("lower") is None else f"{dz['label']} · ${dz['lower']:,.0f} – ${dz['upper']:,.0f}"
qp=st.query_params;view_state=get_chart_view_state(st.session_state,qp)
mode_col,_=st.columns([1,4])
mode=mode_col.segmented_control("ANSICHT",["SIMPLE","RESEARCH"],format_func=lambda k:"EINFACH" if k=="SIMPLE" else "FORSCHUNG",default=view_state["mode"],label_visibility="collapsed")
view_state["mode"]=mode;qp["mode"]=mode
simple=mode=="SIMPLE"

if simple:
    strategic_de=translate_macro_action(decision_state["macro"]);tactical_de=translate_decision(di["decision"])
    is_buy=di["decision"] in ("BUY","STRONG_BUY");zone_msg=zone_message_de(di["active_zone"]);must_happen=what_must_happen_de(di["confirmation"])
    st.markdown(f"""<div class='simplecard'><div class='micro'>WAS SOLL ICH JETZT TUN?</div>
    <div class='simplerow' style='margin-top:.3rem'>
    <div><label>STRATEGISCH (langfristige Lage)</label><b>{strategic_de}</b></div>
    <div><label>AKTION JETZT</label><b style='color:{dec_color}'>{tactical_de}</b></div>
    </div>
    <div class='micro' style='margin-top:.6rem'>{why_text_de(di,decision_explanation)}</div>
    <div class='simplerow' style='margin-top:.6rem'>
    <div><label>INTERESSANTE ZONE</label><b>{zone_msg}</b></div>
    <div><label>JETZT KAUFEN?</label><b>{'JA' if is_buy else 'NEIN'}</b></div>
    <div><label>THESE FALSCH UNTER</label><b>{'—' if di['invalidation_level'] is None else f"${di['invalidation_level']:,.0f}"}</b></div>
    <div><label>ZIELE DANACH</label><b>{', '.join(f"${t['price']:,.0f}" for t in di['targets'][:3]) or '—'}</b></div>
    </div></div>""",unsafe_allow_html=True)

    if is_buy:
        pb=buy_playbook_de(di)
        st.markdown(f"""<div class='simplecard' style='border-color:{dec_color}'><div class='micro'>KAUFSIGNAL AKTIV</div><div class='bigstate' style='color:{dec_color}'>{tactical_de}</div>
        <div class='simplerow' style='margin-top:.5rem'>
        <div><label>ENTRY-TYP</label><b>{pb['entry_type']}</b></div>
        <div><label>ENTRY-ZONE</label><b>{pb['entry_zone']}</b></div>
        <div><label>STOP / INVALIDIERUNG</label><b>{pb['invalidation']}</b></div>
        <div><label>ERSTES ZIEL (T1)</label><b>{pb['first_target']}</b></div>
        <div><label>RISIKO</label><b>{pb['risk']}</b></div>
        </div>
        <div class='micro' style='margin-top:.5rem'><b>WARUM:</b> {' · '.join(pb['why'])}</div>
        <div class='micro'><b>WAS TUN?</b> Einstieg innerhalb der Zone möglich. Nicht oberhalb von {pb['dont_chase_above']} hinterherlaufen.</div>
        </div>""",unsafe_allow_html=True)
    else:
        with st.expander("WARUM NICHT JETZT KAUFEN?"):
            st.markdown(why_not_now_de(di))
            if must_happen["missing"]:
                st.markdown("**Fehlende Bestätigung:**")
                for m in must_happen["missing"]:st.markdown(f"- {m}")
        st.markdown("Es gibt aktuell keinen hochwertigen, bestätigten Trade. Das System wartet bewusst auf bessere Bedingungen." if di["decision"] in ("WAIT","NO_EDGE") else "")

    with st.expander("WAS MUSS PASSIEREN, DAMIT SICH DAS ÄNDERT?"):
        for m in must_happen["missing"]:st.markdown(f"1. {m}")
        st.caption(must_happen["closing"])

    with st.expander("ELLIOTT EINFACH ERKLÄRT"):
        st.markdown(ELLIOTT_BASICS_DE)
        roadmap=elliott_roadmap_de(di["elliott_structure"])
        st.markdown(f"**WO SIND WIR VERMUTLICH?**  \n{roadmap['current_hypothesis']}  \n\n**PASST DAS ZUM ZYKLUS?**  \n{roadmap['consistency_note']}")
        st.markdown("**WAS KÖNNTE DANACH KOMMEN?**")
        for step in roadmap["possible_next_steps"]:st.markdown(f"- {step}")
        st.caption(roadmap["limitation"])

    with st.expander("Begriffe erklärt"):
        for term in ("Cycle","Invalidation","Confirmation","Reclaim"):
            st.markdown(f"**{term}** — {GLOSSARY.get(term,'')}")
    recent_events=event_rows[pd.to_datetime(event_rows.event_time,utc=True)>=pd.Timestamp.now(tz="UTC")-pd.Timedelta(days=90)] if not event_rows.empty else event_rows
    with st.expander(f"WICHTIGE NEWS / EREIGNISSE ({len(recent_events)})"):
        if recent_events.empty:
            if event_health.get("events",0)==0:
                st.markdown("Nachrichtendaten derzeit nicht verfügbar.")
            else:
                st.markdown("Es gibt derzeit keine relevanten Ereignisse in den letzten 90 Tagen.")
        else:
            for _,ev in recent_events.sort_values("event_time",ascending=False).iterrows():
                st.markdown(f"**{ev.get('importance') or 'UNKLASSIFIZIERT'}** — {ev.headline} ({str(ev.event_time)[:10]})")
        st.caption(event_relevance_de(recent_events))
    layers=[];tf_de=st.segmented_control("ZEITRAUM",["1T","1W","1M","1J","ALLES"],default="ALLES",label_visibility="collapsed");tf={"1T":"1D","1W":"1W","1M":"1M","1J":"1Y","ALLES":"ALL"}[tf_de];scale="LOG" if tf in {"ALL","1Y"} else "LIN"
else:
    preset_row=st.columns([1,1,1,1,3])
    for idx,pname in enumerate(LAYER_PRESETS):
        if preset_row[idx].button(pname,key=f"preset_{pname}",use_container_width=True):st.session_state["layers"]=LAYER_PRESETS[pname];qp["preset"]=pname
    if "layers" not in st.session_state:st.session_state["layers"]=LAYER_PRESETS.get(qp.get("preset","SWING"),LAYER_PRESETS["SWING"])
    controls=st.columns([1,2.15,.85]);tf_options={"4H":"4H","1D":"1T","1W":"1W","1M":"1M","1Y":"1J","ALL":"ALLES"};tf=controls[0].segmented_control("ZEITRAUM",list(tf_options),format_func=lambda k:tf_options[k],default=qp.get("tf","ALL"),label_visibility="collapsed");layers=controls[1].multiselect("EBENEN",["Macro Zones","Swing Zones","200D/200W","Bollinger","Fib","Elliott","Historical Entries","Events","Signals"],key="layers",label_visibility="collapsed",format_func=lambda k:{"Macro Zones":"Makrozonen","Swing Zones":"Swing-Zonen","200D/200W":"200T/200W","Bollinger":"Bollinger","Fib":"Fib","Elliott":"Elliott","Historical Entries":"Historische Einstiege","Events":"Ereignisse","Signals":"Signale"}.get(k,k));scale=controls[2].segmented_control("SKALA",["LOG","LIN"],default=qp.get("scale") or ("LOG" if tf in {"ALL","1Y"} else "LIN"),label_visibility="collapsed")
qp["tf"]=tf;qp["scale"]=scale

chart_frame=h4 if tf=="4H" and not h4.empty else frame.resample("W-MON").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1W" else frame.resample("ME").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1M" else frame.resample("YE").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna() if tf=="1Y" else frame
visible=chart_frame if tf in {"ALL","1Y"} else chart_frame.tail(450 if tf in {"4H","1D"} else 220);fig=go.Figure(go.Candlestick(x=visible.index,open=visible.open,high=visible.high,low=visible.low,close=visible.close,increasing_line_color="#26c281",decreasing_line_color="#ee5a67",name="BTC"))
support=ms.get("nearest_support");resistance=ms.get("nearest_resistance")
# Decision Intelligence zone/invalidation/targets ALWAYS render — highest chart-layer priority, never gated behind a layer toggle.
if dz is not None and dz.get("lower") is not None:
    zone_fill={"STRONG_BUY_ZONE":"rgba(38,194,129,.18)","BUY_ZONE":"rgba(38,194,129,.12)","WATCH_ZONE":"rgba(240,180,77,.10)","TAKE_PROFIT_ZONE":"rgba(240,180,77,.10)","HIGH_RISK_ZONE":"rgba(238,90,103,.12)"}.get(dz["zone_type"],"rgba(240,180,77,.10)")
    fig.add_hrect(y0=dz["lower"],y1=dz["upper"],fillcolor=zone_fill,line_width=1.5,line_color=dec_color,annotation_text=f"{dz['zone_type'].replace('_',' ')} · {di['entry_status'].replace('_',' ')}",annotation_position="top left",annotation_font_color=dec_color)
if di.get("invalidation_level") is not None:
    fig.add_hline(y=di["invalidation_level"],line_color="#ee5a67",line_dash="dash",line_width=1.3,annotation_text=f"UNGÜLTIG AB ${di['invalidation_level']:,.0f}",annotation_position="bottom right")
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
# User drawings (P1 chart interaction pass) — pure annotations, never fed into any engine/decision function.
user_drawings=drawing_store.list(timeframe=tf) if not simple else []
for ud in user_drawings:
    c=ud["coordinates"]
    if ud["type"]=="HLINE":
        fig.add_hline(y=c["price"],line_color="#e6edf7",line_width=1,line_dash="solid",annotation_text=f"MEINE: {ud['text'] or 'Linie'}",annotation_position="bottom left")
    elif ud["type"]=="RECTANGLE":
        fig.add_hrect(y0=c["low"],y1=c["high"],fillcolor="rgba(230,237,247,.07)",line_color="#e6edf7",line_width=1,annotation_text=f"MEINE ZONE: {ud['text']}" if ud["text"] else "MEINE ZONE",annotation_position="bottom left")
    elif ud["type"]=="FIB":
        for lvl in compute_fib_levels(c["price_a"],c["price_b"]):
            fig.add_hline(y=lvl["price"],line_color="#c9a0ff",line_width=1,line_dash="dot",annotation_text=f"MEIN FIB {lvl['ratio']}",annotation_position="top left")
visible_lo=float(visible["low"].min());visible_hi=float(visible["high"].max());pad=(visible_hi-visible_lo)*0.12 or visible_hi*0.05
yaxis_layout={"side":"right","gridcolor":"#142033","tickformat":",.0f","type":"log" if scale=="LOG" else "linear","showspikes":True,"spikemode":"across","spikesnap":"cursor","spikecolor":"#4da3ff","spikethickness":1}
if scale=="LIN":yaxis_layout["range"]=[max(0,visible_lo-pad),visible_hi+pad]
else:yaxis_layout["range"]=[math.log10(max(visible_lo*0.5,1)),math.log10(visible_hi*3)]
fig.update_layout(height=620 if simple else 555,margin={"l":8,"r":8,"t":15,"b":8},paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0","size":10},dragmode="pan",newshape={"line":{"color":"#f0b44d","width":1.5}},xaxis={"rangeslider":{"visible":False},"gridcolor":"#142033","showspikes":True,"spikemode":"across","spikesnap":"cursor","spikecolor":"#4da3ff","spikethickness":1},yaxis=yaxis_layout,legend={"orientation":"h","y":1.02,"x":0},hovermode="x unified")
st.plotly_chart(fig,width="stretch",config={"displaylogo":False,"scrollZoom":True,"displayModeBar":True,"modeBarButtonsToAdd":["v1hovermode","toggleSpikelines","drawline","drawopenpath","drawrect","drawcircle","eraseshape"],"modeBarButtonsToRemove":["lasso2d","select2d"]})
st.caption("Grün/Gelb/Rot = aktive Entscheidungszone · gestrichelt rot = Ungültig ab · gepunktet blau = Kursziele · weiß/lila MEINE Linien = eigene gespeicherte Zeichnungen (unten hinzufügen) · das Stift-Symbol im Chart selbst zeichnet nur temporäre Skizzen, die NICHT gespeichert werden — nutzen Sie ZEICHENWERKZEUGE unten für alles, was erhalten bleiben soll")

if simple:
    st.stop()

ma200w_ref=float(frame.close.rolling(1400).mean().iloc[-1])
with st.expander(f"ZEICHENWERKZEUGE ({len(user_drawings)} gespeichert für {tf})"):
    st.caption("Ihre Zeichnungen sind reine Anmerkungen — sie verändern niemals die Entscheidung, Evidence Families oder Elliott-/Zonen-Ausgaben oben.")
    dcol1,dcol2=st.columns([1,2])
    tool=dcol1.radio("WERKZEUG",["Horizontal Line","Rectangle Zone","Fibonacci"],format_func=lambda k:{"Horizontal Line":"Horizontale Linie","Rectangle Zone":"Rechteckzone","Fibonacci":"Fibonacci"}[k],label_visibility="collapsed")
    with dcol2:
        draw_price_max=float(live_price)*10
        if tool=="Horizontal Line":
            price=st.number_input("Preis",value=float(live_price),step=1.0,min_value=0.0,max_value=draw_price_max,key="draw_hline_price")
            label=st.text_input("Beschriftung (optional)",key="draw_hline_label")
            if st.button("Linie hinzufügen",key="draw_hline_add"):drawing_store.add("HLINE",tf,{"price":price},text=label);st.session_state.setdefault("drawing_undo_stack",[]).append(("delete_last",));st.rerun()
        elif tool=="Rectangle Zone":
            c1,c2=st.columns(2);low=c1.number_input("Tief",value=float(live_price)*0.95,step=1.0,min_value=0.0,max_value=draw_price_max,key="draw_rect_low");high=c2.number_input("Hoch",value=float(live_price)*1.05,step=1.0,min_value=0.0,max_value=draw_price_max,key="draw_rect_high")
            label=st.text_input("Beschriftung (optional)",key="draw_rect_label")
            if st.button("Rechteck hinzufügen",key="draw_rect_add"):
                if high>low:drawing_store.add("RECTANGLE",tf,{"low":low,"high":high},text=label);st.rerun()
                else:st.error("Hoch muss größer als Tief sein")
        else:
            c1,c2=st.columns(2);price_a=c1.number_input("Punkt A Preis",value=float(live_price)*0.9,step=1.0,min_value=0.0,max_value=draw_price_max,key="draw_fib_a");price_b=c2.number_input("Punkt B Preis",value=float(live_price),step=1.0,min_value=0.0,max_value=draw_price_max,key="draw_fib_b")
            label=st.text_input("Beschriftung (optional)",key="draw_fib_label")
            st.caption("MEIN FIB — eigenes Retracement, unabhängig von Elliott-/Engine-Zielen (siehe SYSTEM-Zonen/Ziele oben).")
            if st.button("Fibonacci hinzufügen",key="draw_fib_add"):drawing_store.add("FIB",tf,{"price_a":price_a,"price_b":price_b},text=label);st.rerun()
    if user_drawings:
        st.divider()
        for ud in user_drawings:
            row=st.columns([3,1,1,1])
            c=ud["coordinates"]
            desc=f"Linie @ ${c['price']:,.0f}" if ud["type"]=="HLINE" else f"Zone ${c['low']:,.0f}–${c['high']:,.0f}" if ud["type"]=="RECTANGLE" else f"Fib ${c['price_a']:,.0f}→${c['price_b']:,.0f}"
            row[0].write(f"{'🔒 ' if ud['locked'] else ''}{desc}"+(f" · {ud['text']}" if ud["text"] else ""))
            if ud["type"]=="RECTANGLE" and row[1].button("Analysieren",key=f"draw_analyze_{ud['drawing_id']}"):
                low,high=ud["coordinates"]["low"],ud["coordinates"]["high"]
                facts=[]
                if low<=ma200w_ref<=high:facts.append("überschneidet 200W")
                if dz and dz.get("lower") is not None and not (high<dz["lower"] or low>dz["upper"]):facts.append(f"überschneidet aktive {dz['zone_type'].replace('_',' ').lower()}")
                if di.get("invalidation_level") and low<=di["invalidation_level"]<=high:facts.append("enthält das Ungültig-ab-Niveau")
                st.info("Diese Zone " + (", ".join(facts) if facts else "hat keine aktuell erkannte Überschneidung mit dem System") + " — nur informativ, erzeugt kein Signal.")
            if row[2].button("🔓" if ud["locked"] else "🔒",key=f"draw_lock_{ud['drawing_id']}"):drawing_store.update(ud["drawing_id"],locked=not ud["locked"]);st.rerun()
            if not ud["locked"] and row[3].button("Löschen",key=f"draw_del_{ud['drawing_id']}"):
                deleted=drawing_store.delete(ud["drawing_id"]);st.session_state.setdefault("drawing_undo_stack",[]).append(("restore",deleted));st.rerun()
        if st.session_state.get("drawing_undo_stack") and st.button("Letzte Änderung rückgängig",key="draw_undo"):
            action=st.session_state["drawing_undo_stack"].pop()
            if action[0]=="restore":drawing_store.restore(action[1])
            elif action[0]=="delete_last" and user_drawings:drawing_store.delete(user_drawings[-1]["drawing_id"])
            st.rerun()

with st.expander("WARUM?"):
    st.markdown("**Dafür spricht**  \n"+("\n".join(decision_explanation["why_positive"]) or "—"))
    st.markdown("**Dagegen spricht / fehlt**  \n"+("\n".join(decision_explanation["why_not_buy"]) or "—"))
    if di["targets"]:st.markdown("**Kursziele**  \n"+"  \n".join(f"{t['id']}: ${t['price']:,.0f} — {t['why']}" for t in di["targets"]))
    st.caption(decision_explanation["role"]+" · Regeln: "+", ".join(r.split(":")[0] for r in decision_explanation["rule_ids"]))

wait_labels={"no_confirmed_lower_low":"Noch kein neues bestätigtes Tief","structure_reclaim":"Struktur noch nicht zurückerobert","h4_or_d1_confirmation":"H4-/D1-Bestätigung fehlt noch"};waiting="".join(f"<span>○ {wait_labels.get(x,x)}</span>" for x in md["waiting_for"])
macro_primary=macro_e["primary"];macro_alt=(macro_e["alternatives"] or [{}])[0]
recent_important=event_rows[event_rows.importance.isin(["HIGH","CRITICAL"])] if not event_rows.empty and "importance" in event_rows else event_rows.iloc[0:0]
decision_label_de=translate_decision(di["decision"])
st.markdown(f"""<div class='simplerow' style='margin:.3rem 0 .8rem'>
<div class='sidepanel' style='margin:0;grid-column:span 2'><h4>ENTSCHEIDUNGSBEGRÜNDUNG <span class='micro'>erklärt das Leitsignal oben</span></h4><div class='bigstate' style='color:{dec_color}'>{decision_label_de}</div><div class='micro'>{decision_explanation['summary']}</div><div class='levelrow'><span>ZONE</span><b>{zone_line}</b></div><div class='levelrow'><span>EINSTIEG</span><b>{di['entry_status'].replace('_',' ')}</b></div><div class='levelrow'><span>UNGÜLTIG AB</span><b>{'—' if di['invalidation_level'] is None else f"${di['invalidation_level']:,.0f}"}</b></div><div class='levelrow'><span>VERTRAUEN</span><b>{di['decision_confidence']['label']} ({di['decision_confidence']['score']}/100)</b></div></div>
<div class='sidepanel' style='margin:0'><h4>HISTORISCHER SETUP-SCORE <span class='micro' title="Ein separater SPECIALIST-5-Score — wie gut dieses Setup zu historisch erfolgreichen Einstiegen passt. Nicht dasselbe wie der VERTRAUEN-Score oben.">ⓘ</span></h4><div class='bigstate score'>{m5['buy']['quality']:.0f} / 100</div><div>{m5['buy']['state']} · {m5['buy']['zone_lifecycle']['state']}</div><div class='micro'>Historische Übereinstimmungsqualität, keine Erfolgswahrscheinlichkeit</div></div>
<div class='sidepanel' style='margin:0'><h4>ABVERKAUFSRISIKO</h4><div class='bigstate'>{m5['risk']['sell_off_risk']}</div><div class='micro'>{m5['risk']['distribution']} · {m5['risk']['existing_position_action']}</div><div class='levelrow'><span>WICHTIGE UNTERSTÜTZUNG</span><b>{'—' if not support else f'${support["upper_bound"]:,.0f}'}</b></div><div class='levelrow'><span>WICHTIGER WIDERSTAND</span><b>{'—' if not resistance else f'${resistance["lower_bound"]:,.0f}'}</b></div></div>
<div class='sidepanel' style='margin:0'><h4>WARTET AUF</h4><div class='compactlist'>{waiting}</div></div>
<div class='sidepanel' style='margin:0'><h4>ZYKLUS &amp; STRUKTUR</h4><div class='compactlist'><span><b>ZYKLUS</b> {translate_regime(fusion['regime'])} · {cycles['current']['drawdown']:.1%} vom Allzeithoch</span><span><b>ELLIOTT PRIMÄR</b> {macro_primary.get('name','Unbestätigt')}</span><span><b>SZENARIO</b> {translate_scenario_name(active_scenario['name'])} · {translate_scenario_status(active_scenario['status'])}</span></div></div>
<div class='sidepanel' style='margin:0'><h4>RELEVANTE EREIGNISSE</h4><div class='compactlist'>{"".join(f"<span>{e.get('importance') or '—'} · {e.headline[:48]}</span>" for _,e in recent_important.tail(2).iterrows()) or "<span>Keine HIGH/CRITICAL-Ereignisse erfasst</span>"}</div></div>
</div>""",unsafe_allow_html=True)

cycle=cycles["current"];closest=hq.get("closest_historical_entries",[]);rsi_d=mom["daily"]["rsi"];rsi_w=mom["weekly"]["rsi"];rsi_m=mom["monthly"]["rsi"];ma200=float(frame.close.rolling(200).mean().iloc[-1]);ma200w=float(frame.close.rolling(1400).mean().iloc[-1]);data_status=state["data_status"]
b1,b2,b3,b4=st.columns(4,gap="small")
with b1:st.markdown(f"<div class='bottomcard'><h4>ZYKLUS</h4><div class='bottomgrid'><span>REGIME</span><b>{fusion['regime']}</b><span>ELLIOTT</span><b>{elliott['primary']['name'].replace('Possible ','')[:20]}</b><span>RÜCKGANG</span><b>{cycle['drawdown']:.1%}</b><span>SEIT ATH</span><b>{cycle['days_since_ath']}T</b><span>SEIT HALVING</span><b>{cycles['days_since_halving']}T</b></div></div>",unsafe_allow_html=True)
with b2:st.markdown(f"<div class='bottomcard'><h4>HISTORISCH</h4><div class='bottomgrid'><span>EINSTIEGSQUALITÄT</span><b>{hq['score']:.0f} / 100</b><span>STATUS</span><b>{hq['state']}</b><span>ARCHETYP</span><b>{m5['buy']['archetype'].replace('_',' ')}</b><span>ÄHNLICHSTE</span><b>{' · '.join(str(pd.Timestamp(x['date']).year) for x in closest[:3]) or '—'}</b><span>AKTIVE MUSTER</span><b>{len(fusion['active_historical_patterns'])}</b></div></div>",unsafe_allow_html=True)
with b3:st.markdown(f"<div class='bottomcard'><h4>MOMENTUM</h4><div class='bottomgrid'><span>RSI T</span><b>{rsi_d or '—'}</b><span>RSI W</span><b>{rsi_w or '—'}</b><span>RSI M</span><b>{rsi_m or '—'}</b><span>VS 200T</span><b>{live_price/ma200-1:+.1%}</b><span>VS 200W</span><b>{live_price/ma200w-1:+.1%}</b></div></div>",unsafe_allow_html=True)
with b4:st.markdown(f"<div class='bottomcard'><h4>DATEN</h4><div class='bottomgrid'><span>MT5</span><b class='{'positive' if usable else 'negative'}'>{'LIVE' if usable else 'OFFLINE'}</b><span>ON-CHAIN</span><b>{data_status['onchain']['status']}</b><span>DERIVATE</span><b>{data_status['derivatives']['status']}</b><span>MAKRO</span><b>{data_status['macro']['status']}</b><span>NEWS</span><b>{data_status['news']['status']}</b></div></div>",unsafe_allow_html=True)

tabs=st.tabs(["CHART","ZYKLEN","HISTORIE","EREIGNISSE","FORSCHUNG","SYSTEM"])
with tabs[0]:
    st.subheader("Makro-Szenariokarte")
    scenario_rows=[{"Szenario":translate_scenario_name(x["name"]),"Status":translate_scenario_status(x["status"]),"Warum diese Zone existiert":x["price_zone"]["support"],"Zone":f"${x['price_zone']['low']:,.0f} – ${x['price_zone']['high']:,.0f}","Bestätigung":x["confidence_state"],"Aktiviert wenn":" · ".join(x["activation_conditions"]),"Ungültig wenn":" · ".join(x["invalidation_conditions"]),"Historischer Kontext":" · ".join(x["historical_analogues"]) or "NICHT VERFÜGBAR","Elliott-Kontext":x["elliott_context"]} for x in macro7["scenarios"]]
    st.dataframe(pd.DataFrame(scenario_rows),hide_index=True)
    detail_name=st.selectbox("SZENARIO-DETAILS",[s["name"] for s in macro7["scenarios"]],format_func=translate_scenario_name)
    detail=next(s for s in macro7["scenarios"] if s["name"]==detail_name)
    dleft,dright=st.columns(2)
    dleft.markdown(f"""**WARUM DIESES SZENARIO EXISTIERT**  \n{detail['price_zone']['support']}  \n\n**AKTIVIERT WENN**  \n{' · '.join(detail['activation_conditions'])}  \n\n**UNGÜLTIG WENN**  \n{' · '.join(detail['invalidation_conditions'])}""")
    dright.markdown(f"""**KURSZIEL / PREISREGION**  \n${detail['price_zone']['low']:,.0f} – ${detail['price_zone']['high']:,.0f}  \n\n**HISTORISCHE ANALOGIEN**  \n{' · '.join(detail['historical_analogues']) or 'NICHT VERFÜGBAR'}  \n\n**ELLIOTT-KONTEXT**  \n{detail['elliott_context']}  \n\n**RÜCKGANGS-KONTEXT**  \n{detail['drawdown_context']:.1%}""" if isinstance(detail['drawdown_context'],float) else f"**RÜCKGANGS-KONTEXT**  \n{detail['drawdown_context']}")
    st.divider()
    z=macro7["zones"];zone_rows=[{"Horizont":name.replace("_"," ").title(),"Zone":"NICHT VERFÜGBAR" if zone is None else f"${zone['low']:,.0f} – ${zone['high']:,.0f}","Bestätigung":"NICHT VERFÜGBAR" if zone is None else zone["support"]} for name,zone in (("tactical",z["tactical_buy"]),("swing",z["swing_buy"]),("macro accumulation",z["macro_accumulation"]),("deep value",z["deep_value"]),("extreme cycle",z["extreme_cycle"]))];st.dataframe(pd.DataFrame(zone_rows),hide_index=True)
    st.subheader("Makro-Preiskarte · 50k / 40k / 30k bedingter Kontext")
    level_rows=[]
    for target in (50000,40000,30000):
        closest_level=min(macro7["drawdown_ladder"]["levels"],key=lambda x:abs(x["price"]-target));level_rows.append({"BTC-Niveau":f"${target:,.0f}","ATH-Rückgang":f"{target/macro7['indicators']['ath']-1:.1%}","Abstand zu 200W":f"{target/macro7['indicators']['ma200w']-1:.1%}","Historischer Kontext":"Tiefzyklus-Band" if target<macro7['indicators']['ma200w'] else "Nähe 200W","Aktuell aktiv":"NEIN","Szenario":"INAKTIV — KEIN AKTIVES ZIEL · nur bedingter Kontext","Nächste historische Stufe":f"{closest_level['drawdown']:.0%}"})
    st.dataframe(pd.DataFrame(level_rows),hide_index=True);st.caption("Diese Level sind bedingter Kontext, keine Prognose · CONTROL 3 bleibt Leitsystem · MACRO SWING 7 bleibt Forschungs-Herausforderer · AUTOMATISCHER HANDEL: DEAKTIVIERT")
with tabs[1]:
    cyc_tabs=st.tabs(["ELLIOTT","ZYKLUS-LABOR"])
    with cyc_tabs[1]:
        st.subheader("Historisches Bitcoin-Zyklus-Labor")
        view_options=["Full BTC History","Halving Cycles","ATH Drawdowns","Bottom Recoveries","Yearly Candles"]
        view_labels_de={"Full BTC History":"Volle BTC-Historie","Halving Cycles":"Halving-Zyklen","ATH Drawdowns":"ATH-Rückgänge","Bottom Recoveries":"Tief-Erholungen","Yearly Candles":"Jahreskerzen"}
        view=st.segmented_control("ZYKLUS-ANSICHT",view_options,format_func=lambda k:view_labels_de[k],default="Full BTC History")
        halvings=[pd.Timestamp("2012-11-28",tz="UTC"),pd.Timestamp("2016-07-09",tz="UTC"),pd.Timestamp("2020-05-11",tz="UTC"),pd.Timestamp("2024-04-20",tz="UTC")]
        if view=="Yearly Candles":
            yearly=frame.resample("YE").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna();yf=go.Figure(go.Candlestick(x=yearly.index,open=yearly.open,high=yearly.high,low=yearly.low,close=yearly.close));yf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log");st.plotly_chart(yf,width="stretch")
            annual=yearly.assign(year=yearly.index.year,ret=yearly.close/yearly.open-1,max_drawdown=yearly.low/yearly.open-1)[["year","open","high","low","close","ret","max_drawdown"]].rename(columns={"ret":"Rendite","max_drawdown":"Max. Rückgang"})
            st.dataframe(annual,hide_index=True)
        elif view=="Halving Cycles":
            cf=go.Figure();hn=cycles.get("halving_normalized",[])
            for i,cycle_item in enumerate(hn):
                pts=pd.DataFrame(cycle_item["points"]);is_current=i==len(hn)-1
                cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized,name=str(cycle_item["halving"])[:10]+(" · CURRENT" if is_current else ""),line={"width":3 if is_current else 1.4,"color":"#f0b44d" if is_current else None}))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Tage seit Halving",yaxis_title="Halving-Preis = 1,0");st.plotly_chart(cf,width="stretch");st.caption("Nur Forschungskontext. Keine mechanische Vier-Jahres-Zyklus-Annahme. Aktueller Zyklus hervorgehoben, nicht extrapoliert.")
        elif view=="ATH Drawdowns":
            cf=go.Figure()
            for item in cycles.get("ath_normalized",[]):
                pts=pd.DataFrame(item["points"]);cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized-1,name=f"Cycle {item['cycle']}"))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Tage seit ATH",yaxis_title="Rückgang");st.plotly_chart(cf,width="stretch")
        elif view=="Bottom Recoveries":
            cf=go.Figure()
            for item in cycles.get("bottom_recovery_normalized",[]):
                pts=pd.DataFrame(item["points"]);cf.add_trace(go.Scatter(x=pts.day,y=pts.normalized,name=f"Cycle {item['cycle']}"))
            cf.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Tage seit Tief",yaxis_title="Tiefpreis = 1,0");st.plotly_chart(cf,width="stretch")
        else:
            cyclefig=go.Figure(go.Scatter(x=frame.index,y=frame.close,line={"color":"#4da3ff","width":1},name="BTC"))
            ath_running=frame.close.cummax();ath_points=frame[frame.close>=ath_running.shift(1).fillna(0)]
            cyclefig.add_trace(go.Scatter(x=ath_points.index,y=ath_points.close,mode="markers",marker={"size":5,"color":"#26c281"},name="Neues ATH"))
            for h in halvings:
                if h>=frame.index.min() and h<=frame.index.max():cyclefig.add_vline(x=h,line_color="#7f8ea3",line_dash="dot",annotation_text="HALVING",annotation_position="top")
            cycle_rows=cycles.get("cycles",[])
            if cycle_rows:latest_cycle=cycle_rows[-1];cyclefig.add_trace(go.Scatter(x=[pd.Timestamp(latest_cycle["major_low"])],y=[latest_cycle["trough_price"]],mode="markers",marker={"size":11,"color":"#ee5a67","symbol":"x"},name="Letztes größeres Tief"))
            cyclefig.add_trace(go.Scatter(x=[frame.index[-1]],y=[live_price],mode="markers+text",text=["JETZT"],textposition="top center",marker={"size":9,"color":"#f0b44d"},name="Aktueller Rückgangspfad"))
            cyclefig.update_layout(height=560,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log",legend={"orientation":"h","y":1.02,"x":0});st.plotly_chart(cyclefig,width="stretch",key="cycles_full_history")
            st.caption("Neue Allzeithochs, Halvings und das aktuelle Zyklustief sind strukturelle Marker, keine Vorhersage des nächsten.")
    with cyc_tabs[0]:
        st.subheader("Elliott · vollständige BTC-Historie · NUR FORSCHUNG / NUR KONTEXT — kein Handelssignal")
        degree_labels=["MACRO","PRIMARY","INTERMEDIATE"];degree_key={"MACRO":"MACRO_CYCLE","PRIMARY":"PRIMARY","INTERMEDIATE":"INTERMEDIATE"};degree_color={"MACRO":"#f0b44d","PRIMARY":"#4da3ff","INTERMEDIATE":"#9b7bff"}
        degrees=st.multiselect("GRADE",degree_labels,default=["MACRO","PRIMARY"],label_visibility="collapsed")
        show_alt=st.toggle("Alternative Zählung einblenden",False)
        piv=pd.DataFrame(macro_e["macro_pivots"]);primary=macro_e["primary"];alt=(macro_e["alternatives"] or [{}])[0];ex=macro_e["explanation"]
        efig=go.Figure(go.Scatter(x=frame.index,y=frame.close,line={"color":"#33475f","width":1},name="BTC"))
        if "MACRO" in degrees and not piv.empty:
            efig.add_trace(go.Scatter(x=piv.timestamp,y=piv.price,mode="markers+text",text=piv.algorithmic_label,textposition="top center",marker={"size":9,"color":degree_color["MACRO"],"symbol":"diamond"},name="MACRO bestätigte Pivots"))
            last_piv=piv.iloc[-1];efig.add_trace(go.Scatter(x=[last_piv.timestamp,frame.index[-1]],y=[last_piv.price,live_price],mode="lines",line={"color":degree_color["MACRO"],"width":2,"dash":"dot"},name="Aktuelle Welle · unbestätigt"))
        for key in ("PRIMARY","INTERMEDIATE"):
            if key in degrees:
                sw=pd.DataFrame(macro_e["hierarchy"][degree_key[key]]["evidence"]["confirmed_swings"])
                if not sw.empty:efig.add_trace(go.Scatter(x=pd.to_datetime(sw.pivot_time),y=sw.price,mode="markers",marker={"size":6,"color":degree_color[key]},name=f"{key} bestätigte Swings"))
        if primary.get("invalidation_level") is not None:efig.add_hline(y=primary["invalidation_level"],line_color="#ee5a67",line_dash="dash",annotation_text=f"MACHT PRIMÄR UNGÜLTIG · ${primary['invalidation_level']:,.0f}",annotation_position="bottom right")
        if primary.get("confirmation_level") is not None:efig.add_hline(y=primary["confirmation_level"],line_color="#26c281",line_dash="dash",annotation_text=f"BESTÄTIGT NÄCHSTE PHASE · ${primary['confirmation_level']:,.0f}",annotation_position="top right")
        if show_alt:
            if alt.get("invalidation_level") is not None:efig.add_hline(y=alt["invalidation_level"],line_color="#9b7bff",line_dash="dot",annotation_text=f"ALT. UNGÜLTIG AB · ${alt['invalidation_level']:,.0f}",annotation_position="bottom left")
            if alt.get("confirmation_level") is not None:efig.add_hline(y=alt["confirmation_level"],line_color="#9b7bff",line_dash="dot",annotation_text=f"ALT. BESTÄTIGUNG · ${alt['confirmation_level']:,.0f}",annotation_position="top left")
        efig.update_layout(height=600,margin={"l":8,"r":8,"t":15,"b":8},paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0","size":10},xaxis={"gridcolor":"#142033"},yaxis={"gridcolor":"#142033","type":"log","side":"right","tickformat":",.0f"},legend={"orientation":"h","y":1.02,"x":0},hovermode="x unified")
        e1,e2=st.columns([3,1])
        with e1:st.plotly_chart(efig,width="stretch",key="elliott_full_history",config={"displaylogo":False,"scrollZoom":True})
        with e2:
            revision_rate=macro_e["quality"].get("historical_revision_rate");revision_text="NICHT VERFÜGBAR" if revision_rate is None else str(revision_rate)
            st.markdown(f"""**PRIMÄRE ZÄHLUNG**  \n{primary.get('name','Unbestätigt')}  \n\n**ALTERNATIVE ZÄHLUNG**  \n{alt.get('name',ex['abc_alternative'])}  \n\n**WELLENANKER / START**  \n{str(ex['wave_start'])[:10]} · {'—' if ex['wave_start_price'] is None else f"${ex['wave_start_price']:,.0f}"}  \n\n**UNGÜLTIG AB**  \n{'—' if primary.get('invalidation_level') is None else f"${primary['invalidation_level']:,.0f}"} · {primary.get('invalidation_reason','—')}  \n\n**BESTÄTIGUNG**  \n{'—' if primary.get('confirmation_level') is None else f"${primary['confirmation_level']:,.0f}"}  \n\n**STABILITÄT DER ZÄHLUNG**  \n{macro_e['quality']['count_stability']}  \n\n**HISTORISCHE REVISIONSRATE**  \n{revision_text}  \n\n**STATUS**  \n{macro_e['status']} · {macro_e['production_role']}""")
            with st.expander("WARUM DIESE ZÄHLUNG?"):
                st.markdown(f"""**Erfüllte Regeln**  \n{' · '.join(primary.get('rules_passed',[])) or '—'}  \n\n**Erfüllte Richtlinien**  \n{' · '.join(primary.get('guidelines_matched',[])) or '—'}  \n\n**Verfehlte Richtlinien**  \n{' · '.join(primary.get('guidelines_missed',[])) or '—'}  \n\n**Fibonacci-Übereinstimmung**  \n{macro_e['quality'].get('fib_alignment','NICHT VERFÜGBAR')}  \n\n**Strukturelle Gültigkeit**  \n{macro_e['quality'].get('structural_validity','NICHT VERFÜGBAR')}  \n\n**Was diese Zählung entkräften würde**  \n{ex['why']}  \n\n**Alternative Interpretation**  \n{ex['abc_alternative']}""")
            st.caption("Elliott bleibt NUR FORSCHUNG / NUR KONTEXT · niemals Treiber für Produktion oder Ausführung · Beschriftungen sind revidierbar")
with tabs[2]:
    hist_tabs=st.tabs(["EINSTIEGS-LABOR","RISIKO / TOP-LABOR"])
    with hist_tabs[0]:
        st.subheader("Historische Analogien · normalisierter Vergleich")
        compare=go.Figure()
        for item in closest[:3]:
            date=pd.Timestamp(item["date"]);date=date.tz_localize("UTC") if date.tzinfo is None else date;path=frame.loc[date-pd.Timedelta(days=90):date+pd.Timedelta(days=365)].close
            if not path.empty:compare.add_trace(go.Scatter(x=[(x-date).days for x in path.index],y=path/path.loc[date],name=str(date.date())))
        compare.update_layout(height=460,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},xaxis_title="Tage seit Einstieg",yaxis_title="Normalisierter Preis");st.plotly_chart(compare,width="stretch");st.caption("Historisches Ergebnis – keine Prognose.")
        signal_book_path=ROOT/"data"/"reports"/"master5_signal_book.csv"
        if signal_book_path.exists():
            book=pd.read_csv(signal_book_path,parse_dates=["timestamp"]);buy_book=book[book.direction=="BUY"] if "direction" in book else book[book.signal.isin(SIGNAL_STYLE)]
            show_failures=st.toggle("FEHLSIGNALE ANZEIGEN",False,key="entry_show_failures")
            entry_view=buy_book if show_failures else buy_book[buy_book.get("false_signal",False)==False]
            st.dataframe(entry_view[[c for c in ("timestamp","signal","price","archetype","return_365d","MAE","false_signal","status") if c in entry_view.columns]].sort_values("timestamp",ascending=False),hide_index=True)
            st.caption(f"{(~buy_book.get('false_signal',pd.Series(dtype=bool))).sum() if 'false_signal' in buy_book else len(buy_book)} historisch erfolgreich · {buy_book.get('false_signal',pd.Series(dtype=bool)).sum() if 'false_signal' in buy_book else 0} fehlgeschlagene Kandidaten · FEHLSIGNALE ANZEIGEN für beide")
        else:
            st.info("Signal-Buch in dieser Umgebung nicht verfügbar.")
    with hist_tabs[1]:
        st.subheader("Historische Top- / Risikoepisoden")
        if signal_book_path.exists():
            risk_book=book[book.direction=="RISK"] if "direction" in book else book.iloc[0:0]
            show_risk_failures=st.toggle("FEHLSIGNALE ANZEIGEN",False,key="risk_show_failures")
            risk_view=risk_book if show_risk_failures else risk_book[risk_book.get("false_signal",False)==False]
            st.dataframe(risk_view[[c for c in ("timestamp","signal","price","archetype","return_365d","MAE","false_signal","status") if c in risk_view.columns]].sort_values("timestamp",ascending=False),hide_index=True)
            st.caption("Historische Verteilung / Top-Risiko-Forschungsepisoden · nur Ergebnisse, niemals eine Vorhersage des nächsten Tops.")
        else:
            st.info("Signal-Buch in dieser Umgebung nicht verfügbar.")
with tabs[3]:
    st.subheader("Zeitpunktgenauer Ereignis-Explorer");categories=sorted(event_rows.category.unique()) if not event_rows.empty else [];selected=st.multiselect("EREIGNISFILTER",categories,default=categories);shown=event_rows[event_rows.category.isin(selected)] if selected else event_rows.iloc[0:0];st.caption(f"{event_health['events']} verifizierte Ereignisse mit Quelle · {event_health['reactions']} ausgereifte BTC-Reaktionen · {event_health['from']} bis {event_health['to']}")
    if not shown.empty:
        event_times=pd.to_datetime(shown.available_at,utc=True);event_prices=frame.close.reindex(event_times,method="ffill");event_fig=go.Figure(go.Scatter(x=frame.index,y=frame.close,name="BTC",line={"color":"#4da3ff","width":1.2}));event_fig.add_trace(go.Scatter(x=event_times,y=event_prices,mode="markers",text=shown.headline,customdata=shown.category,hovertemplate="%{customdata}<br>%{text}<extra></extra>",marker={"color":"#f0b44d","size":9,"symbol":"diamond"},name="Zeitpunktgenaue Ereignisse"));event_fig.update_layout(height=460,paper_bgcolor="#070b12",plot_bgcolor="#070b12",font={"color":"#8d9bb0"},yaxis_type="log");st.plotly_chart(event_fig,width="stretch")
        selected_event=st.selectbox("EREIGNISDETAILS",shown.event_id,format_func=lambda eid:shown.loc[shown.event_id==eid,"headline"].iloc[0]);detail=shown.loc[shown.event_id==selected_event].iloc[0];reactions=event_db.reactions(selected_event);eleft,eright=st.columns([1,2])
        eleft.markdown(f"**EREIGNIS**  \n{detail.headline}  \n\n**DATUM**  \n{detail.event_time}  \n\n**REGIME-EINGANGSZEIT**  \n{detail.available_at}  \n\n**KATEGORIE / WICHTIGKEIT**  \n{detail.category} · {detail.get('importance') or 'NICHT KLASSIFIZIERT'}  \n\n**STATUS**  \n{detail.get('status') or 'NICHT KLASSIFIZIERT'}  \n\n**QUELLENQUALITÄT**  \n{detail.source_quality}  \n\n[QUELLE]({detail.source_url})")
        reaction_24h=reactions.loc[reactions.horizon=="24H","return"].iloc[0] if not reactions.empty and "24H" in reactions.get("horizon",pd.Series()).values else None
        evo=expected_vs_observed(detail.get("expected_direction"),reaction_24h)
        causality=classify_causality(1,True,False)
        eright.dataframe(reactions[[x for x in ("horizon","asset","return","max_drawdown","resolution") if x in reactions]],hide_index=True)
        eright.markdown(f"**ERWARTET VS. BEOBACHTET (24H)**  \n{evo['comparison']} — {evo['note']}  \n\n**KAUSALITÄTS-VERTRAUEN**  \n{causality['causality_level']} — {causality['note']}")
    st.dataframe(shown[["event_time","available_at","category","headline","source_quality","source_name","source_url"]],hide_index=True,column_config={"source_url":st.column_config.LinkColumn("QUELLE")});st.write("Kalenderkontext",state["modules"]["seasonality"]);st.caption("Nur Informationen, die zum Zeitpunkt available_at bekannt waren, sind zulässig. Fehlende historische Fälle bleiben ungeklärt, werden nie erfunden.")
with tabs[4]:
    res_tabs=st.tabs(["MUSTER","SIGNAL-BUCH","DATENQUALITÄT","BACKTEST","AI COPILOT"])
    with res_tabs[0]:
        disc=feeds["fusion_discovery"];patterns_df=pd.DataFrame(disc["patterns"]);stable=patterns_df[patterns_df.longevity=="STABLE"];st.subheader("Stabile historische Muster");st.dataframe(stable[["pattern_id","hypothesis","sample_size","effect_lift","era_coverage","longevity","status"]],hide_index=True);st.metric("Getestete Hypothesen",disc["hypotheses_tested"]);show_rejected=st.toggle("Verworfene Muster anzeigen",False);visible_patterns=patterns_df if show_rejected else patterns_df[(patterns_df.status.isin(["PROMISING","DISCOVERED"]))|(patterns_df.longevity=="STABLE")];st.dataframe(visible_patterns[["pattern_id","hypothesis","sample_size","effect_lift","era_coverage","longevity","status"]],hide_index=True);st.caption("Explorativ, Risiko durch Mehrfachtests: HOCH. RESEARCH_NEXT kann die Live-Entscheidung nicht beeinflussen.")
    with res_tabs[1]:
        p=ROOT/"data"/"reports"/"master5_signal_book.csv";st.dataframe(pd.read_csv(p) if p.exists() else pd.DataFrame(),hide_index=True)
    with res_tabs[2]:st.dataframe(pd.DataFrame(data_status).T)
    with res_tabs[3]:st.info("Forschungsberichte bleiben unter data/reports verfügbar. Die Leitregeln bleiben unverändert.")
    with res_tabs[4]:
        ai=BitcoinAIRouter(values=env_values(ROOT/".env"),cache_dir=ROOT/"runtime"/"ai_cache");st.caption("AI Copilot erklärt nur den Systemzustand · entscheidet niemals · OpenAI ist optional und nur erklärend · AUTOMATISCHER HANDEL DEAKTIVIERT.")
        nano_button,deep_button=st.columns(2)
        if nano_button.button("AKTUELLE KURZFASSUNG",use_container_width=True):st.session_state["p8_nano"]=ai.explain("NANO",state)
        if deep_button.button("TIEFENANALYSE",use_container_width=True):st.session_state["p8_analysis"]=ai.explain("ANALYSIS",state,deep=True)
        for key,title in (("p8_nano","KURZFASSUNG"),("p8_analysis","TIEFENANALYSE")):
            result=st.session_state.get(key)
            if result:
                st.subheader(title);st.write(result.text);st.caption(f"{result.model or 'deterministischer Fallback'} · {result.status} · Cache={'TREFFER' if result.cached else 'KEIN TREFFER'} · Widerspruch={result.contradiction_guard} · Halluzination={result.hallucination_guard}")
with tabs[5]:
    st.subheader("SYSTEMZUSTAND")
    heartbeat=ROOT/"runtime"/"production8"/"heartbeat.json";watcher_age=None if not heartbeat.exists() else pd.Timestamp.now(tz="UTC").timestamp()-heartbeat.stat().st_mtime
    ai=ai if "ai" in dir() else BitcoinAIRouter(values=env_values(ROOT/".env"),cache_dir=ROOT/"runtime"/"ai_cache")
    usage=ai.usage_today();health_rows=[
        {"Komponente":"MT5 / BTC-Tick","Status":f"{live['status']} / {translate_freshness(tick.get('freshness','OFFLINE'))}","Herkunft":"MetaTrader 5"},
        {"Komponente":"Bestätigt H4 / D1 / W1","Status":" / ".join("AKTUELL" if live.get(key) is not None else "NICHT VERFÜGBAR" for key in ("last_confirmed_h4","last_confirmed_d1","last_confirmed_w1")),"Herkunft":"MT5, nur geschlossene Kerzen"},
        {"Komponente":"Production-8-Watcher","Status":"ONLINE" if watcher_age is not None and watcher_age<180 else "OFFLINE","Herkunft":"runtime/production8/heartbeat.json"},
        {"Komponente":"Ereignis-Datenbank","Status":"ONLINE" if event_health.get('events',0)>0 else "UNZUREICHENDE DATEN","Herkunft":"Primärquellen-Datenbank (zeitpunktgenau)"},
        {"Komponente":"Forward Ledger","Status":"ONLINE","Herkunft":"Append-only SQLite"},
        {"Komponente":"OpenAI","Status":"AKTIVIERT" if ai.enabled else "DEAKTIVIERT","Herkunft":f"{ai.models['NANO']} / {ai.models['ANALYSIS']}"},
        {"Komponente":"Automatischer Handel","Status":"DEAKTIVIERT","Herkunft":"Fest gesperrt"},
        {"Komponente":"Telegram Signal-Alerts","Status":telegram_progress_status,"Herkunft":telegram_progress_source},
    ];st.dataframe(pd.DataFrame(health_rows),hide_index=True,use_container_width=True)
    st.subheader("AI HEUTE");u1,u2,u3,u4,u5=st.columns(5);u1.metric("Anfragen",usage["calls"]);u2.metric("Nano",usage["nano_requests"]);u3.metric("Tiefenanalyse",usage["deep_requests"]);u4.metric("Cache-Treffer",usage["cache_hits"]);u5.metric("Kosten",f"${usage['estimated_cost_usd']:.4f}")
    st.caption(f"Tokens: {usage['input_tokens']:,} Eingabe · {usage['output_tokens']:,} Ausgabe · Fallbacks: {usage['fallbacks']} · Eingefrorene Engines unverändert")
    st.divider();st.subheader("Maschinenlesbarer Zustand · nur Forschungsexporte")
    registry=rule_registry(macro7);indicator_state=build_indicator_state_v1(state,macro7)
    reg_col,ind_col=st.columns(2)
    with reg_col:
        st.markdown("**Regelverzeichnis**");st.caption(f"{len(registry['scenarios'])} Szenarioregeln · {len(registry['zones'])} Zonendefinitionen")
        st.download_button("rule_registry.json herunterladen",json.dumps(registry,indent=2,default=str),file_name="rule_registry.json",mime="application/json")
    with ind_col:
        st.markdown("**BitcoinIndicatorStateV1**");st.caption(f"signal_state={indicator_state['signal_state']} · evidence={indicator_state['evidence']}")
        st.download_button("indicator_state.json herunterladen",json.dumps(indicator_state,indent=2,default=str),file_name="indicator_state.json",mime="application/json")
    st.markdown("**Pine / MQL5 Fähigkeitsmatrix (nur Export)**")
    st.dataframe(pd.DataFrame(PINE_MQL_CAPABILITY_MATRIX),hide_index=True)
    st.caption("Nur Fähigkeitsmatrix — es wird kein Pine-Script- oder MQL5-Code erzeugt. AUTOMATISCHER HANDEL bleibt in jedem Fall DEAKTIVIERT.")
    st.divider();st.subheader("Entscheidungs-Regelverzeichnis")
    st.dataframe(pd.DataFrame(DECISION_RULE_REGISTRY),hide_index=True,use_container_width=True)
    st.download_button("decision_state.json herunterladen",json.dumps(decision_intel,indent=2,default=str),file_name="decision_state.json",mime="application/json")
    st.caption(f"{len(DECISION_RULE_REGISTRY)} prüfbare Entscheidungsregeln · jeder DecisionState lässt sich hier auf eine rule_id zurückführen · Elliott bleibt NUR FORSCHUNG / NUR KONTEXT")
