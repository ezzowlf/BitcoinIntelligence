"""Winner-vs-loser forensics for the existing deterministic 30s MACD discovery class."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, minimum_filter1d
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_v5_3_macd_forensics"
FEATURES = ["macd_30s_cross_direction", "macd_30s_histogram", "macd_30s_histogram_slope", "macd_30s_histogram_acceleration", "price_return_30s", "price_acceleration_30s", "volatility_score", "flow_pressure", "spot_futures_agreement", "expansion_score", "price_response_efficiency", "flow_price_absorption"]
TARGETS = (100, 200, 300, 500)
HORIZONS = (300, 600, 900, 1800, 3600)
COST = 17.0


def load() -> pd.DataFrame:
    frames = []
    cols = ["timestamp", "spot_price", *FEATURES, "regime", "spot_pressure_10s", "futures_pressure_10s", "spot_cvd_acceleration", "futures_cvd_acceleration", "macd_60s_histogram", "macd_180s_histogram", "macd_300s_histogram"]
    for path in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path):
            continue
        try:
            d = pd.read_parquet(path, columns=cols)
        except (OSError, ValueError):
            continue
        d["timestamp"] = pd.to_datetime(d.timestamp, utc=True)
        d["period"] = "Q1_2025" if "q1_2025" in str(path) else ("JUL_2026" if "2026\\07" in str(path) else "APR_JUN_2025")
        frames.append(d)
    return pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    price = frame.spot_price.to_numpy(float)
    steps = 720  # 60 minutes at 5-second rows
    rev = price[1:][::-1]
    origin = (steps - 1) // 2
    hi = maximum_filter1d(rev, steps, origin=origin, mode="nearest")[::-1]
    lo = minimum_filter1d(rev, steps, origin=origin, mode="nearest")[::-1]
    frame = frame.copy()
    frame["long_mfe"] = np.nan; frame["short_mfe"] = np.nan; frame["long_mae"] = np.nan; frame["short_mae"] = np.nan
    frame.loc[: len(frame)-2, "long_mfe"] = hi - price[:-1] - COST/2
    frame.loc[: len(frame)-2, "short_mfe"] = price[:-1] - COST/2 - lo
    frame.loc[: len(frame)-2, "long_mae"] = lo - price[:-1] - COST/2
    frame.loc[: len(frame)-2, "short_mae"] = price[:-1] - COST/2 - hi
    frame.loc[len(frame)-steps:, ["long_mfe", "short_mfe", "long_mae", "short_mae"]] = np.nan
    return frame


def signals(frame: pd.DataFrame, threshold: float) -> pd.Series:
    q1 = frame[frame.period == "Q1_2025"]["macd_30s_histogram_acceleration"].abs().quantile(threshold)
    return (frame.macd_30s_cross_direction.fillna(0) < 0) & (frame.macd_30s_histogram.fillna(0) < 0) & (frame.macd_30s_histogram_slope.fillna(0) < 0) & (frame.macd_30s_histogram_acceleration.fillna(0) < 0) & (frame.macd_30s_histogram_acceleration.abs() >= q1) & (frame.macd_30s_histogram.abs() >= frame[frame.period == "Q1_2025"]["macd_30s_histogram"].abs().quantile(threshold))


def decluster(frame: pd.DataFrame, mask: pd.Series) -> np.ndarray:
    idx = np.flatnonzero(mask.to_numpy()); t = frame.timestamp.to_numpy(dtype="datetime64[s]"); keep = []
    for i in idx:
        if not keep or t[i] - t[keep[-1]] >= np.timedelta64(180, "s"):
            keep.append(int(i))
    return np.asarray(keep, dtype=int)


def classify(frame: pd.DataFrame, idx: np.ndarray) -> pd.DataFrame:
    rows = []
    times = frame.timestamp.to_numpy(dtype="datetime64[s]")
    prices = frame.spot_price.to_numpy(float)
    for i in idx:
        mfe = frame.short_mfe.iloc[i]
        if not np.isfinite(mfe):
            continue
        if mfe >= 500: group = "STRONG_WINNER"
        elif mfe >= 300: group = "MODERATE_WINNER"
        elif mfe >= 100: group = "LATE_WINNER"
        elif frame.short_mae.iloc[i] < -100: group = "ABSORBED"
        else: group = "FAILED_CONTINUATION"
        future_end = i + 720
        future = prices[i + 1:future_end + 1]
        future_times = times[i + 1:future_end + 1]
        valid = len(future) == 720 and future_times[-1] - times[i] <= np.timedelta64(3600, "s") if len(future) else False
        entry = prices[i] - COST / 2
        favorable = entry - future if valid else np.asarray([])
        def first_time(favorable: np.ndarray, level: float) -> float | None:
            hits = np.flatnonzero(favorable >= level)
            return None if len(hits) == 0 else float((hits[0] + 1) * 5)
        rows.append({"index": int(i), "period": frame.period.iloc[i], "timestamp": frame.timestamp.iloc[i].isoformat(), "group": group, "mfe_60m": float(mfe), "mae_60m": float(frame.short_mae.iloc[i]), "time_to_profit_s": first_time(favorable, 0), "time_to_100_s": first_time(favorable, 100), "time_to_500_s": first_time(favorable, 500)})
    return pd.DataFrame(rows)


def matched(frame: pd.DataFrame, cases: pd.DataFrame) -> list[dict]:
    winners = cases[cases.group.isin(["STRONG_WINNER", "MODERATE_WINNER", "LATE_WINNER"])].head(10)
    losers = cases[cases.group.isin(["FAILED_CONTINUATION", "ABSORBED"])].copy()
    if winners.empty or losers.empty:
        return []
    matrix = frame.loc[cases.index, FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(float)
    mean = matrix.mean(axis=0); std = np.where(matrix.std(axis=0) == 0, 1, matrix.std(axis=0)); matrix = (matrix-mean)/std
    win_pos = [list(cases.index).index(i) for i in winners.index]; lose_pos = [list(cases.index).index(i) for i in losers.index]
    dist = cdist(matrix[win_pos], matrix[lose_pos], metric="euclidean")
    result = []
    for wi, row in enumerate(winners.itertuples()):
        li = int(np.argmin(dist[wi])); loser = losers.iloc[li]; result.append({"winner": row._asdict(), "loser": loser.to_dict(), "distance": float(dist[wi, li])})
    return result


def main() -> None:
    frame = outcomes(load()); mask = signals(frame, 0.80); cases = classify(frame, decluster(frame, mask))
    if cases.empty:
        raise SystemExit("No MACD forensic cases found")
    counts = cases.groupby("group").size().to_dict()
    pairs = matched(frame, cases.set_index("index"))
    summaries = []
    winner_idx = cases[cases.group.str.contains("WINNER")].index
    loser_idx = cases[cases.group.isin(["FAILED_CONTINUATION", "ABSORBED"])].index
    for col in FEATURES:
        w = frame.loc[cases.loc[winner_idx, "index"], col].median(); l = frame.loc[cases.loc[loser_idx, "index"], col].median(); summaries.append({"feature": col, "winner_median": None if pd.isna(w) else float(w), "loser_median": None if pd.isna(l) else float(l), "difference": None if pd.isna(w) or pd.isna(l) else float(w-l)})
    payload = {"execution": "DISABLED", "holdout_closed": ["2026-08-16", "2026-08-17"], "population": {"threshold": "Q1 top 20%", "direction": "SHORT", "cases": len(cases), "groups": counts}, "matched_pairs": pairs, "feature_difference": summaries, "vantage_historical": "UNAVAILABLE", "l2_historical": "UNAVAILABLE"}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "forensics.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "groups": counts, "matched": len(pairs), "output": str(OUT / 'forensics.json')}, indent=2))


if __name__ == "__main__":
    main()
