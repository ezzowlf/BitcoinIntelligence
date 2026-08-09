from __future__ import annotations
import sqlite3
import pandas as pd
from bitcoin_cycle_analyzer.macro.contracts import MacroObservation
from bitcoin_cycle_analyzer.macro.store import MacroReleaseStore
from bitcoin_cycle_analyzer.news.meanpulse_sqlite import event_chains, transmission_state
from bitcoin_cycle_analyzer.news.ingestion import parse_meanpulse_event
from bitcoin_cycle_analyzer.scoring import confluence_score, evidence_score_v22
from bitcoin_cycle_analyzer.explainability import explain_state


def test_macro_store_vintage_selection_and_duplicates(tmp_path):
    store=MacroReleaseStore(tmp_path/"macro.db"); period=pd.Timestamp("2024-01-01",tz="UTC")
    release=pd.Timestamp("2024-02-10",tz="UTC"); record=MacroObservation("cpi",period,period,3.1,release,release,"initial","alfred")
    store.upsert([record,record]); assert store.as_of("cpi",release-pd.Timedelta(seconds=1)).empty
    assert len(store.as_of("cpi",release))==1 and store.health()["duplicates"]==0


def event(version,available):
    return parse_meanpulse_event({"event_id":f"story:v{version}","event_time":"2024-01-01T00:00:00Z","available_at":available,
        "category":"WAR_ESCALATION","severity":.8,"risk_direction":"RISK_OFF","btc_direction":"UNKNOWN",
        "confidence":.7,"source":"meanpulse-news"})


def test_news_update_chains_preserve_versions_and_transmission_context_only():
    chains=event_chains([event(2,"2024-01-01T01:00:00Z"),event(1,"2024-01-01T00:05:00Z")])
    assert [e.event for e in chains["story"]]==["story:v1","story:v2"]
    assert transmission_state(chains["story"][0])["btc"]=="UNKNOWN"
    assert transmission_state(chains["story"][0])["signal"]=="CONTEXT_ONLY"


def test_confluence_missing_groups_not_negative_and_evidence_penalizes_coverage():
    one=confluence_score([{"name":"price","group":"price","strength":.5},{"name":"etf","status":"UNAVAILABLE","strength":-1}])
    assert one["score"]==75 and one["independent_groups"]==1
    low=evidence_score_v22(2,1,.2,100,.5,1,1,.5)["score"]
    high=evidence_score_v22(6,1,1,100,.5,1,1,.5)["score"]
    assert low<high


def test_explainability_is_rule_based_and_execution_disabled():
    state={"technical":{"states":{}},"dimensions":{"long_term_value":72},"cycle":{"primary_regime":"TRANSITION"},
           "drawdown_risk":{"label":"HIGH"},"entry_timing":"WAIT",
           "modules":{"derivatives":{"risk_score":50,"modules":{"open_interest":{"level":"NORMAL"}}},"macro":{"status":"UNAVAILABLE"}}}
    result=explain_state(state)
    assert result["entry_trigger"]["execution"]=="DISABLED"
    assert "price_structure_reclaim" in result["what_would_improve"]
