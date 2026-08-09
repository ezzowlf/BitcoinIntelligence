from copy import deepcopy
from pathlib import Path
import sys
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
import bitcoin_intelligence
from bitcoin_cycle_analyzer.master.historical_entry_quality import FACTOR_GROUPS,load_reference_set,evaluate_historical_entry_quality
from bitcoin_cycle_analyzer.research.best_entries import staged_entry_research
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.telegram.formatter import command_message

@pytest.fixture(scope="module")
def current():return bitcoin_intelligence.state()[0]

def test_entry_quality_contract_and_groups(current):
    h=current["historical_entry_quality"]
    assert h["state"] in {"LOW","MODERATE","HIGH","VERY_HIGH","EXTREME"}
    assert set(FACTOR_GROUPS)=={"VALUE","LOCATION","MOMENTUM_EXTREME","STRESS"}
    assert h["sample_size"]==8 and h["research_status"]=="LIVE_RESEARCH_CONTEXT"

def test_no_duplicate_support_fib_evidence(current):
    groups=current["historical_entry_quality"]["factor_groups"]
    assert groups["LOCATION"]["available"]==1
    assert "FIB" not in str(groups)

def test_reference_loading_and_hash():
    episodes,matrix,status=load_reference_set(Path(__file__).parents[1])
    assert status=="AVAILABLE" and len(episodes)==8 and not matrix.empty

def test_reference_missing_is_nonfatal(current,tmp_path):
    frame=OHLCVStore(Path(__file__).parents[1]/"database"/"bitcoin.db").load("1d")
    state=deepcopy(current);state.pop("master");technical={"price":state["decision"]["zones"]["current_price"]}
    result=evaluate_historical_entry_quality(frame,state,technical,tmp_path)
    assert result["state"]=="HISTORICAL_ENTRY_QUALITY_UNAVAILABLE"

def test_history_comparison_controls_and_mae(current):
    h=current["historical_entry_quality"]
    assert len(h["closest_historical_entries"])==3
    assert h["control_comparison"]["failed_buy_reference_n"]==5
    assert {"median","best","worst","warning"}<=h["mae_context"].keys()

def test_staged_research_fixed_variants():
    root=Path(__file__).parents[1];frame=OHLCVStore(root/"database"/"bitcoin.db").load("1d");episodes=pd.read_csv(root/"BITCOIN_ENTRY_EPISODES.csv")
    result=staged_entry_research(frame,episodes)
    assert set(result.variant)=={"single_entry","2_stage","3_stage","recovery_confirmed"}
    assert (result.status=="RESEARCH_ONLY").all()

def test_telegram_views_and_production_unchanged(current):
    assert "HISTORICAL ENTRY QUALITY" in command_message("/master",current)
    assert "HISTORICAL OUTCOMES - NOT FORECASTS" in command_message("/history",current)
    assert "HISTORICAL ENTRY QUALITY" in command_message("/buy",current)
    assert current["master"]["decision"]["production_signal"]=="NO_PRODUCTION_SIGNAL"
    assert current["master"]["execution"]=="DISABLED"

def test_master_state_contains_forward_fields(current):
    s=current["master"]["state"]
    assert {"historical_entry_quality_score","historical_entry_quality_state","entry_archetype","closest_entry_episodes","historical_mae_median","price_vs_200d_pct","price_vs_200w_pct"}<=s.keys()
