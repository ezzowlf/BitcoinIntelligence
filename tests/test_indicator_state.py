import pandas as pd
from pathlib import Path

from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.indicator_state import build_decision_state_v1, build_indicator_state_v1, rule_registry, PINE_MQL_CAPABILITY_MATRIX

ROOT = Path(__file__).resolve().parents[1]


def _state():
    config = load_config(ROOT / "config.yaml")
    store = OHLCVStore(ROOT / config["data"]["database"])
    frame = store.load("1d")
    external = ExternalMetricStore(ROOT / config["data"]["external_database"])
    feeds = {
        "onchain_provider": StoreOnChainProvider(external),
        "four_hour": store.load("4h"),
        "funding": external.load("funding_rate_8h"),
        "open_interest": external.load("open_interest_usd"),
        "etf": external.load("etf_net_flow_usd"),
        "macro": {},
        "live_market": {"status": "UNAVAILABLE"},
        "price_provider": "test",
        "project_root": ROOT,
        "fusion_discovery": HistoricalPatternDiscoveryEngine().discover(frame),
    }
    return analyze_intelligence(frame, config, feeds=feeds), frame


def test_decision_state_v1_is_view_only_and_execution_disabled():
    state, frame = _state()
    macro7 = state["macro7"]
    active = next((x for x in macro7["scenarios"] if x["status"] == "ACTIVE"), macro7["scenarios"][0])
    decision = build_decision_state_v1(state, macro7, float(frame.close.iloc[-1]), active, "EARLY")
    assert decision["version"] == "BitcoinDecisionStateV1"
    assert decision["execution"] == "DISABLED"
    assert decision["current_scenario"]["name"] == active["name"]


def test_indicator_state_v1_schema_matches_spec_fields():
    state, frame = _state()
    macro7 = state["macro7"]
    indicator = build_indicator_state_v1(state, macro7)
    for field in ("timestamp", "symbol", "timeframe", "signal_type", "signal_state", "entry_zone", "risk_zone", "invalidation", "evidence", "historical_quality", "cycle", "regime"):
        assert field in indicator
    assert indicator["execution"] == "DISABLED"


def test_rule_registry_reflects_macro7_without_mutating_it():
    state, frame = _state()
    macro7 = state["macro7"]
    before = len(macro7["scenarios"])
    registry = rule_registry(macro7)
    assert len(macro7["scenarios"]) == before
    assert registry["execution"] == "DISABLED"
    assert len(registry["scenarios"]) == before


def test_pine_mql_capability_matrix_never_marks_execution_ready():
    for row in PINE_MQL_CAPABILITY_MATRIX:
        if "execution" in row["capability"].lower() or "order" in row["capability"].lower():
            assert "NOT PLANNED" in row["pine"] and "NOT PLANNED" in row["mql5"]
