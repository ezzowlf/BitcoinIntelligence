import pandas as pd
from bitcoin_cycle_analyzer.indicators import add_indicators
from bitcoin_cycle_analyzer.similarity import find_similar, forward_returns, summarize_forward
from bitcoin_cycle_analyzer.backtesting import run_backtest
from bitcoin_cycle_analyzer.walk_forward import splits, run_walk_forward
from bitcoin_cycle_analyzer.opportunity_score import calculate_score
from bitcoin_cycle_analyzer.analyzer import analyze

def test_indicators_have_no_future_dependency(ohlcv):
    cutoff = ohlcv.index[1000]
    before = add_indicators(ohlcv.loc[:cutoff])
    after = add_indicators(ohlcv.copy())
    pd.testing.assert_series_equal(before.iloc[-1], after.loc[cutoff])

def test_similarity_is_point_in_time(ohlcv):
    data = add_indicators(ohlcv)
    cutoff = data.index[1400]
    a = find_similar(data, cutoff, exclusion_days=365)
    mutated = data.copy(); mutated.loc[mutated.index > cutoff, "close"] *= 100
    b = find_similar(mutated, cutoff, exclusion_days=365)
    pd.testing.assert_frame_equal(a, b)
    assert a.empty or a.index.max() <= cutoff - pd.Timedelta(days=365)
    if len(a) > 1:
        ordered = pd.Series(a.index).sort_values()
        assert ordered.diff().dropna().min() >= pd.Timedelta(days=30)

def test_forward_return_summary(ohlcv):
    result = forward_returns(ohlcv, [ohlcv.index[100]], horizons=(30,))
    assert "return_30d" in result
    assert summarize_forward(result, 30)["count"] == 1

def test_score_is_explainable_and_bounded():
    weights = {"a": 70, "b": 30}
    result = calculate_score({"a": 2, "b": -.2}, weights)
    assert result.total == 70 and result.components == {"a": 70, "b": 0}

def test_backtest_executes_next_bar(ohlcv):
    frame = ohlcv.iloc[:20]
    scores = pd.Series(0, index=frame.index); scores.iloc[5] = 80
    result = run_backtest(frame, scores)
    assert result["entries"][0][0] == frame.index[6]
    assert result["entries"][0][1] == frame.open.iloc[6]

def test_walk_forward_disjoint(ohlcv):
    parts = list(splits(ohlcv.index, train_days=365, test_days=180, step_days=180))
    assert parts and parts[0]["train"][1] == parts[0]["test"][0]
    out = run_walk_forward(ohlcv, lambda f: len(f), train_days=365, test_days=180, step_days=180)
    assert out[0]["in_sample"] > out[0]["out_of_sample"]


def test_full_analysis_at_cutoff_ignores_future_prices(ohlcv):
    cutoff = ohlcv.index[1400]
    config = {"swings": {"1d": {"window": 10, "min_atr_move": 2.0}}, "similarity": {"neighbors": 10, "exclusion_days": 365, "min_history_days": 365, "min_case_spacing_days": 30}, "score_weights": {"long_term_trend": 20, "historical_similarity": 20, "fibonacci": 15, "elliott_abc": 15, "momentum_rsi": 10, "support_resistance": 10, "volume": 5, "risk_reward": 5}}
    original = analyze(ohlcv, config, as_of=cutoff)
    mutated = ohlcv.copy()
    mutated.loc[mutated.index > cutoff, ["open", "high", "low", "close"]] *= 100
    changed = analyze(mutated, config, as_of=cutoff)
    assert original["score"].total == changed["score"].total
    assert original["structure"] == changed["structure"]
    assert original["elliott_scenarios"] == changed["elliott_scenarios"]
