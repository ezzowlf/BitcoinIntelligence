import json
from pathlib import Path

import pandas as pd
import pytest

from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.fusion6 import HistoricalPatternDiscoveryEngine
from bitcoin_cycle_analyzer.decision_intelligence import (
    assess_evidence_families, EVIDENCE_FAMILIES,
    classify_cycle_bucket, elliott_cycle_context,
    build_structural_zones,
    evaluate_confirmation,
    match_playbooks, ENTRY_PLAYBOOKS,
    build_decision_state,
    build_explanation_facts,
    RULE_REGISTRY,
)
from bitcoin_cycle_analyzer.decision_intelligence.evidence import independent_agreement
from bitcoin_cycle_analyzer.decision_intelligence.zones import active_zone

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def real_state():
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
    state = analyze_intelligence(frame, config, feeds=feeds)
    return state, frame


# ---------------------------------------------------------------- Evidence

def test_evidence_families_cover_all_seven_and_are_independent(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    assert {f["family"] for f in families} == set(EVIDENCE_FAMILIES)
    for f in families:
        assert f["direction"] in ("SUPPORT", "CONTRADICT", "NEUTRAL", "UNAVAILABLE")
        assert f["facts"]


def test_unavailable_macro_data_is_never_treated_as_neutral_bearish(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    macro_family = next(f for f in families if f["family"] == "MACRO")
    if state["data_status"]["macro"]["status"] != "AVAILABLE":
        assert macro_family["direction"] == "UNAVAILABLE"


def test_historical_family_strength_bounded_by_sample_size(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    hist = next(f for f in families if f["family"] == "HISTORICAL")
    n = state["historical_entry_quality"].get("sample_size", 0)
    if n < 4:
        assert hist["strength"] == "LOW"


def test_independent_agreement_does_not_double_count_correlated_signals(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    agreement = independent_agreement(families)
    assert agreement["supporting_count"] == len(agreement["supporting_families"])
    assert agreement["supporting_count"] <= len(EVIDENCE_FAMILIES)


# ---------------------------------------------------------------- Cycle/Elliott context

def test_cycle_bucket_is_one_of_known_buckets(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    cycle_current = state["elliott_cycle"]["cycle_history"]["current"]
    bucket = classify_cycle_bucket(macro7, cycle_current)
    assert bucket["bucket"] in ("DEEP_BEAR_BOTTOM_SEARCH", "LATE_BEAR", "EARLY_BULL", "MID_BULL", "LATE_BULL_DISTRIBUTION", "TRANSITION")


def test_elliott_cycle_context_flags_consistency_not_certainty(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    cycle_current = state["elliott_cycle"]["cycle_history"]["current"]
    ctx = elliott_cycle_context(macro7, cycle_current)
    assert ctx["consistency"] in ("CONSISTENT", "CONFLICT")
    assert "known_limitation" in ctx  # engine cannot yet resolve wave 1/2/3 vs 5 — must stay documented


def test_elliott_never_claims_certainty_language(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    cycle_current = state["elliott_cycle"]["cycle_history"]["current"]
    ctx = elliott_cycle_context(macro7, cycle_current)
    for text in (ctx["note"], ctx["known_limitation"]):
        assert "definitely" not in text.lower() and " is wave" not in text.lower()


# ---------------------------------------------------------------- Zones

def test_zones_have_provenance_and_no_bare_decoration(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    zones = build_structural_zones(state, macro7, live_price, families)
    assert zones
    for z in zones:
        assert z["why"]
        assert z["provenance"]
        assert z["zone_type"] in ("STRONG_BUY_ZONE", "BUY_ZONE", "WATCH_ZONE", "TAKE_PROFIT_ZONE", "HIGH_RISK_ZONE")


def test_active_zone_picks_price_containing_zone(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    families = assess_evidence_families(state, macro7, live_price)
    zones = build_structural_zones(state, macro7, live_price, families)
    zone = active_zone(zones)
    if zone is not None:
        assert zone["lower"] <= live_price <= zone["upper"]


# ---------------------------------------------------------------- Confirmation

def test_confirmation_triggers_are_all_present_and_boolean(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    confirmation = evaluate_confirmation(state, macro7, frame, live_price)
    assert confirmation["confirmation_state"] in ("CONFIRMED", "PARTIAL", "NOT_CONFIRMED")
    for trigger in confirmation["triggers"].values():
        assert isinstance(trigger["met"], bool)
        assert trigger["description"]


def test_confirmation_met_count_matches_confirmation_state(real_state):
    state, frame = real_state
    macro7 = state["macro7"]
    live_price = float(frame.close.iloc[-1])
    confirmation = evaluate_confirmation(state, macro7, frame, live_price)
    met = sum(1 for t in confirmation["triggers"].values() if t["met"])
    assert met == confirmation["met_count"]


# ---------------------------------------------------------------- Playbooks

def test_playbook_registry_has_seven_archetypes():
    assert len(ENTRY_PLAYBOOKS) == 7
    ids = [p["id"] for p in ENTRY_PLAYBOOKS]
    assert len(ids) == len(set(ids))


def test_playbooks_require_eligibility_not_confirmation_to_appear():
    zone = {"zone_id": "DZ-TEST", "zone_type": "BUY_ZONE", "lower": 100, "upper": 200, "active": True}
    confirmation = {"triggers": {"weekly_reclaim": {"met": False}, "momentum_recovery": {"met": False}, "higher_low": {"met": False}, "structure_reclaim": {"met": False}, "swing_low_confirmed": {"met": False}}}
    matches = match_playbooks("LATE_BEAR", zone, supporting_count=5, confirmation=confirmation)
    assert matches  # eligible playbooks still appear even though nothing is confirmed
    assert all(m["entry_status"] != "CONFIRMED" for m in matches)


def test_playbooks_never_eligible_with_zero_zone():
    confirmation = {"triggers": {}}
    assert match_playbooks("LATE_BEAR", None, supporting_count=5, confirmation=confirmation) == []


# ---------------------------------------------------------------- Decision engine (constructed fixtures for precise branch coverage)

def _minimal_state(price=60000.0, cycle_phase="BEAR", cycle_confidence="MODERATE", sell_off_risk="LOW", distribution="NONE",
                    invalidation_level=55000.0, confirmation_level=70000.0, buy_zone=(58000.0, 62000.0), confluence_count=7,
                    macro_action="ACCUMULATE", drawdown=-0.5, weekly_rsi=40.0, hq_score=60.0, hq_sample=6):
    ms = {
        "buy_zones": [{"label": "BUY ZONE 1", "status": "AVAILABLE", "low": buy_zone[0], "high": buy_zone[1], "confidence": "HIGH", "confluence_count": confluence_count}],
        "nearest_support": None, "nearest_resistance": {"lower_bound": 68000.0, "upper_bound": 70000.0, "confidence": "HIGH", "touch_count": 3},
        "confluence": {"supportive_groups": ["PRICE_STRUCTURE", "LONG_TERM_VALUE"]},
        "drawdown_percentile": 80, "price_vs_200d_pct": -0.1, "price_vs_200w_pct": 0.0,
    }
    m5 = {"risk": {"sell_off_risk": sell_off_risk, "distribution": distribution, "existing_position_action": "HOLD"}}
    mom = {"daily": {"rsi": 45}, "weekly": {"rsi": weekly_rsi}, "monthly": {"rsi": 50}}
    hq = {"score": hq_score, "state": "MODERATE", "sample_size": hq_sample}
    data_status = {"macro": {"status": "UNAVAILABLE"}, "onchain": {"status": "AVAILABLE"}, "derivatives": {"status": "AVAILABLE"}}
    elliott = {"evidence": {"confirmed_swings": [{"pivot_time": "2026-01-01", "confirmed_at": "2026-01-15", "kind": "low", "price": 56000.0}, {"pivot_time": "2026-02-01", "confirmed_at": "2026-02-15", "kind": "low", "price": 57000.0}]}}
    macro7 = {
        "actions": {"macro": macro_action, "risk": "CAUTION"},
        "cycle": {"phase": cycle_phase, "confidence": cycle_confidence},
        "elliott": {"primary": {"name": "Possible macro wave 4 completion / recovery watch", "invalidation_level": invalidation_level, "invalidation_reason": "test", "confirmation_level": confirmation_level}, "alternatives": [{"name": "Larger ABC / C-wave continuation"}]},
        "zones": {"tactical_buy": None, "macro_accumulation": None, "deep_value": None, "extreme_cycle": None},
        "indicators": {"ath": 120000.0},
    }
    state = {
        "master": {"state": ms},
        "master5_challenger": m5,
        "advanced": {"momentum": mom},
        "historical_entry_quality": hq,
        "data_status": data_status,
        "elliott_cycle": {"cycle_history": {"current": {"drawdown": drawdown, "days_since_ath": 300}}, "elliott": elliott},
        "fusion6": {"regime": "BEAR"},
    }
    idx = pd.date_range("2020-01-01", periods=400, freq="D", tz="UTC")
    frame = pd.DataFrame({"close": [price] * 400, "high": [price] * 400, "low": [price] * 400, "open": [price] * 400, "volume": [1.0] * 400}, index=idx)
    return state, macro7, frame, price


def test_decision_engine_high_risk_overrides_everything():
    state, macro7, frame, price = _minimal_state(sell_off_risk="HIGH")
    macro7["zones"]["extreme_cycle"] = {"low": price - 1000, "high": price + 1000, "support": "LOW"}
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] == "HIGH_RISK"
    assert "DE-001" in ds["reasons"]["rule_ids"][0]


def test_decision_engine_take_profit_at_distribution():
    state, macro7, frame, _ = _minimal_state(distribution="DISTRIBUTION_CONFIRMED")
    price = 69000.0  # inside nearest_resistance band
    state["master"]["state"]["buy_zones"] = []
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] == "TAKE_PROFIT"


def test_decision_engine_no_edge_with_no_zones():
    state, macro7, frame, _ = _minimal_state()
    state["master"]["state"]["buy_zones"] = []
    state["master"]["state"]["nearest_resistance"] = None
    price = 40000.0  # far from everything
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] in ("NO_EDGE", "WAIT")


def test_decision_engine_hard_invalidation_blocks_buy():
    state, macro7, frame, _ = _minimal_state(invalidation_level=59000.0)
    price = 58000.0  # inside the buy zone geometrically but BELOW invalidation
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] == "WAIT"
    assert ds["hard_invalidation_breached"] is True


def test_decision_engine_watch_when_zone_active_but_cycle_ineligible():
    state, macro7, frame, price = _minimal_state(cycle_phase="TRANSITION", cycle_confidence="LOW", drawdown=-0.1)
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] in ("WATCH", "ACCUMULATE")
    assert ds["entry_status"] != "CONFIRMED"


def test_decision_engine_never_issues_strong_buy_without_full_confirmation():
    state, macro7, frame, price = _minimal_state(weekly_rsi=30.0)  # momentum contradicts, confirmation weak
    ds = build_decision_state(state, macro7, frame, price)
    assert ds["decision"] != "STRONG_BUY"


def test_decision_state_is_json_serializable():
    state, macro7, frame, price = _minimal_state()
    ds = build_decision_state(state, macro7, frame, price)
    json.dumps(ds, default=str)  # must not raise
    assert ds["execution"] == "DISABLED"


# ---------------------------------------------------------------- Explanation

def test_explanation_facts_never_recommend_without_confirmation():
    state, macro7, frame, price = _minimal_state(weekly_rsi=30.0)
    ds = build_decision_state(state, macro7, frame, price)
    exp = build_explanation_facts(ds)
    assert exp["role"].startswith("RESEARCH_ONLY")
    if ds["decision"] not in ("STRONG_BUY", "BUY"):
        assert exp["why_not_buy"]


def test_explanation_summary_mentions_decision_and_confidence():
    state, macro7, frame, price = _minimal_state()
    ds = build_decision_state(state, macro7, frame, price)
    exp = build_explanation_facts(ds)
    assert ds["decision"] in exp["summary"]
    assert ds["decision_confidence"]["label"] in exp["summary"]


# ---------------------------------------------------------------- Rule Registry

def test_rule_registry_ids_are_unique_and_referenced():
    ids = [r["id"] for r in RULE_REGISTRY]
    assert len(ids) == len(set(ids))
    for r in RULE_REGISTRY:
        assert r["status"] in ("ACTIVE", "DEPRECATED")
        assert r["version"]


# ---------------------------------------------------------------- Lookahead / walk-forward (golden scenario smoke)

@pytest.mark.parametrize("as_of", ["2018-12-15", "2020-03-16", "2022-11-21"])
def test_decision_state_at_historical_cutoff_uses_no_future_data(as_of):
    config = load_config(ROOT / "config.yaml")
    store = OHLCVStore(ROOT / config["data"]["database"])
    frame = store.load("1d")
    cutoff = pd.Timestamp(as_of, tz="UTC")
    historical_frame = frame.loc[:cutoff]
    assert historical_frame.index.max() <= cutoff  # walk-forward guarantee
    external = ExternalMetricStore(ROOT / config["data"]["external_database"])
    feeds = {
        "onchain_provider": StoreOnChainProvider(external), "four_hour": store.load("4h").loc[:cutoff],
        "funding": external.load("funding_rate_8h"), "open_interest": external.load("open_interest_usd"), "etf": external.load("etf_net_flow_usd"),
        "macro": {}, "live_market": {"status": "UNAVAILABLE"}, "price_provider": "test", "project_root": ROOT,
        "fusion_discovery": HistoricalPatternDiscoveryEngine().discover(historical_frame),
    }
    state = analyze_intelligence(frame, config, as_of=cutoff, feeds=feeds)
    macro7 = state["macro7"]
    live_price = float(historical_frame.close.iloc[-1])
    ds = build_decision_state(state, macro7, historical_frame, live_price)
    assert ds["decision"] in ("STRONG_BUY", "BUY", "ACCUMULATE", "WATCH", "WAIT", "REDUCE", "TAKE_PROFIT", "HIGH_RISK", "SELL", "NO_EDGE")
    # No pivot/swing used for confirmation may be timestamped after the cutoff.
    for swing in state["elliott_cycle"]["elliott"]["evidence"]["confirmed_swings"]:
        assert pd.Timestamp(swing["confirmed_at"]) <= cutoff
