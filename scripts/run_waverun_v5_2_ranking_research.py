"""V5.2 adaptive daily opportunity ranking research.

Research-only. Uses existing causal derived data, chronological train/test,
day-local top-k selection, and an explicit cost proxy where Vantage history is
not available. No production wiring and no holdout access.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reports" / "waverun_v5_2_ranking_research"
COST = 17.0
TARGET = 100.0
HORIZON = 300
FEATURE_GROUPS = {
    "PRICE": ["price_return_10s", "price_return_30s", "price_acceleration_30s", "price_response_efficiency"],
    "FLOW": ["flow_pressure", "flow_pressure_acceleration", "spot_cvd_acceleration", "futures_cvd_acceleration", "spot_pressure_persistence"],
    "CROSS_MARKET": ["spot_futures_agreement", "spot_lead_1s", "futures_lead_1s"],
    "MACD": ["macd_alignment", "macd_acceleration", "macd_10s_histogram_acceleration"],
    "REGIME": ["volatility_score", "expansion_score", "mean_zscore"],
}
FEATURES = [c for cols in FEATURE_GROUPS.values() for c in cols]


def load() -> pd.DataFrame:
    frames = []
    for path in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(path) or "2026\\08\\17" in str(path):
            continue
        try:
            frame = pd.read_parquet(path, columns=["timestamp", "spot_price", "regime", *FEATURES])
        except (OSError, ValueError):
            continue
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["tier"] = "q1_2025" if "q1_2025" in str(path) else "blind"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    price = frame.spot_price.to_numpy(float)
    step = max(1, round(np.median(np.diff(frame.timestamp.to_numpy(dtype="datetime64[s]")).astype(float))))
    steps = max(1, round(HORIZON / step))
    future = price[1:][::-1]
    from scipy.ndimage import maximum_filter1d, minimum_filter1d
    origin = (steps - 1) // 2
    hi = maximum_filter1d(future, steps, origin=origin, mode="nearest")[::-1]
    lo = minimum_filter1d(future, steps, origin=origin, mode="nearest")[::-1]
    long_entry = price + COST / 2
    short_entry = price - COST / 2
    frame = frame.copy()
    frame["long_mfe"] = np.nan
    frame["short_mfe"] = np.nan
    frame.loc[: len(frame) - 2, "long_mfe"] = hi - long_entry[:-1]
    frame.loc[: len(frame) - 2, "short_mfe"] = short_entry[:-1] - lo
    frame["long_terminal"] = np.nan
    frame["short_terminal"] = np.nan
    frame.loc[: len(frame) - steps - 1, "long_terminal"] = price[steps:] - long_entry[: len(price) - steps]
    frame.loc[: len(frame) - steps - 1, "short_terminal"] = short_entry[: len(price) - steps] - price[steps:]
    frame["long_label"] = frame.long_mfe >= TARGET
    frame["short_label"] = frame.short_mfe >= TARGET
    frame.loc[frame.long_mfe.isna(), "long_label"] = False
    frame.loc[frame.short_mfe.isna(), "short_label"] = False
    return frame


def decluster(indices: np.ndarray, times: pd.Series | np.ndarray, cooldown=180) -> np.ndarray:
    kept = []
    for i in indices:
        if not kept or times[i] - times[kept[-1]] >= np.timedelta64(cooldown, "s"):
            kept.append(int(i))
    return np.asarray(kept, dtype=int)


def fit_score(train: pd.DataFrame, test: pd.DataFrame, direction: str, cols: list[str], model_name: str) -> tuple[np.ndarray, np.ndarray | None]:
    label = f"{direction}_label"
    usable = train[cols + [label]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(usable) > 200_000:
        usable = usable.iloc[:: max(1, len(usable) // 200_000)]
    if model_name == "LOGISTIC":
        model = make_pipeline(StandardScaler(), LogisticRegression(C=0.25, max_iter=300, class_weight="balanced"))
    elif model_name == "HISTGB":
        model = HistGradientBoostingClassifier(max_iter=80, max_leaf_nodes=15, l2_regularization=1.0, random_state=0)
    else:
        model = ExtraTreesClassifier(n_estimators=80, max_depth=12, min_samples_leaf=50, n_jobs=-1, random_state=0, class_weight="balanced")
    model.fit(usable[cols], usable[label].astype(int))
    x = test[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    coef = model.named_steps["logisticregression"].coef_[0] if model_name == "LOGISTIC" else None
    return model.predict_proba(x)[:, 1], coef


def topk_metrics(test: pd.DataFrame, score: np.ndarray, direction: str) -> list[dict]:
    test = test.copy(); test["rank_score"] = score
    times = test.timestamp
    rows = []
    for day, day_frame in test.groupby(test.timestamp.dt.date, sort=True):
        base = day_frame.index.to_numpy()
        eligible = base[np.isfinite(day_frame.loc[base, "rank_score"].to_numpy())]
        eligible = decluster(eligible, times)
        eligible = eligible[np.argsort(test.loc[eligible, "rank_score"].to_numpy())[::-1]]
        for k in (3, 5, 7, 10):
            selected = eligible[:k]
            if not len(selected):
                rows.append({"day": str(day), "k": k, "N": 0, "precision": None, "net_positive": None, "median_mae": None})
                continue
            mfe = test.loc[selected, f"{direction}_mfe"]
            terminal = test.loc[selected, f"{direction}_terminal"]
            rows.append({"day": str(day), "k": k, "N": len(selected), "precision": float(mfe.ge(TARGET).mean()), "net_positive": float(terminal.gt(0).mean()), "median_mae": None})
    return rows


def main() -> None:
    frame = outcomes(load())
    train = frame[frame.tier == "q1_2025"].copy()
    test = frame[frame.tier == "blind"].copy()
    test_2025 = test[test.timestamp.dt.year == 2025].copy()
    test_2026 = test[test.timestamp.dt.year == 2026].copy()
    results = []
    ablation = []
    for model_name in ("LOGISTIC", "HISTGB", "EXTRATREES"):
      for group_name, cols in {"CORE": FEATURES, "PRICE_ONLY": FEATURE_GROUPS["PRICE"], "CORE_NO_MACD": [c for c in FEATURES if c not in FEATURE_GROUPS["MACD"]]}.items():
        for direction in ("long", "short"):
            for period, period_frame in (("blind_2025", test_2025), ("jul_2026", test_2026)):
                score, coef = fit_score(train, period_frame, direction, cols, model_name)
                rows = topk_metrics(period_frame, score, direction)
                summary = pd.DataFrame(rows).groupby("k").agg(days=("day", "nunique"), signals=("N", "sum"), precision=("precision", "mean"), net_positive=("net_positive", "mean"), zero_signal_days=("N", lambda x: int((x == 0).sum()))).reset_index()
                for row in summary.to_dict("records"):
                    results.append({"model": model_name, "feature_set": group_name, "direction": direction.upper(), "period": period, **row})
                if group_name != "PRICE_ONLY" and coef is not None:
                    ablation.append({"model": model_name, "feature_set": group_name, "direction": direction.upper(), "period": period, "coefficient_l1": float(np.abs(coef).sum()), "features": cols})
    payload = {"execution": "DISABLED", "holdout_closed": ["2026-08-16", "2026-08-17"], "rows": len(frame), "train_rows": len(train), "test_rows": len(test), "target": TARGET, "horizon_seconds": HORIZON, "cost_proxy_usd": COST, "vantage_historical": "UNAVAILABLE", "results": results, "ablation": ablation}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ranking_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(frame), "train": len(train), "test": len(test), "results": len(results), "output": str(OUT / 'ranking_results.json')}, indent=2))


if __name__ == "__main__":
    main()
