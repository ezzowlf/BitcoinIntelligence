import pandas as pd
import pytest
from bitcoin_cycle_analyzer.macro7 import MacroSwingEngine,FullHistoryElliottEngine,MacroSwingResearch
from bitcoin_cycle_analyzer.macro7_live import Macro7ShadowLedger

def market():
    idx=pd.date_range("2011-01-01",periods=5600,freq="D",tz="UTC");trend=pd.Series(range(len(idx)),index=idx,dtype=float);cycle=1+.45*((trend%700)/700)-.35*((trend%350)/350);close=10*(1.0015**trend)*cycle
    return pd.DataFrame({"open":close*.99,"high":close*1.03,"low":close*.97,"close":close,"volume":1000},index=idx)

def test_yearly_candles_and_stats():
    y=MacroSwingResearch().yearly(market());assert len(y)>=15 and {"year","return","max_drawdown","rolling_2y_return","rolling_4y_return","yearly_roc"}<=set(y)

def test_all_history_and_macro_elliott_hierarchy():
    result=FullHistoryElliottEngine().analyze(market());assert result["coverage"]["from"]==market().index.min();assert set(result["hierarchy"])=={"MACRO_CYCLE","PRIMARY","INTERMEDIATE","MINOR"};assert result["production_role"]=="CONTEXT_ONLY"

def test_full_history_count_is_algorithmic_and_has_explanation():
    result=FullHistoryElliottEngine().analyze(market());assert result["macro_pivots"] and all("confirmed_at" in x for x in result["macro_pivots"]);assert result["explanation"]["abc_alternative"]

def test_pit_elliott_replay_never_uses_future():
    frame=market();engine=FullHistoryElliottEngine();replay=engine.replay(frame);result=engine.analyze(frame);assert not replay.empty and replay.cutoff.max()<=frame.index.max();assert all(pd.Timestamp(x["confirmed_at"])<=frame.index.max() for x in result["macro_pivots"])

def test_macro_scenarios_activation_and_invalidation_are_conditional():
    result=MacroSwingEngine().analyze(market());assert {"BULL RECOVERY","BASE CONSOLIDATION","DEEP BEAR","EXTREME CYCLE"}<={x["name"] for x in result["scenarios"]};assert all(x["activation_conditions"] and x["invalidation_conditions"] for x in result["scenarios"])

def test_deep_and_extreme_scenarios_have_no_probability():
    scenarios=MacroSwingEngine().analyze(market())["scenarios"]
    for x in scenarios:assert "probability" not in x and x["confidence_state"] in {"LOW","MODERATE","HIGH"}

def test_drawdown_price_ladder():
    ladder=MacroSwingEngine().analyze(market())["drawdown_ladder"];assert [x["drawdown"] for x in ladder["levels"]]==[-.1,-.2,-.3,-.4,-.5,-.6,-.7,-.8,-.85,-.9];assert sum(x["current_marker"] for x in ladder["levels"])==1

def test_macro_and_swing_zones_have_independent_groups():
    zones=MacroSwingEngine().analyze(market())["zones"];assert zones["swing_buy"]["horizon"]=="SWING" and zones["macro_accumulation"]["horizon"]=="MACRO";assert len(zones["macro_accumulation"]["independent_groups"])==3

def test_cycle_overlays_and_halvings():
    overlays=MacroSwingResearch().overlays(market());assert len(overlays["halving"])==4 and "ath_drawdowns" in overlays

def test_long_swing_entries_are_pit_and_minimum_duration():
    swings=MacroSwingResearch().long_swings(market());assert swings.empty or (swings.duration>=14).all();assert swings.empty or set(swings.signal_input)=={"PIT"}

def test_staged_entries_are_research_only_outcomes():
    rows=MacroSwingResearch().ladder_backtest(market());assert rows.empty or rows.stages_filled.between(1,4).all()

def test_horizon_outputs_and_no_production_impact():
    result=MacroSwingEngine().analyze(market());assert set(result["actions"])=={"macro","long_swing","medium_swing","tactical_timing","risk"};assert result["production_impact"]=="NONE" and result["execution"]=="DISABLED"

def test_macro7_forward_ledger_is_post_freeze_and_append_only(tmp_path):
    ledger=Macro7ShadowLedger(tmp_path/"m.db","2026-01-01T00:00Z")
    with pytest.raises(ValueError):ledger.append("W1","2026-01-01T00:00Z",{})
    sid=ledger.append("W1","2026-01-05T00:00Z",{"execution":"DISABLED"});assert ledger.append("W1","2026-01-05T00:00Z",{"execution":"DISABLED"})==sid
    with pytest.raises(ValueError):ledger.append("W1","2026-01-05T00:00Z",{"changed":True})
