import pandas as pd
import pytest
from bitcoin_cycle_analyzer.core.cycle_engine import analyze_cycle, halving_context
from bitcoin_cycle_analyzer.data_contracts import MetricObservation, DataStatus, freshness, point_in_time
from bitcoin_cycle_analyzer.seasonality.statistics import monthly_statistics, weekday_statistics, monthly_heatmap
from bitcoin_cycle_analyzer.seasonality.event_windows import event_window_statistics, holiday_dates
from bitcoin_cycle_analyzer.derivatives.funding import analyze_funding
from bitcoin_cycle_analyzer.derivatives.open_interest import analyze_open_interest
from bitcoin_cycle_analyzer.derivatives.basis import annualized_basis
from bitcoin_cycle_analyzer.flows.etf import analyze_etf_flows
from bitcoin_cycle_analyzer.flows.spot_demand import classify_move
from bitcoin_cycle_analyzer.onchain import UnavailableOnChainProvider, analyze_onchain, METRICS
from bitcoin_cycle_analyzer.macro import analyze_macro
from bitcoin_cycle_analyzer.macro.economic_calendar import released_events
from bitcoin_cycle_analyzer.news import NewsEvent, EventCategory, EventDirection, events_as_of, impact_chain
from bitcoin_cycle_analyzer.news.macro_news import news_risk
from bitcoin_cycle_analyzer.scoring import evidence_score, confluence_score
from bitcoin_cycle_analyzer.validation.ablation import ablation_report
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence, public_payload
from bitcoin_cycle_analyzer.alerts import build_alert


def external_frame(values, dates):
    return pd.DataFrame({"value": values, "observed_at": dates, "available_at": dates, "provider": "fixture"})


def config():
    return {"version":"test", "swings":{"1d":{"window":10,"min_atr_move":2.0}}, "similarity":{"neighbors":10,"exclusion_days":365,"min_history_days":365,"min_case_spacing_days":30}, "score_weights":{"long_term_trend":20,"historical_similarity":20,"fibonacci":15,"elliott_abc":15,"momentum_rsi":10,"support_resistance":10,"volume":5,"risk_reward":5}}


def test_cycle_engine_probabilistic_and_causal(ohlcv):
    cutoff = ohlcv.index[1200]
    first = analyze_cycle(ohlcv, cutoff)
    changed = ohlcv.copy(); changed.loc[changed.index > cutoff, "close"] *= 100
    second = analyze_cycle(changed, cutoff)
    assert first == second
    assert round(sum(first["all_regimes"].values()), 0) == 100
    assert first["primary_regime"] in first["all_regimes"]
    assert halving_context(pd.Timestamp("2025-04-20", tz="UTC"))["days_since"] == 365


def test_metric_availability_and_freshness():
    date = pd.Timestamp("2025-01-02", tz="UTC")
    observation = MetricObservation("x", 1, date, date + pd.Timedelta(days=1), "p", DataStatus.AVAILABLE)
    assert not observation.visible_as_of(date)
    assert observation.visible_as_of(date + pd.Timedelta(days=1))
    assert freshness(date, 3600, date + pd.Timedelta(minutes=30))["status"] == "AVAILABLE"


def test_point_in_time_rejects_future_release():
    dates = pd.to_datetime(["2025-01-01", "2025-02-01"], utc=True)
    frame = external_frame([1, 999], dates)
    visible = point_in_time(frame, dates[0])
    assert visible.value.tolist() == [1]


def test_seasonality_and_heatmap_real_history(ohlcv):
    monthly = monthly_statistics(ohlcv)
    assert monthly["1"]["samples"] > 0
    assert 0 <= monthly["1"]["win_rate"] <= 1
    assert len(weekday_statistics(ohlcv)) == 7
    assert not monthly_heatmap(ohlcv).empty


def test_holiday_window_has_no_future_samples(ohlcv):
    cutoff = pd.Timestamp("2017-11-20", tz="UTC")
    result = event_window_statistics(ohlcv, "black_friday", as_of=cutoff)
    assert all(item["event_date"] + pd.Timedelta(days=14) <= cutoff for item in result["observations"])
    assert holiday_dates(2025)["black_friday"].weekday() == 4


