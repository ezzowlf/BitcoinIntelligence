from copy import deepcopy
from pathlib import Path
import json,sys
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.master import BitcoinMasterEngine
from bitcoin_cycle_analyzer.master.registry import build_factor_registry
from bitcoin_cycle_analyzer.master.replay import build_master_historical_signal_book
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.telegram.formatter import command_message
from bitcoin_cycle_analyzer.telegram.events import detect_events


@pytest.fixture(scope="module")
def current():return bitcoin_intelligence.state()[0]


def technical(current):
    return {"price":current["master"]["state"]["btc_price"]}


def rebuild(current,mutate=None):
    state=deepcopy(current)
    if mutate:mutate(state)
    old=state.pop("master",None);return state,BitcoinMasterEngine().analyze(state,technical(current))


def test_master_state_and_model_hierarchy(current):
    assert current["master"]["primary_analysis_model"]=="2.5-RARE-SIGNAL" and current["master"]["control_model"]=="2.3-FROZEN"
    assert current["master"]["version"]=="MASTER-3.0"


def test_master_current_decision_separates_actions(current):
    d=current["master"]["decision"];assert d["long_term_action"]=="ACCUMULATE" and d["new_entry_action"]=="ACCUMULATE" and d["existing_position_action"]=="HOLD"


def test_factor_registry_contract_and_rejected_sell(current):
    registry=current["master"]["state"]["factor_registry"]
    assert all({"name","group","status","direction_role","confidence","freshness","availability","independence_group","research_status"}<=x.keys() for x in registry)
    rejected=next(x for x in registry if x["name"]=="historical_sell_proxy");assert rejected["status"]=="REJECTED" and rejected["direction_role"]=="NONE"


def test_redundancy_groups_fib_and_zones(current):
    registry=current["master"]["state"]["factor_registry"]
    assert next(x for x in registry if x["name"]=="fibonacci")["independence_group"]==next(x for x in registry if x["name"]=="historical_zones")["independence_group"]


def test_confluence_is_not_universal_score(current):
    c=current["master"]["state"]["confluence"];assert "score" not in c and "not a universal score" in c["method"]


def test_buy_and_strong_buy_hierarchy(current):
    def buy(s):s["rare_signal"]["level_a"]["signal"]="BUY";s["rare_signal"]["buy_state"]="BUY"
    _,m=rebuild(current,buy);assert m["decision"]["production_signal"]=="BUY" and m["decision"]["new_entry_action"]=="BUY"
    def strong(s):s["rare_signal"]["level_a"]["signal"]="STRONG_BUY";s["rare_signal"]["buy_state"]="STRONG_BUY"
    _,m=rebuild(current,strong);assert m["decision"]["long_term_action"]=="STRONG_ACCUMULATE" and m["decision"]["new_entry_action"]=="STRONG_BUY"


def test_rejected_or_unconfirmed_sell_is_isolated(current):
    def mutate(s):s["rare_signal"]["level_a"]["signal"]="SELL";s["rare_signal"]["sell"]["confirmation"]="NOT_YET";s["rare_signal"]["sell"]["independent_groups"]=6
    _,m=rebuild(current,mutate);assert m["decision"]["production_signal"]=="NO_PRODUCTION_SIGNAL" and m["decision"]["existing_position_action"]=="HOLD"


def test_confirmed_sell_and_strong_sell_require_independent_groups(current):
    for signal in ("SELL","STRONG_SELL"):
        def mutate(s,signal=signal):s["rare_signal"]["level_a"]["signal"]=signal;s["rare_signal"]["sell"]["confirmation"]="CONFIRMED";s["rare_signal"]["sell"]["independent_groups"]=4
        _,m=rebuild(current,mutate);assert m["decision"]["production_signal"]==signal and m["decision"]["existing_position_action"]=="SELL"


def test_reduce_and_partial_profit_are_not_sell(current):
    def reduce(s):s["rare_signal"]["sell"]["state"]="REDUCE"
    _,m=rebuild(current,reduce);assert m["decision"]["existing_position_action"]=="REDUCE"


