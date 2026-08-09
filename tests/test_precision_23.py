from __future__ import annotations
import pandas as pd
from bitcoin_cycle_analyzer.precision.value import value_engine
from bitcoin_cycle_analyzer.precision.regime import regime_ensemble
from bitcoin_cycle_analyzer.precision.risk import precision_risk
from bitcoin_cycle_analyzer.precision.timing import timing_engine
from bitcoin_cycle_analyzer.precision.decision import uncertainty_engine,market_taxonomy,scenarios
from bitcoin_cycle_analyzer.precision.engine import data_quality_state,hysteresis
from bitcoin_cycle_analyzer.precision.similarity import sequence_analogues
from bitcoin_cycle_analyzer.precision.replay import replay_frame,navigate
from bitcoin_cycle_analyzer.precision.storage import PrecisionStore
from bitcoin_cycle_analyzer.precision.validation import false_confirmation,monotonicity
from bitcoin_cycle_analyzer.precision.research import era_diagnostics,holdout_registry
from bitcoin_cycle_analyzer.alerts import precision_alert


def technical(): return {"states":{"confirmation":"LOW"},"structure":{"trend":"bearish"},"forward_summary_365d":{"worst_drawdown":-.5}}
def cycle(): return {"halving":{"months_since":27},"primary_regime":"TRANSITION"}


def test_value_percentile_is_point_in_time(ohlcv):
    early=value_engine(ohlcv,cycle(),technical(),ohlcv.index[-100]); late=value_engine(ohlcv,cycle(),technical(),ohlcv.index[-1])
    assert 0<=early["historical_percentile"]<=100 and early!=late
    assert "funding" in early["excluded_inputs"]


def test_regime_ensemble_support_stability_transition(ohlcv):
    result=regime_ensemble(ohlcv,cycle(),as_of=ohlcv.index[-1])
    assert round(sum(result["relative_support"].values()),0)==100
    assert result["stability"] in {"LOW","MEDIUM","HIGH"}
    assert result["transition_status"] in {"CANDIDATE","CONFIRMING","CONFIRMED"}


def test_timing_mandatory_conditions_and_data_hold():
    risk={"tail_state":"NORMAL"}; quality={"critical_healthy":True}
    result=timing_engine(technical(),risk,quality)
    assert result["state"] not in {"CONFIRMING","CONFIRMED"} and result["execution"]=="DISABLED"
    quality["critical_healthy"]=False
    assert timing_engine(technical(),risk,quality)["state"]=="STATE_HELD_DUE_TO_DATA_QUALITY"


def test_horizon_risk_and_capitulation_no_bottom_claim(ohlcv):
    result=precision_risk(ohlcv,technical(),as_of=ohlcv.index[-1])
    assert set(result["horizons"])=={"7d","30d","90d"}
    assert "bottom" not in str(result).lower()


def test_uncertainty_no_edge_conflict_and_scenarios():
    regime={"model_agreement":.2,"candidate":"RECOVERY","stability":"LOW"}; conf={"independent_groups":2,"level":"LOW"}; evidence={"score":30}
    uncertainty=uncertainty_engine(regime,conf,evidence,{"unavailable_groups":5},.9)
    assert uncertainty["state"] in {"HIGH","VERY_HIGH"}
    value={"state":"HIGH_VALUE","score":75}; timing={"state":"WAIT"}; risk={"tail_state":"HIGH","capitulation":"NONE"}
    taxonomy=market_taxonomy(value,timing,risk,regime,evidence,conf)
    assert taxonomy["market_state"]=="HIGH_VALUE_HIGH_RISK"
    assert all("probability" not in item for item in scenarios(value,regime,timing,risk))


def test_hysteresis_prevents_flip():
    assert hysteresis("BEAR","RECOVERY",1,min_days=3)=={"state":"BEAR","held":True}
    assert hysteresis("BEAR","RECOVERY",3,min_days=3)["state"]=="RECOVERY"


def test_sequence_similarity_uses_independent_episodes(ohlcv):
    result=sequence_analogues(ohlcv,window=30,top_n=5,spacing_days=120)
    assert result["independent_episodes"]<=5
    dates=[row["date"] for row in result["analogues"]]
    assert all(abs((a-b).days)>=120 for i,a in enumerate(dates) for b in dates[i+1:])


def test_replay_never_sees_future(ohlcv):
    cutoff=ohlcv.index[100]; replay=replay_frame(ohlcv,cutoff)
    assert replay.index.max()==cutoff and len(replay)==101
    assert navigate(cutoff,"plus_7_days")==cutoff+pd.Timedelta(days=7)


def test_snapshot_versioning_and_as_of(tmp_path):
    store=PrecisionStore(tmp_path/"precision.db"); snapshot={"timestamp":"2024-01-01","price":1,"value":{"score":50},"regime":{"current":"TRANSITION"},"timing":{"state":"WAIT"},"risk":{"horizons":{"30d":70}},"evidence":{"score":40},"confluence":{"score":50},"engine_version":"2.3","config_hash":"x"}
    store.save_snapshot(snapshot); assert store.as_of("2024-01-02") is not None
    store.record_transition("2024-01-02","WAIT","EARLY",["reclaim"],.6,"2024-01-02")
    store.register_factor({"factor":"timing","hypothesis":"reclaim improves MAE","first_test_date":"2024-01-01","training_window":"2011-2020","validation_window":"2021-2022","oos_window":"2023-2024","result":"failed","status":"RESEARCH"})
    store.record_experiment({"experiment_id":"e1","hypothesis":"fixed test","change":"none","dataset":"btc","metrics":{"mae":-.1},"result":"negative","decision":"do_not_promote"})


def test_false_confirmation_and_score_monotonicity():
    rows=[{"state":"CONFIRMED","mae":-.2,"return_30d":.1},{"state":"CONFIRMED","mae":-.02,"return_30d":.2}]
    assert false_confirmation(rows)["false_confirmation_rate"]==.5
    result=monotonicity(pd.Series([10,30,50,70,90]),pd.Series([-1,0,1,2,3]))
    assert result["monotone"] is True


def test_data_quality_penalty_alert_dedup_and_research(ohlcv):
    quality=data_quality_state({"price":{"status":"AVAILABLE"},"oi":{"status":"STALE"}}); assert quality["critical_healthy"] is False
    current={"market_state":"B","timing":{"state":"WAIT"},"risk":{"horizons":{"30d":50}},"explanation":{},"scenarios":{"base":{}}}
    assert precision_alert(current,current) is None
    changed={**current,"market_state":"C"}; assert precision_alert(current,changed)["severity"]=="WATCH"
    assert era_diagnostics(ohlcv)["status"]=="RESEARCH" and holdout_registry()["final_holdout"]=="NOT_AVAILABLE_YET"
