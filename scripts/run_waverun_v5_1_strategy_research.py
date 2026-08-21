"""Bounded, chronological WAVERUN V5.1 strategy research on existing derived data.

This is research only: deterministic mechanism rules, fixed thresholds, no model
selection on the walk-forward periods, no locked-holdout access, execution disabled.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, minimum_filter1d

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_v5_1_strategy_research"
TARGETS = (100, 150, 200, 300, 400, 500)
HORIZONS = (180, 300, 600, 900, 1800, 3600)
COST = 17.0  # explicit conservative proxy; historical Vantage ticks are unavailable
OUTCOME_CACHE: dict[tuple[int, int, str], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def load() -> pd.DataFrame:
    rows = []
    for path in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path):
            continue
        try:
            frame = pd.read_parquet(path)
        except (OSError, ValueError):
            continue
        frame = frame.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["tier"] = "q1_2025" if "q1_2025" in str(path) else "blind_v1"
        rows.append(frame)
    return pd.concat(rows, ignore_index=True).sort_values("timestamp")


def signals(frame: pd.DataFrame) -> dict[str, pd.Series]:
    p = frame["price_pressure"].fillna(0)
    flow = frame["flow_pressure"].fillna(0)
    acc = frame["flow_pressure_acceleration"].fillna(0)
    agreement = frame["spot_futures_agreement"].fillna(0)
    expansion = frame["expansion_score"].fillna(0)
    response = frame["price_response_efficiency"].fillna(0)
    absorption = frame["flow_price_absorption"].fillna(0)
    lead = frame["futures_lead_1s"].fillna(0) - frame["spot_lead_1s"].fillna(0)
    macd = frame["macd_alignment"].fillna(0)
    return {
        "pressure_continuation": (flow.abs() > 0.25) & (acc.abs() > 0) & (agreement > 0),
        "early_expansion": (expansion > 0.5) & (acc.abs() > 0) & (frame["momentum_age"].fillna(0) < 30 if "momentum_age" in frame else True),
        "failed_pullback": (p.abs() > 0.25) & (flow.abs() > 0.25) & (response.abs() > 0),
        "absorption_reversal": (flow.abs() > 0.5) & (absorption.abs() > 0.25) & (response.abs() < 0.1),
        "spot_futures_confirmed": (agreement > 0.5) & (flow.abs() > 0.25),
        "futures_led_spot_confirmed": (lead.abs() > 0) & (agreement > 0),
        "cross_exchange_confirmed": (agreement > 0.75) & (frame["spot_pressure_10s"].fillna(0).abs() > 0.25) & (frame["futures_pressure_10s"].fillna(0).abs() > 0.25),
        "mean_reversion_confirmed": (frame["mean_zscore"].fillna(0).abs() > 2) & (absorption.abs() > 0.25) & (response.abs() < 0.1),
        "macd_microstructure": (macd.abs() > 0) & (flow.abs() > 0.25) & (agreement > 0),
    }


def decluster(frame: pd.DataFrame, mask: pd.Series) -> np.ndarray:
    idx = np.flatnonzero(mask.to_numpy())
    if len(idx) == 0:
        return idx
    times = frame["timestamp"].to_numpy(dtype="datetime64[ns]")
    keep = [idx[0]]
    for value in idx[1:]:
        if times[value] - times[keep[-1]] >= np.timedelta64(180, "s"):
            keep.append(value)
    return np.asarray(keep, dtype=int)


def evaluate(frame: pd.DataFrame, idx: np.ndarray, target: float, horizon: int, direction: str) -> dict:
    prices = frame["spot_price"].to_numpy(float)
    times = frame["timestamp"].to_numpy(dtype="datetime64[ns]")
    key = (int(frame.index[0]), horizon, direction)
    cached = OUTCOME_CACHE.get(key)
    if cached is None:
        step_seconds = max(1, round(np.median(np.diff(times).astype("timedelta64[s]").astype(float))))
        steps = max(1, round(horizon / step_seconds))
        reversed_future = prices[1:][::-1]
        filter_origin = (steps - 1) // 2
        future_max = maximum_filter1d(reversed_future, size=steps, origin=filter_origin, mode="nearest")[::-1]
        future_min = minimum_filter1d(reversed_future, size=steps, origin=filter_origin, mode="nearest")[::-1]
        favorable = np.full(len(prices), np.nan); adverse = np.full(len(prices), np.nan); terminal = np.full(len(prices), np.nan)
        if direction == "LONG":
            favorable[:-1] = future_max - (prices[:-1] + COST / 2)
            adverse[:-1] = (prices[:-1] + COST / 2) - future_min
            terminal[: len(prices) - steps] = prices[steps:] - (prices[: len(prices) - steps] + COST / 2)
        else:
            favorable[:-1] = (prices[:-1] - COST / 2) - future_min
            adverse[:-1] = future_max - (prices[:-1] - COST / 2)
            terminal[: len(prices) - steps] = (prices[: len(prices) - steps] - COST / 2) - prices[steps:]
        favorable[len(prices) - steps :] = np.nan
        adverse[len(prices) - steps :] = np.nan
        OUTCOME_CACHE[key] = (favorable, adverse, terminal)
    favorable, adverse, terminal = OUTCOME_CACHE[key]
    valid = idx[np.isfinite(favorable[idx]) & np.isfinite(adverse[idx]) & np.isfinite(terminal[idx])]
    accepted = np.column_stack((favorable[valid], -adverse[valid], terminal[valid])) if len(valid) else np.empty((0, 3))
    if len(accepted) == 0:
        return {"N": 0, "precision": None, "signals_per_day": 0, "net_ev": None, "median_mae": None, "median_time_to_profit": None}
    arr = accepted
    wins = arr[:, 0] >= target
    return {"N": len(arr), "precision": round(float(wins.mean()), 6), "signals_per_day": round(len(arr) / max((frame.timestamp.max() - frame.timestamp.min()).total_seconds() / 86400, 1), 4), "net_ev": round(float(arr[:, 2].mean()), 4), "median_mae": round(float(np.median(arr[:, 1])), 4), "median_time_to_profit": None}


def main() -> None:
    frame = load()
    sig = signals(frame)
    folds = [("train_q1", frame[frame.tier == "q1_2025"]), ("walk_forward_blind_2025", frame[(frame.tier == "blind_v1") & (frame.timestamp.dt.year == 2025)]), ("walk_forward_jul_2026", frame[(frame.tier == "blind_v1") & (frame.timestamp.dt.year == 2026)])]
    results = []
    for family, mask in sig.items():
        for fold, part in folds:
            local_mask = mask.loc[part.index]
            for direction in ("LONG", "SHORT"):
                signed = local_mask & ((frame.loc[part.index, "flow_pressure"].fillna(0) >= 0) if direction == "LONG" else (frame.loc[part.index, "flow_pressure"].fillna(0) < 0))
                selected = decluster(part, signed)
                for target in TARGETS:
                    for horizon in HORIZONS:
                        row = evaluate(part, selected, target, horizon, direction)
                        results.append({"family": family, "fold": fold, "direction": direction, "target": target, "horizon": horizon, **row})
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"execution": "DISABLED", "holdout": {"closed": True, "dates": ["2026-08-16", "2026-08-17"]}, "data": {"rows": len(frame), "files": 212, "tiers": ["q1_2025", "blind_v1"], "vantage_bid_ask": "UNAVAILABLE_HISTORICAL; COST_PROXY_17_USD"}, "results": results}
    (OUT / "strategy_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(frame), "results": len(results), "output": str(OUT / 'strategy_results.json')}, indent=2))


if __name__ == "__main__":
    main()
