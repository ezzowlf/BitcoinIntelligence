from __future__ import annotations
import pandas as pd
from .indicators import add_indicators
from .swing_detection import detect_swings
from .market_structure import classify_structure
from .fibonacci import from_swings, confluence_zones
from .elliott_wave import analyze_scenarios
from .similarity import find_similar, forward_returns, summarize_forward
from .opportunity_score import calculate_score, states
from .zones import build_zones


def analyze(frame: pd.DataFrame, config: dict, as_of=None) -> dict:
    visible = frame.loc[:as_of].copy() if as_of is not None else frame.copy()
    enriched = add_indicators(visible)
    settings = config["swings"].get("1d", {"window": 10, "min_atr_move": 2})
    swings = detect_swings(enriched, **settings)
    structure = classify_structure(swings)
    fibs = from_swings(swings)
    confluences = confluence_zones(fibs)
    scenarios = analyze_scenarios(swings)
    similar = find_similar(enriched, neighbors=config["similarity"]["neighbors"], exclusion_days=config["similarity"]["exclusion_days"], min_history_days=config["similarity"]["min_history_days"], min_case_spacing_days=config["similarity"].get("min_case_spacing_days", 30))
    returns = forward_returns(enriched, similar.index, horizons=(365,))
    summary = summarize_forward(returns, 365)
    row = enriched.iloc[-1]
    fib_signal = 0 if not confluences else max(0, 1 - abs(confluences[0]["center"] / row.close - 1) / .3)
    signals = {"long_term_trend": .9 if row.close > row.ema_200 else .35, "historical_similarity": summary.get("win_rate", .5), "fibonacci": fib_signal, "elliott_abc": scenarios[0]["confidence"] / 100, "momentum_rsi": max(0, min(1, (70 - row.rsi_14) / 40)) if pd.notna(row.rsi_14) else .5, "support_resistance": .7 if structure["support"] and row.close >= structure["support"] else .4, "volume": min(1, row.get("volume_ratio", 1) / 2) if pd.notna(row.get("volume_ratio")) else .5, "risk_reward": .6}
    score = calculate_score(signals, config["score_weights"], {k: f"normalized input {v:.2f}" for k, v in signals.items()})
    status = states(score, .7 if structure["trend"] == "bullish" else .3, min(1, abs(float(row.drawdown))))
    return {"timestamp": enriched.index[-1], "price": float(row.close), "drawdown_from_ath": float(row.drawdown), "score": score, "states": status, "structure": structure, "fibonacci_levels": fibs, "confluence_zones": confluences, "elliott_scenarios": scenarios, "similar_cases": similar, "forward_summary_365d": summary, "zones": build_zones(float(row.close), confluences, structure["support"], scenarios), "data": enriched, "swings": swings}