def test_derivatives_are_release_causal():
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-09"], utc=True)
    frame = external_frame([-.01, .01, .02], dates)
    funding = analyze_funding(frame, dates[1])
    oi = analyze_open_interest(frame, dates[-1])
    assert funding["value"] == .01
    assert oi["change_7d"] == pytest.approx(1.0)
    assert annualized_basis(100, 105, 30) == pytest.approx(.6083333333)


def test_etf_flow_and_spot_demand():
    dates = pd.date_range("2025-01-01", periods=20, tz="UTC")
    frame = pd.DataFrame({"net_flow_usd": range(1, 21), "available_at": dates, "provider":"fixture"})
    state = analyze_etf_flows(frame, dates[-1])
    assert state["state"] == "STRONG_ACCUMULATION"
    assert classify_move(.05, 1, .01, .5)["state"] == "SPOT_LED_RALLY"
    assert classify_move(.05, -1, .2, .95)["state"] == "LEVERAGE_LED_MOVE"


def test_unavailable_onchain_is_explicit():
    result = analyze_onchain(UnavailableOnChainProvider(), pd.Timestamp.now(tz="UTC"))
    assert result["status"] == "UNAVAILABLE"
    assert len(result["metrics"]) == len(METRICS)
    assert all(value["status"] == "UNAVAILABLE" for value in result["metrics"].values())


def test_macro_and_calendar_use_release_timestamp():
    dates = pd.to_datetime(["2025-01-01", "2025-02-01"], utc=True)
    frame = external_frame([4, 5], dates)
    result = analyze_macro({"fed_funds": frame}, dates[0])
    assert result["metrics"]["fed_funds"]["value"] == 4
    calendar = pd.DataFrame({"release_timestamp": dates, "value":[4,5]})
    assert released_events(calendar, dates[0]).value.tolist() == [4]


def test_news_is_available_at_not_event_time():
    t = pd.Timestamp("2025-01-01", tz="UTC")
    event = NewsEvent(t, t + pd.Timedelta(hours=2), EventCategory.WAR, "verified fixture", .8, EventDirection.RISK_OFF, .7, "fixture")
    assert events_as_of([event], t) == []
    assert events_as_of([event], t + pd.Timedelta(hours=2)) == [event]
    assert impact_chain(event, oil_change=.1, rate_expectation_change=.1)["interpretation"] == "RISK_OFF_PRESSURE"
    assert news_risk([event])["risk"] == "MEDIUM"


def test_evidence_and_confluence_do_not_double_count():
    evidence = evidence_score(20, 1, .5, .5, .5)
    assert evidence["score"] == 75
    factors = [{"name":"rsi","group":"momentum","strength":.7},{"name":"stoch","group":"momentum","strength":.4},{"name":"etf","group":"flows","strength":.8}]
    result = confluence_score(factors)
    assert result["independent_groups"] == 2
    assert {x["name"] for x in result["selected"]} == {"rsi", "etf"}


def test_ablation_reports_incremental_rank_information():
    idx = pd.date_range("2025-01-01", periods=5, tz="UTC")
    result = ablation_report(pd.Series(range(5), idx), {"x":pd.Series([0,0,1,1,1],idx)}, pd.Series(range(5),idx))
    assert result["full"]["rank_correlation"] == pytest.approx(1)
    assert "without_x" in result


def test_full_intelligence_gracefully_degrades(ohlcv):
    state = analyze_intelligence(ohlcv, config())
    assert state["modules"]["onchain"]["status"] == "UNAVAILABLE"
    assert state["modules"]["seasonality"]["status"] == "AVAILABLE"
    assert state["entry_timing"] in {"WAIT", "WATCH", "CONFIRMED"}
    payload = public_payload(state)
    assert payload["service"] == "bitcoin-cycle"
    assert build_alert(state, min_value=0, min_evidence=0)["execution"] == "DISABLED"
