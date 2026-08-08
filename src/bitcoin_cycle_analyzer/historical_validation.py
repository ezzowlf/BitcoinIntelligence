from __future__ import annotations
import numpy as np
import pandas as pd
from .indicators import add_indicators
from .swing_detection import detect_swings, swings_as_of
from .market_structure import classify_structure
from .fibonacci import from_swings, confluence_zones
from .elliott_wave import analyze_scenarios
from .similarity import find_similar, forward_returns, summarize_forward, evidence_label
from .opportunity_score import calculate_score
from .backtesting import run_backtest

HORIZONS = (7, 30, 90, 180, 365, 730)
THRESHOLDS = (60, 70, 75, 80, 85, 90)


def build_point_in_time_scores(frame: pd.DataFrame, config: dict, start_after: int = 400) -> pd.DataFrame:
    enriched = add_indicators(frame)
    settings = config["swings"]["1d"]
    all_swings = detect_swings(enriched, **settings)
    rows = []
    similarity_cfg = config["similarity"]
    for position in range(start_after, len(enriched)):
        date = enriched.index[position]
        row = enriched.iloc[position]
        known_swings = swings_as_of(all_swings, date)
        structure = classify_structure(known_swings)
        fibs = from_swings(known_swings)
        confluences = confluence_zones(fibs)
        scenarios = analyze_scenarios(known_swings)
        similar = find_similar(enriched, as_of=date, **similarity_cfg)
        known = enriched.loc[:date]
        returns = forward_returns(known, similar.index, horizons=(365,))
        summary = summarize_forward(returns, 365)
        fib_signal = 0 if not confluences else max(0, 1 - abs(confluences[0]["center"] / row.close - 1) / .3)
        signals = {
            "long_term_trend": .9 if pd.notna(row.ema_200) and row.close > row.ema_200 else .35,
            "historical_similarity": summary.get("win_rate", .5),
            "fibonacci": fib_signal,
            "elliott_abc": scenarios[0]["confidence"] / 100,
            "momentum_rsi": max(0, min(1, (70 - row.rsi_14) / 40)) if pd.notna(row.rsi_14) else .5,
            "support_resistance": .7 if structure["support"] and row.close >= structure["support"] else .4,
            "volume": min(1, row.volume_ratio / 2) if pd.notna(row.volume_ratio) else .5,
            "risk_reward": .6,
        }
        result = calculate_score(signals, config["score_weights"])
        output = {"date": date, "price": float(row.close), "score": result.total, "market_phase": structure["trend"], "elliott_scenario": scenarios[0]["name"], "elliott_confidence": scenarios[0]["confidence"], "fib_confluence_count": confluences[0]["count"] if confluences else 0, "similarity_n": summary.get("count", 0), "evidence": evidence_label(summary.get("count", 0))}
        output.update({f"component_{key}": value for key, value in result.components.items()})
        rows.append(output)
    return pd.DataFrame(rows).set_index("date")


def signal_rows(frame: pd.DataFrame, scores: pd.DataFrame, threshold: float) -> pd.DataFrame:
    crossing = (scores.score >= threshold) & (scores.score.shift(1, fill_value=0) < threshold)
    signals = scores[crossing].copy()
    if signals.empty:
        return signals
    future = forward_returns(frame, signals.index, HORIZONS)
    signals = signals.join(future)
    details = []
    for date, signal in signals.iterrows():
        pos = frame.index.get_indexer([date], method="nearest")[0]
        entry = signal.price
        future_window = frame.iloc[pos + 1:min(pos + 731, len(frame))]
        if future_window.empty:
            details.append((np.nan, np.nan, np.nan, np.nan))
            continue
        low_date = future_window.low.idxmin()
        below = future_window.close < entry
        after_below = below.cummax()
        recovered = future_window[(future_window.close >= entry) & after_below]
        details.append((float(future_window.low.min() / entry - 1), int((low_date - date).days), None if recovered.empty else int((recovered.index[0] - date).days), float(future_window.high.max() / entry - 1)))
    signals[["max_drawdown_after", "days_to_low", "days_to_breakeven", "max_positive_move"]] = details
    return signals


def aggregate_signals(signals: pd.DataFrame) -> dict:
    result = {"signal_count": len(signals), "evidence": evidence_label(len(signals))}
    for horizon in HORIZONS:
        column = f"return_{horizon}d"
        if column not in signals:
            continue
        values = signals[column].dropna()
        result[f"{horizon}d"] = {"n": len(values)} if values.empty else {"n": len(values), "mean": float(values.mean()), "median": float(values.median()), "min": float(values.min()), "max": float(values.max()), "q10": float(values.quantile(.1)), "q25": float(values.quantile(.25)), "q75": float(values.quantile(.75)), "q90": float(values.quantile(.9)), "positive_rate": float((values > 0).mean())}
    dd = signals.max_drawdown_after.dropna() if "max_drawdown_after" in signals else pd.Series(dtype=float)
    result["drawdown"] = {"median": None if dd.empty else float(dd.median()), "worst": None if dd.empty else float(dd.min())}
    return result


