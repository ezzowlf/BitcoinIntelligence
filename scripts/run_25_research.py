from __future__ import annotations
import json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.advanced import HistoricalZoneEngine,DrawdownCycleEngine,multi_timeframe_indicators
from bitcoin_cycle_analyzer.rare_signals import build_historical_signal_book
from bitcoin_cycle_analyzer.seasonality.event_windows import event_window_statistics
import bitcoin_intelligence


def pct(value):return "n/a" if value is None or pd.isna(value) else f"{value:.2%}"
def main():
    config=load_config(ROOT/"config.yaml");frame=OHLCVStore(ROOT/config["data"]["database"]).load("1d");zones=HistoricalZoneEngine().analyze(frame);draw=DrawdownCycleEngine().analyze(frame);momentum=multi_timeframe_indicators(frame);book=build_historical_signal_book(frame);state,_=bitcoin_intelligence.state();rare=state["rare_signal"]
    reports=ROOT/"data"/"reports";reports.mkdir(parents=True,exist_ok=True);book.to_csv(reports/"historical_signal_book_25.csv",index=False)
    frequency=book.assign(year=pd.to_datetime(book.date).dt.year).pivot_table(index="year",columns="signal_type",values="signal_id",aggfunc="count",fill_value=0).astype(int) if not book.empty else pd.DataFrame()
    holidays={name:{window:event_window_statistics(frame,name,before=window,after=window) for window in (7,14,21)} for name in ("thanksgiving","black_friday","christmas","new_year")}
    payload={"status":"RESEARCH_ONLY","challenger":rare,"zones":zones,"drawdown":draw,"momentum":momentum,"signal_frequency":frequency.to_dict(orient="index"),"holiday_studies":holidays,"geopolitical":{"status":"UNAVAILABLE","reason":"NO_PIT_EVENT_LIBRARY; no events invented"},"ablation":{"FULL":"RESEARCH","FULL_MINUS_HISTORICAL_ZONES":"NOT_IDENTIFIABLE_WITHOUT_FORWARD_SAMPLE","FULL_MINUS_RSI":"NOT_IDENTIFIABLE_WITHOUT_FORWARD_SAMPLE","FULL_MINUS_BOLLINGER":"NOT_IDENTIFIABLE_WITHOUT_FORWARD_SAMPLE","FULL_MINUS_DRAWDOWN":"NOT_IDENTIFIABLE_WITHOUT_FORWARD_SAMPLE"}}
    (reports/"intelligence_25_research.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
    cycles=draw["cycles"]
    lines=["# Bitcoin Drawdown and Recovery Study","","Status: `RESEARCH_ONLY`.","","| Peak date | Peak price | Trough date | Trough price | Drawdown | Days to trough | Days to ATH recovery | Recovery |","|---|---:|---|---:|---:|---:|---:|---:|"]
    for c in cycles:lines.append(f"| {pd.Timestamp(c['peak_date']).date()} | ${c['peak_price']:,.2f} | {pd.Timestamp(c['trough_date']).date()} | ${c['trough_price']:,.2f} | {pct(c['drawdown'])} | {c['days_to_trough']} | {c['days_to_ath_recovery'] or 'not recovered'} | {pct(c['recovery_gain'])} |")
    lines+= ["",f"Maximum historical drawdown: **{pct(draw['maximum_historical_drawdown'])}**.",f"Current drawdown: **{pct(draw['current_drawdown'])}**, severity percentile **{draw['historical_severity_percentile']:.2f}**.",f"Current recovery from the last major low: **{pct(draw['recovery_from_major_low'])}**. State: **{draw['state']}**.","","Cycles are detected algorithmically from the visible price history; no desired dates or results are hard-coded."]
    (ROOT/"BITCOIN_DRAWDOWN_RECOVERY_STUDY.md").write_text("\n".join(lines),encoding="utf-8")
    zone_lines=["# Bitcoin Historical Zones Study","","Status: `RESEARCH_ONLY`; every zone forms only after the confirming future pivot window has closed.","","| Type | Range | Strength | Confidence | Independent touches | Failures | First known | Last confirmed |","|---|---:|---:|---|---:|---:|---|---|"]
    for z in zones:zone_lines.append(f"| {z['zone_type']} | ${z['lower_bound']:,.2f}-${z['upper_bound']:,.2f} | {z['strength']:.1f} | {z['confidence']} | {z['touch_count']} | {z['failed_reactions']} | {pd.Timestamp(z['first_seen']).date()} | {pd.Timestamp(z['last_confirmed']).date()} |")
    zone_lines += ["","Repeated observations within 21 days count as one independent reaction. Zone width comes from observed ATR and reaction dispersion. Later touches create a new version; they do not change the historical version retroactively."]
    (ROOT/"BITCOIN_HISTORICAL_ZONES_STUDY.md").write_text("\n".join(zone_lines),encoding="utf-8")
    summary={"signals":len(book),"production":int((book.level=="PRODUCTION").sum()) if not book.empty else 0,"candidate":int((book.level=="CANDIDATE").sum()) if not book.empty else 0,"frequency":frequency.to_dict(orient="index"),"zones":len(zones),"supports":sum("SUPPORT" in z["zone_type"] for z in zones),"resistances":sum("RESISTANCE" in z["zone_type"] for z in zones),"drawdown_cycles":len(cycles)};print(json.dumps(summary,indent=2,default=str))
if __name__=="__main__":main()
