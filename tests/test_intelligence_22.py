from __future__ import annotations
import json
import pandas as pd

from bitcoin_cycle_analyzer.coverage import factor_availability
from bitcoin_cycle_analyzer.flows.etf import analyze_etf_flows
from bitcoin_cycle_analyzer.macro.contracts import MacroObservation
from bitcoin_cycle_analyzer.macro.engine import analyze_macro
from bitcoin_cycle_analyzer.news.ingestion import load_meanpulse_jsonl, parse_meanpulse_event
from bitcoin_cycle_analyzer.news.event_model import decay_weight
from bitcoin_cycle_analyzer.scoring import evidence_score_v22
from bitcoin_cycle_analyzer.validation.matrix import empty_validation_matrix, ablation_plan


def test_macro_release_timestamp_blocks_early_use():
    frame=pd.DataFrame({"value":[3.0],"observed_at":[pd.Timestamp("2024-07-01",tz="UTC")],
                        "available_at":[pd.Timestamp("2024-08-10",tz="UTC")],"provider":["alfred"]})
    assert analyze_macro({"cpi":frame},pd.Timestamp("2024-08-09",tz="UTC"))["metrics"]["cpi"]["status"]=="UNAVAILABLE"
    assert analyze_macro({"cpi":frame},pd.Timestamp("2024-08-10",tz="UTC"))["metrics"]["cpi"]["status"]=="AVAILABLE"
    record=MacroObservation("cpi",frame.observed_at[0],frame.observed_at[0],3.0,frame.available_at[0],frame.available_at[0],"initial","alfred")
    assert record.release_time==record.available_at


def test_etf_available_at_and_missing_days():
    dates=pd.to_datetime(["2024-01-01","2024-01-03"],utc=True)
    frame=pd.DataFrame({"net_flow_usd":[10,-5],"available_at":dates+pd.Timedelta(hours=6),"provider":"test"})
    early=analyze_etf_flows(frame,pd.Timestamp("2024-01-03 05:00",tz="UTC"))
    assert early["daily"]==10
    assert analyze_etf_flows(frame,pd.Timestamp("2024-01-04",tz="UTC"))["daily"]==-5


def test_meanpulse_ingestion_availability_and_decay(tmp_path):
    payload={"event_id":"e1","event_time":"2024-01-01T10:00:00Z","available_at":"2024-01-01T10:05:00Z",
             "category":"WAR_ESCALATION","severity":.8,"market_scope":["BTC","OIL"],"risk_direction":"RISK_OFF",
             "btc_direction":"UNKNOWN","confidence":.7,"source":"meanpulse-news"}
    event=parse_meanpulse_event(payload)
    assert event.btc_direction.value=="unknown" and decay_weight(event,pd.Timestamp("2024-01-02",tz="UTC"))>0
    path=tmp_path/"events.jsonl"; path.write_text(json.dumps(payload),encoding="utf-8")
    assert load_meanpulse_jsonl(path,pd.Timestamp("2024-01-01 10:04",tz="UTC"))==[]


def test_provider_outage_inputs_are_stable():
    result=analyze_macro(None,pd.Timestamp("2024-01-01",tz="UTC"))
    assert result["status"]=="UNAVAILABLE" and result["state"]["overall"]=="UNAVAILABLE"


def test_evidence_22_and_validation_matrix():
    evidence=evidence_score_v22(6,.8,.7,100,.6,.5,1,.7)
    assert set(evidence["components"])=={"independent_groups","data_quality","historical_coverage","sample_size","oos_value","provider_agreement","point_in_time_quality","regime_coverage"}
    matrix=empty_validation_matrix()
    assert len(matrix)==7 and matrix["CORE"]["independent_episodes"]==0
    assert "FULL - MACRO" in ablation_plan({"MACRO","ONCHAIN"})


def test_availability_freshness():
    coverage=pd.DataFrame([{"metric":"oi","provider":"x","min_time":"2024-01-01","max_time":"2024-01-03","rows":3}])
    result=factor_availability(coverage,pd.Timestamp("2024-01-05",tz="UTC"))
    assert result.iloc[0].freshness=="DELAYED"