def baseline_scores(frame: pd.DataFrame, enriched: pd.DataFrame) -> dict[str, pd.Series]:
    weekly = add_indicators(frame.resample("W-MON", label="right", closed="right").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna())
    weekly_rsi = weekly.rsi_14.reindex(frame.index, method="ffill")
    return {
        "weekly_rsi_below_35": pd.Series(np.where(weekly_rsi < 35, 100, 0), index=frame.index),
        "weekly_rsi_below_30": pd.Series(np.where(weekly_rsi < 30, 100, 0), index=frame.index),
        "drawdown_30": pd.Series(np.where(enriched.drawdown <= -.30, 100, 0), index=frame.index),
        "drawdown_50": pd.Series(np.where(enriched.drawdown <= -.50, 100, 0), index=frame.index),
        "drawdown_70": pd.Series(np.where(enriched.drawdown <= -.70, 100, 0), index=frame.index),
    }


def cycle_for(date: pd.Timestamp) -> str:
    boundaries = [("early Bitcoin", "2012-11-28"), ("2013/2014", "2016-07-09"), ("2017/2018", "2020-05-11"), ("2020/2021", "2021-11-10"), ("2021/2022", "2024-04-20")]
    for name, end in boundaries:
        if date < pd.Timestamp(end, tz="UTC"):
            return name
    return "current cycle"


def validate(frame: pd.DataFrame, config: dict) -> tuple[dict, pd.DataFrame]:
    scores = build_point_in_time_scores(frame, config)
    enriched = add_indicators(frame)
    report = {"data": {"from": str(frame.index.min()), "to": str(frame.index.max()), "rows": len(frame)}, "thresholds": {}, "cycles": {}, "baselines": {}, "components": {}, "elliott": {}, "walk_forward": []}
    for threshold in THRESHOLDS:
        signals = signal_rows(frame, scores, threshold)
        report["thresholds"][str(threshold)] = aggregate_signals(signals)
        report["thresholds"][str(threshold)]["signals"] = [{"date": str(date), **{key: (None if pd.isna(value) else value.item() if hasattr(value, "item") else value) for key, value in row.items()}} for date, row in signals.iterrows()]
        for cycle in sorted({cycle_for(x) for x in signals.index}):
            subset = signals[[cycle_for(x) == cycle for x in signals.index]]
            report["cycles"].setdefault(cycle, {})[str(threshold)] = aggregate_signals(subset)
    aligned = frame.loc[scores.index]
    for threshold in THRESHOLDS:
        report["thresholds"][str(threshold)]["portfolio"] = {key: value for key, value in run_backtest(aligned, scores.score, threshold=threshold).items() if key not in {"entries", "equity"}}
    for name, series in baseline_scores(frame, enriched).items():
        series = series.loc[scores.index]
        report["baselines"][name] = aggregate_signals(signal_rows(frame, pd.DataFrame({"score": series, "price": frame.close.reindex(series.index)}), 75))
    for name in config["score_weights"]:
        normalized = scores[f"component_{name}"] / config["score_weights"][name] * 100
        proxy = pd.DataFrame({"score": normalized, "price": scores.price})
        report["components"][name] = aggregate_signals(signal_rows(frame, proxy, 75))
    without = (scores.score - scores.component_elliott_abc) / 85 * 100
    report["elliott"]["with_component"] = aggregate_signals(signal_rows(frame, scores, 75))
    report["elliott"]["without_component"] = aggregate_signals(signal_rows(frame, pd.DataFrame({"score": without, "price": scores.price}), 75))
    report["elliott"]["confidence_distribution"] = scores.elliott_confidence.describe(percentiles=[.1,.25,.5,.75,.9]).to_dict()
    fold_starts = [pd.Timestamp(x, tz="UTC") for x in ("2016-07-09", "2020-05-11", "2024-04-20")]
    for number, test_start in enumerate(fold_starts, 1):
        next_start = fold_starts[number] if number < len(fold_starts) else scores.index.max() + pd.Timedelta(days=1)
        train_scores = scores[scores.index < test_start]
        test_scores = scores[(scores.index >= test_start) & (scores.index < next_start)]
        if train_scores.empty or test_scores.empty:
            continue
        train_signals = signal_rows(frame, train_scores, 75)
        test_signals = signal_rows(frame, test_scores, 75)
        test_bt = run_backtest(frame.loc[test_scores.index], test_scores.score, threshold=75)
        report["walk_forward"].append({"fold": number, "parameters": {"score_threshold": 75, "config_version": config["version"]}, "train_period": [str(train_scores.index.min()), str(train_scores.index.max())], "test_period": [str(test_scores.index.min()), str(test_scores.index.max())], "in_sample": aggregate_signals(train_signals), "out_of_sample": aggregate_signals(test_signals), "test_portfolio": {key: value for key, value in test_bt.items() if key not in {"entries", "equity"}}})
    return report, scores
