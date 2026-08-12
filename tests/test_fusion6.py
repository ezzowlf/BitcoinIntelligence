from pathlib import Path
import pandas as pd
import pytest
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine,HistoricalEventStore
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.config import load_config

@pytest.fixture
def discovery(ohlcv):return HistoricalPatternDiscoveryEngine(minimum_sample=5).discover(ohlcv)

def test_discovery_is_pit_and_multiple_testing_explicit(discovery):
    assert discovery["status"]=="RESEARCH_ONLY" and discovery["hypotheses_tested"]==72
    assert discovery["multiple_testing"]["production_promotion"] is False
    assert all(p["discovered_at"]<=discovery["coverage"]["price_end"] for p in discovery["patterns"])

def test_backwards_windows_never_use_future(discovery):
    for study in discovery["reverse_studies"].values():
        for event in study["windows"]:
            assert all(key.startswith("T-") or key=="event_time" for key in event)

def test_regime_conditioning_and_rule_survival(discovery):
    assert all("regimes" in p and p["longevity"] in {"ONE_ERA","MULTI_ERA","STABLE","INSUFFICIENT_DATA"} for p in discovery["patterns"])

def test_rejected_registry_and_independence_groups(discovery):
    assert discovery["rejected_registry"]
    assert all(len(p["independence_groups"])>=1 for p in discovery["patterns"])

def test_fusion_state_uses_domain_routing_not_average(ohlcv):
    state=analyze_intelligence(ohlcv,load_config("config.yaml"));f=state["fusion6"]
    assert f["model"]=="FUSION_6_RESEARCH_CHALLENGER" and "domain_ownership" in f
    assert f["execution"]=="DISABLED" and f["status"]=="RESEARCH_CHALLENGER"

def test_event_store_is_pit_and_requires_source(tmp_path):
    store=HistoricalEventStore(tmp_path/"events.db");eid=store.append("Verified event","FED","2020-01-01T12:00Z","2020-01-01T12:05Z","https://example.com/source","HIGH")
    assert store.as_of("2020-01-01T12:04Z").empty and len(store.as_of("2020-01-01T12:05Z"))==1
    with pytest.raises(ValueError):store.append("bad","FED","2020-01-01T12:00Z","2020-01-01T11:00Z","https://example.com","LOW")
    with pytest.raises(ValueError):store.append("bad","FED","2020-01-01T12:00Z","2020-01-01T12:00Z","unsourced","LOW")

def test_active_pattern_completion_is_not_probability(ohlcv,discovery):
    state=analyze_intelligence(ohlcv,load_config("config.yaml"),feeds={"fusion_discovery":discovery});completion=state["fusion6"]["pattern_completion"]
    assert completion is None or completion["probability"] is False
