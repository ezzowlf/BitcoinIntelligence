from pathlib import Path
import numpy as np
import pandas as pd
from bitcoin_cycle_analyzer.advanced.indicators import rsi,bollinger,divergence,multi_timeframe_indicators
from bitcoin_cycle_analyzer.advanced.zones import HistoricalZoneEngine
from bitcoin_cycle_analyzer.advanced.drawdown import DrawdownCycleEngine
from bitcoin_cycle_analyzer.rare_signals.signal_book import build_historical_signal_book
from bitcoin_cycle_analyzer.seasonality.event_windows import holiday_dates
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.rare_signals.shocks import geopolitical_reaction,market_shocks
import pytest


def frame(periods=2200):
    idx=pd.date_range("2018-01-01",periods=periods,tz="UTC");trend=np.exp(np.linspace(np.log(1000),np.log(50000),periods));wave=1+.28*np.sin(np.arange(periods)/55);close=trend*wave
    return pd.DataFrame({"open":close*.995,"high":close*1.025,"low":close*.975,"close":close,"volume":100+50*np.cos(np.arange(periods)/13)},index=idx)


def test_historical_zone_pit_never_uses_later_confirmation():
    data=frame();cutoff=data.index[1500];zones=HistoricalZoneEngine().analyze(data,cutoff)
    assert all(pd.Timestamp(z["formation_cutoff"])<=cutoff for z in zones)


def test_zone_replay_does_not_mutate_old_version():
    data=frame();cutoff=data.index[1500];old=HistoricalZoneEngine().analyze(data,cutoff);new=HistoricalZoneEngine().analyze(data,data.index[1900])
    assert [(z["zone_id"],z["version"]) for z in old]==[(z["zone_id"],z["version"]) for z in HistoricalZoneEngine().analyze(data,cutoff)]
    assert all(z["last_confirmed"]<=data.index[1900] for z in new)


def test_zone_clustering_has_dynamic_width_and_independent_touches():
    zones=HistoricalZoneEngine().analyze(frame());assert zones
    assert all(z["upper_bound"]>z["lower_bound"] and z["touch_count"]>=2 for z in zones)


def test_zone_strength_failure_and_exhaustion_are_bounded():
    for z in HistoricalZoneEngine().analyze(frame()):
        assert 0<=z["strength"]<=100 and 0<=z["failure_rate"]<=1 and 0<=z["support_exhaustion"]<=1


def test_zone_flip_field_and_reaction_statistics_exist():
    z=HistoricalZoneEngine().analyze(frame())[0]
    assert z["zone_flip"] in {None,"RESISTANCE_TO_SUPPORT","SUPPORT_TO_RESISTANCE"}
    assert {"median_7d_reaction","median_30d_reaction","MAE","MFE"}<=z.keys()


def test_zone_fib_confluence_is_not_separate_zone():
    engine=HistoricalZoneEngine();base=engine.analyze(frame());level=(base[0]["lower_bound"]+base[0]["upper_bound"])/2;enriched=engine.analyze(frame(),fib_levels=[level])
    assert len(base)==len(enriched) and any(z["fib_confluence"] for z in enriched)


def test_previous_ath_zones_are_detected_algorithmically():
    assert any(z["zone_type"]=="PREVIOUS_ATH" for z in HistoricalZoneEngine().analyze(frame()))


def test_peak_to_trough_and_recovery_cycles():
    result=DrawdownCycleEngine().analyze(frame());assert result["cycles"]
    assert all(c["trough_date"]>=c["peak_date"] and c["drawdown"]<=-.2 for c in result["cycles"])


def test_drawdown_percentile_velocity_and_time_under_water():
    result=DrawdownCycleEngine().analyze(frame());assert 0<=result["historical_severity_percentile"]<=100
    assert set(result["drawdown_velocity"])=={"7d","30d","90d"} and result["days_below_previous_ath"]>=0


def test_recovery_state_is_named_and_recovery_nonnegative():
    result=DrawdownCycleEngine().analyze(frame());assert result["state"] in {"EARLY_DRAWDOWN","MID_DRAWDOWN","DEEP_DRAWDOWN","EXTREME_DRAWDOWN","RECOVERY","LATE_RECOVERY","NEW_EXPANSION"}
    assert result["recovery_from_major_low"]>=0


def test_wilder_rsi_reference_monotonic_series():
    values=rsi(pd.Series(np.arange(100,dtype=float)));assert values.iloc[-1]==100