def test_data_quality_gate_blocks_production(current):
    def mutate(s):s["precision"]["data_health"]["critical_healthy"]=False;s["rare_signal"]["level_a"]["signal"]="BUY"
    _,m=rebuild(current,mutate);assert m["decision"]["new_entry_action"]=="DO_NOT_BUY" and m["decision"]["confidence"]=="LOW"


def test_missing_providers_stay_unavailable(current):
    s=current["master"]["state"];assert s["macro_state"]==s["etf_state"]==s["news_state"]=="UNAVAILABLE"


def test_derivatives_are_risk_only(current):
    factor=next(x for x in current["master"]["state"]["factor_registry"] if x["name"]=="derivatives");assert factor["status"]=="RISK_ONLY" and factor["direction_role"]=="RISK"


def test_zone_drawdown_rsi_bollinger_integration(current):
    s=current["master"]["state"];assert s["nearest_support"] and s["nearest_resistance"] and len(s["buy_zones"])==2
    assert s["drawdown"]<0 and s["weekly_rsi"] is not None and s["daily_bollinger"] in {"BELOW","INSIDE","ABOVE"}


def test_model_disagreement_is_explicit(current):
    assert current["master"]["decision"]["model_disagreement"]["state"] in {"ALIGNED","MODEL_DISAGREEMENT"}


@pytest.mark.parametrize("command",["/master","/buy","/sell","/levels","/drawdown"])
def test_master_telegram_commands(current,command):
    message=command_message(command,current);assert message and "DISABLED" in message


def test_candidate_completion_is_labeled_not_probability(current):
    assert "not probability" in command_message("/master",current) and "not probability" in command_message("/buy",current)


def test_master_forward_ledger_and_cutoff(current,tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db");early=deepcopy(current["master"])
    with pytest.raises(ValueError):ledger.append_master_snapshot(early)
    eligible=deepcopy(early);eligible["state"]["timestamp"]="2026-08-10T00:00:00Z";ledger.append_master_snapshot(eligible);assert ledger.health()["master_snapshots"]==1
    with pytest.raises(Exception):ledger.append_master_snapshot(eligible)


def test_historical_master_replay_is_research_and_rejected_sell_absent(current):
    cfg=bitcoin_intelligence.state()[1];frame=bitcoin_intelligence.OHLCVStore(bitcoin_intelligence.root/cfg["data"]["database"]).load("1d");book,errors=build_master_historical_signal_book(frame)
    assert set(book.master_signal)<={"BUY","REDUCE"} and (book.research_status=="RESEARCH_ONLY").all();assert not errors.empty and "FALSE_SELL" in set(errors.error)


def test_execution_is_disabled_everywhere(current):
    assert current["master"]["execution"]==current["master"]["decision"]["execution"]=="DISABLED"


def test_master_production_alert_and_candidate_silence(current):
    previous=deepcopy(current);now=deepcopy(current);now["master"]["decision"]["production_signal"]="BUY"
    assert "MASTER_PRODUCTION_SIGNAL" in detect_events(now,previous)
    candidate=deepcopy(current);candidate["master"]["state"]["buy_completion"]=75
    assert "MASTER_PRODUCTION_SIGNAL" not in detect_events(candidate,previous)


def test_candidate_change_is_separate_from_production(current):
    previous=deepcopy(current);now=deepcopy(current);now["master"]["state"]["buy_candidate"]="NONE"
    events=detect_events(now,previous);assert "MASTER_CANDIDATE_CHANGE" in events and "MASTER_PRODUCTION_SIGNAL" not in events


def test_master_freeze_hash_matches_sources():
    import hashlib
    root=Path(__file__).parents[1];freeze=json.loads((root/"frozen"/"master_3_0_frozen.json").read_text(encoding="utf-8"));digest=hashlib.sha256()
    for file in ("engine.py","models.py","registry.py","replay.py"):digest.update((root/"src"/"bitcoin_cycle_analyzer"/"master"/file).read_bytes())
    assert digest.hexdigest()==freeze["master_code_hash"] and freeze["execution"]=="DISABLED"
