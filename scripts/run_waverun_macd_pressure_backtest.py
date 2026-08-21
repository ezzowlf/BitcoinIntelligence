"""Deterministic MACD-pressure backtest; deliberately no ranking or ML."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, minimum_filter1d

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_macd_pressure"
TARGETS = (100, 150, 200, 300, 400, 500)
HORIZONS = (300, 600, 900, 1800, 3600)
PERCENTILES = (0.80, 0.90, 0.95, 0.98, 0.99)
TIMEFRAMES = ("30s", "60s", "180s", "300s")
COST = 17.0
OUTCOME_CACHE: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}


def load() -> pd.DataFrame:
    frames = []
    for path in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path):
            continue
        try:
            columns = ["timestamp", "spot_price", "price_return_30s", "spot_futures_agreement", "expansion_score", "price_response_efficiency", "flow_price_absorption"]
            columns += [f"macd_{tf}_{suffix}" for tf in TIMEFRAMES for suffix in ("histogram", "histogram_slope", "histogram_acceleration", "macd_slope", "macd_acceleration", "cross_direction", "cross_age")]
            frame = pd.read_parquet(path, columns=columns)
        except (OSError, ValueError):
            continue
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frame["period"] = "Q1_2025" if "q1_2025" in str(path) else ("JUL_2026" if "2026\\07" in str(path) else "APR_JUN_2025")
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def outcome_arrays(price: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    step = 5
    steps = horizon // step
    future = price[1:][::-1]
    origin = (steps - 1) // 2
    hi = maximum_filter1d(future, steps, origin=origin, mode="nearest")[::-1]
    lo = minimum_filter1d(future, steps, origin=origin, mode="nearest")[::-1]
    long_entry = price + COST / 2
    short_entry = price - COST / 2
    long_mfe = np.full(len(price), np.nan); short_mfe = np.full(len(price), np.nan)
    long_mae = np.full(len(price), np.nan); short_mae = np.full(len(price), np.nan)
    long_mfe[:-1] = hi - long_entry[:-1]; short_mfe[:-1] = short_entry[:-1] - lo
    long_mae[:-1] = lo - long_entry[:-1]; short_mae[:-1] = short_entry[:-1] - hi
    long_mfe[len(price)-steps:] = np.nan; short_mfe[len(price)-steps:] = np.nan
    long_mae[len(price)-steps:] = np.nan; short_mae[len(price)-steps:] = np.nan
    return long_mfe, short_mfe, long_mae, short_mae


def decluster(frame: pd.DataFrame, mask: pd.Series) -> np.ndarray:
    idx = np.flatnonzero(mask.to_numpy())
    times = frame.timestamp.to_numpy(dtype="datetime64[s]")
    kept = []
    for i in idx:
        if not kept or times[i] - times[kept[-1]] >= np.timedelta64(180, "s"):
            kept.append(int(i))
    return np.asarray(kept, dtype=int)


def run_setup(frame: pd.DataFrame, mask: pd.Series, direction: str, threshold: float) -> list[dict]:
    selected = decluster(frame, mask)
    if not len(selected):
        return []
    price = frame.spot_price.to_numpy(float)
    rows = []
    for horizon in HORIZONS:
        key = (int(frame.index[0]), horizon)
        if key not in OUTCOME_CACHE:
            OUTCOME_CACHE[key] = outcome_arrays(price, horizon)
        lmfe, smfe, lmae, smae = OUTCOME_CACHE[key]
        mfe = lmfe if direction == "LONG" else smfe
        mae = lmae if direction == "LONG" else smae
        valid = selected[np.isfinite(mfe[selected])]
        for target in TARGETS:
            if not len(valid):
                continue
            values = mfe[valid]
            rows.append({"threshold": round((1-threshold)*100), "direction": direction, "horizon": horizon, "target": target, "N": len(valid), "target_reach_rate": float((values >= target).mean()), "net_positive_rate": float((values >= 0).mean()), "median_mfe": float(np.median(values)), "median_mae": float(np.median(mae[valid])), "signals_per_day": float(len(valid) / max((frame.timestamp.max()-frame.timestamp.min()).total_seconds()/86400, 1))})
    return rows


def main() -> None:
    frame = load()
    q1 = frame[frame.period == "Q1_2025"]
    results = []
    for tf in TIMEFRAMES:
        hist = frame[f"macd_{tf}_histogram"].abs()
        accel = frame[f"macd_{tf}_histogram_acceleration"].abs()
        for percentile in PERCENTILES:
            hist_threshold = float(q1[f"macd_{tf}_histogram"].abs().quantile(percentile))
            accel_threshold = float(q1[f"macd_{tf}_histogram_acceleration"].abs().quantile(percentile))
            for confirmation_name, confirmation in (("MACD_ONLY", pd.Series(True, index=frame.index)), ("MACD_PRICE", frame.price_return_30s.fillna(0).abs() > 0)):
                for extra_name, extra in (("NONE", pd.Series(True, index=frame.index)), ("SPOT_FUTURES", frame.spot_futures_agreement.fillna(0) > 0), ("EXPANSION", frame.expansion_score.fillna(0) > 0), ("FLOW_EFFICIENCY", frame.flow_price_absorption.fillna(0) < 0)):
                    long_mask = (frame[f"macd_{tf}_cross_direction"].fillna(0) > 0) & (frame[f"macd_{tf}_histogram"].fillna(0) > 0) & (frame[f"macd_{tf}_histogram_slope"].fillna(0) > 0) & (frame[f"macd_{tf}_histogram_acceleration"].fillna(0) > 0) & (hist >= hist_threshold) & (accel >= accel_threshold) & confirmation & extra
                    short_mask = (frame[f"macd_{tf}_cross_direction"].fillna(0) < 0) & (frame[f"macd_{tf}_histogram"].fillna(0) < 0) & (frame[f"macd_{tf}_histogram_slope"].fillna(0) < 0) & (frame[f"macd_{tf}_histogram_acceleration"].fillna(0) < 0) & (hist >= hist_threshold) & (accel >= accel_threshold) & confirmation & extra
                    for period in ("Q1_2025", "APR_JUN_2025", "JUL_2026"):
                        part = frame[frame.period == period].copy()
                        results += [{"timeframe": tf, "confirmation": confirmation_name, "extra_filter": extra_name, "period": period, **row} for row in run_setup(part, long_mask.loc[part.index], "LONG", percentile)]
                        results += [{"timeframe": tf, "confirmation": confirmation_name, "extra_filter": extra_name, "period": period, **row} for row in run_setup(part, short_mask.loc[part.index], "SHORT", percentile)]
    payload = {"execution": "DISABLED", "holdout_closed": ["2026-08-16", "2026-08-17"], "rows": len(frame), "cost_proxy_usd": COST, "historical_vantage": "UNAVAILABLE", "results": results}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "macd_pressure_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(frame), "result_rows": len(results), "output": str(OUT / 'macd_pressure_results.json')}, indent=2))


if __name__ == "__main__":
    main()