def test_weekly_monthly_and_rsi365_are_research_outputs():
    result=multi_timeframe_indicators(frame(),four_hour=frame());assert result["weekly"]["rsi"] is not None and result["monthly"]["rsi"] is not None and result["4h"]["rsi"] is not None
    assert result["rsi_365d"]["status"]=="RESEARCH"


def test_4h_is_unavailable_without_real_4h_data():
    assert multi_timeframe_indicators(frame())["4h"]["status"]=="UNAVAILABLE"


def test_rsi_divergence_schema():
    result=divergence(pd.Series(np.arange(100,dtype=float)),pd.Series(np.arange(100,dtype=float)));assert list(result)==["bullish","bearish"]


def test_bollinger_reference_calculation_matches_population_std():
    values=pd.Series(np.arange(1,31,dtype=float));result=bollinger(values,20,2).iloc[-1];window=values.iloc[-20:]
    assert np.isclose(result.middle,window.mean()) and np.isclose(result.upper,window.mean()+2*window.std(ddof=0))


def test_bollinger_bandwidth_and_extreme_state():
    result=multi_timeframe_indicators(frame());assert result["weekly"]["bollinger"]["bandwidth"]>0
    assert result["weekly"]["bollinger"]["state"] in {"BELOW","INSIDE","ABOVE"}


def test_holiday_dates_compute_fourth_thursday_and_following_friday():
    dates=holiday_dates(2025);assert dates["thanksgiving"].weekday()==3 and (dates["black_friday"]-dates["thanksgiving"]).days==1


def test_signal_book_has_symmetric_outcomes_and_spacing():
    book=build_historical_signal_book(frame());assert not book.empty
    assert {"return_30d","MAE_30d","MFE_30d","false_sell_30d","days_after_local_low","days_after_local_high"}<=set(book.columns)
    for _,group in book.groupby("signal_type"):
        assert (pd.to_datetime(group.date).sort_values().diff().dropna().dt.days>=30).all()


def test_signal_book_levels_are_separate():
    book=build_historical_signal_book(frame());assert set(book.level)<={"PRODUCTION","CANDIDATE"}


def test_tradingview_uses_v6_and_no_fake_rare_signal():
    pine=(Path(__file__).parents[1]/"tradingview"/"bitcoin_intelligence_indicator.pine").read_text(encoding="utf-8")
    assert pine.startswith("//@version=6") and "lookahead=barmerge.lookahead_off" in pine and "STRONG_BUY" not in pine


def test_tradingview_reference_components_are_present():
    pine=(Path(__file__).parents[1]/"tradingview"/"bitcoin_intelligence_indicator.pine").read_text(encoding="utf-8")
    for token in ("ta.rsi","ta.bb","ta.atr","drawdown","majorSupport","majorResistance","alertcondition"):assert token in pine


def test_forward_rare_signal_cutoff_and_separation(tmp_path):
    ledger=ForwardLedger(tmp_path/"forward.db")
    with pytest.raises(ValueError):ledger.append_rare_signal("x","2026-08-09T00:00:00Z","CANDIDATE","BUY_CANDIDATE",{})
    ledger.append_rare_signal("y","2026-08-10T00:00:00Z","PRODUCTION","BUY",{"status":"FORWARD"})
    assert ledger.health()["rare_signals"]==1


def test_war_news_alone_never_becomes_sell():
    result=geopolitical_reaction("WAR_ESCALATION",frame(100),frame(100).index[-10])
    assert result["maximum_news_only_state"]=="WATCH" and result["risk_action"]!="SELL"


def test_news_reaction_transmission_and_resilience():
    data=frame(100);result=geopolitical_reaction("MISSILE_STRIKE",data,data.index[-10],oil_return=.05,nasdaq_return=-.03)
    assert set(result["returns"])=={"24h","3d","7d"} and isinstance(result["negative_news_resilience"],bool)


def test_market_shock_contract():
    result=market_shocks(frame(100));assert {"volatility_shock","volume_shock","gap_move","status"}==set(result)


def test_challenger_registry_preserves_frozen_boundary():
    import json
    registry=json.loads((Path(__file__).parents[1]/"challengers"/"rare_signal_challenger_1.json").read_text(encoding="utf-8"))
    assert registry["model_id"]=="RARE_SIGNAL_CHALLENGER_1" and registry["champion_unchanged"]=="2.3-FROZEN" and registry["execution"]=="DISABLED"
