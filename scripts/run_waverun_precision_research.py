from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.research_protocol import (
    PROBABILITY_THRESHOLDS,
    ExperimentRegistry,
    selective_metrics,
    wilson_interval,
)

HORIZONS = (30, 60, 90, 120, 180, 240, 300)
FEATURE_GROUPS = {
    "price": ("price_return_", "price_acceleration_", "price_pressure", "structure_break"),
    "macd": ("macd_",),
    "spot": ("spot_",),
    "futures": ("futures_",),
    "mean_reversion": ("mean_zscore", "mean_displacement", "exhaustion", "reversion_"),
    "absorption": ("flow_efficiency", "absorption"),
    "regime": ("volatility", "volatility_score", "spread_pct"),
    "origin": ("source_agreement", "source_divergence", "flow_pressure"),
}
SLIPPAGE_ROUNDTRIP = 0.0001
MIN_SIGNALS = 100
DERIVED = ROOT / "runtime" / "waverun_data" / "derived" / "research"


def _days(start: str, end: str) -> list[date]:
    return [day.date() for day in pd.date_range(start, end, freq="D")]


CORE_TRAIN = _days("2026-07-20", "2026-08-03")
CALIBRATION = _days("2026-08-04", "2026-08-06")
VALIDATION = _days("2026-08-07", "2026-08-11")
WALK_FORWARD = _days("2026-08-12", "2026-08-15")


def _path(day: date) -> Path:
    return DERIVED / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def _columns() -> tuple[list[str], dict[str, list[str]]]:
    names = pd.read_parquet(_path(CORE_TRAIN[0])).columns.tolist()
    groups = {group: sorted({name for name in names if any(name.startswith(prefix) for prefix in prefixes)})
              for group, prefixes in FEATURE_GROUPS.items()}
    excluded = {"price", "mid", "bid", "ask", "spread"}
    groups = {group: [name for name in columns if name not in excluded and not name.startswith(("long_net_", "short_net_", "gross_return_"))]
              for group, columns in groups.items()}
    return sorted(set().union(*groups.values())), groups


def _load(days: list[date], feature_columns: list[str]) -> pd.DataFrame:
    labels = [column for horizon in HORIZONS for delay in (0, 1, 2, 3, 5, 10)
              for column in (f"long_net_{horizon}s_d{delay}", f"short_net_{horizon}s_d{delay}", f"gross_return_{horizon}s_d{delay}")]
    columns = ["timestamp", "hour_utc", "weekday", "session", "regime", "spread_regime", *feature_columns, *labels]
    frames = [pd.read_parquet(_path(day), columns=columns).assign(day=day.isoformat()) for day in days]
    return pd.concat(frames, ignore_index=True)


def _matrices(frames: list[pd.DataFrame], features: list[str]) -> list[np.ndarray]:
    arrays = [frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32).copy() for frame in frames]
    medians = np.nanmedian(arrays[0], axis=0)
    medians[~np.isfinite(medians)] = 0
    for values in arrays:
        rows, columns = np.where(~np.isfinite(values))
        values[rows, columns] = medians[columns]
    means = arrays[0].mean(axis=0)
    scales = arrays[0].std(axis=0)
    scales[scales == 0] = 1
    return [((values - means) / scales).astype(np.float32) for values in arrays]


def _targets(frame: pd.DataFrame, horizon: int, delay: int = 3) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    gross = frame[f"gross_return_{horizon}s_d{delay}"].to_numpy()
    long_net = frame[f"long_net_{horizon}s_d{delay}"].to_numpy() - SLIPPAGE_ROUNDTRIP
    short_net = frame[f"short_net_{horizon}s_d{delay}"].to_numpy() - SLIPPAGE_ROUNDTRIP
    direction = (gross > 0).astype(int)
    move = (np.maximum(long_net, short_net) > 0).astype(int)
    valid = np.isfinite(gross) & np.isfinite(long_net) & np.isfinite(short_net)
    return direction, move, long_net, short_net, valid


class Platt:
    def fit(self, probability: np.ndarray, target: np.ndarray) -> Platt:
        from sklearn.linear_model import LogisticRegression

        clipped = np.clip(probability, 1e-6, 1 - 1e-6)
        self.model = LogisticRegression().fit(np.log(clipped / (1 - clipped)).reshape(-1, 1), target)
        return self

    def predict(self, probability: np.ndarray) -> np.ndarray:
        clipped = np.clip(probability, 1e-6, 1 - 1e-6)
        return self.model.predict_proba(np.log(clipped / (1 - clipped)).reshape(-1, 1))[:, 1]


def _model(name: str):
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=300, class_weight="balanced", C=0.3)
    if name == "gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=50,
                                              l2_regularization=1.0, random_state=42)
    if name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(n_estimators=120, max_depth=10, min_samples_leaf=30, max_features="sqrt",
                                      class_weight="balanced_subsample", n_jobs=-1, random_state=42)
    raise ValueError(name)


def _fit_pair(name: str, train_x: np.ndarray, train: pd.DataFrame, calibration_x: np.ndarray,
              calibration: pd.DataFrame, horizon: int):
    train_direction, train_move, _, _, train_valid = _targets(train, horizon)
    cal_direction, cal_move, _, _, cal_valid = _targets(calibration, horizon)
    direction_model, move_model = _model(name), _model(name)
    direction_model.fit(train_x[train_valid & (train_move == 1)], train_direction[train_valid & (train_move == 1)])
    move_model.fit(train_x[train_valid], train_move[train_valid])
    direction_calibrator = Platt().fit(direction_model.predict_proba(calibration_x[cal_valid])[:, 1], cal_direction[cal_valid])
    move_calibrator = Platt().fit(move_model.predict_proba(calibration_x[cal_valid])[:, 1], cal_move[cal_valid])
    return direction_model, move_model, direction_calibrator, move_calibrator


def _ece(probability: np.ndarray, target: np.ndarray, bins: int = 10) -> float:
    total = len(target)
    value = 0.0
    for low in np.linspace(0, 1, bins, endpoint=False):
        selected = (probability >= low) & (probability < low + 1 / bins)
        if selected.any():
            value += selected.mean() * abs(probability[selected].mean() - target[selected].mean())
    return float(value) if total else math.nan


def _evaluate(pair, frame: pd.DataFrame, matrix: np.ndarray, horizon: int, delay: int = 3) -> dict:
    from sklearn.metrics import brier_score_loss, log_loss

    predictions = _predictions(pair, frame, matrix, horizon, delay)
    direction = predictions.direction.to_numpy()
    move = predictions.move.to_numpy()
    p_up = predictions.p_up.to_numpy()
    confidence = predictions.confidence.to_numpy()
    net = predictions.net_return.to_numpy()
    correct = predictions.correct.to_numpy()
    valid = predictions.valid.to_numpy()
    predicted = predictions.predicted.to_numpy()
    probability_correct = np.where(predicted == 1, p_up, 1 - p_up)
    thresholds = []
    for threshold in PROBABILITY_THRESHOLDS:
        selected = valid & (confidence >= threshold)
        count = int(selected.sum())
        wins = int(correct[selected].sum())
        ci = wilson_interval(wins, count) if count else (None, None)
        thresholds.append({"threshold": threshold, "signals": count, "wins": wins, "losses": count - wins,
                           "precision": wins / count if count else None, "precision_ci95": list(ci),
                           "net_ev": float(net[selected].mean()) if count else None})
    return {"samples": int(valid.sum()), "move_prevalence": float(move[valid].mean()),
            "direction_brier": float(brier_score_loss(direction[valid], p_up[valid])),
            "direction_log_loss": float(log_loss(direction[valid], p_up[valid])),
            "direction_ece": _ece(p_up[valid], direction[valid]),
            "correctness_ece": _ece(probability_correct[valid], correct[valid].astype(int)),
            "coverage_curve": selective_metrics(confidence[valid], correct[valid], net[valid]), "thresholds": thresholds}


def _predictions(pair, frame: pd.DataFrame, matrix: np.ndarray, horizon: int, delay: int = 3) -> pd.DataFrame:
    direction_model, move_model, direction_calibrator, move_calibrator = pair
    direction, move, long_net, short_net, valid = _targets(frame, horizon, delay)
    p_up = direction_calibrator.predict(direction_model.predict_proba(matrix)[:, 1])
    p_move = move_calibrator.predict(move_model.predict_proba(matrix)[:, 1])
    predicted = (p_up >= 0.5).astype(int)
    confidence = p_move * np.maximum(p_up, 1 - p_up)
    net = np.where(predicted == 1, long_net, short_net)
    valid &= np.isfinite(confidence)
    return pd.DataFrame({"direction": direction, "move": move, "p_up": p_up, "p_move": p_move,
                         "predicted": predicted, "confidence": confidence, "correct": predicted == direction,
                         "net_return": net, "valid": valid})


def _ranking_cell(result: dict) -> dict:
    eligible = [row for row in result["coverage_curve"] if row["signals"] >= MIN_SIGNALS and row["net_ev"] > 0]
    return max(eligible, key=lambda row: (row["precision"], row["net_ev"]), default={"precision": 0, "net_ev": -1, "signals": 0, "coverage": None})


def main() -> None:
    all_features, groups = _columns()
    core = _load(CORE_TRAIN, all_features)
    calibration = _load(CALIBRATION, all_features)
    validation = _load(VALIDATION, all_features)
    walk = _load(WALK_FORWARD, all_features)
    core_x, calibration_x, validation_x, walk_x = _matrices([core, calibration, validation, walk], all_features)
    matrices = {"core": core_x, "calibration": calibration_x, "validation": validation_x, "walk": walk_x}
    registry = ExperimentRegistry(DERIVED / "experiment_registry.jsonl")
    results: dict[str, object] = {"execution": "DISABLED", "status": "RESEARCH_ONLY", "holdout_opened": False,
                                 "exploratory_used": False, "slippage_roundtrip": SLIPPAGE_ROUNDTRIP,
                                 "minimum_signals": MIN_SIGNALS, "screening": [], "ablations": [], "walk_forward": []}
    started = perf_counter()
    for model_name in ("logistic", "gradient_boosting", "random_forest"):
        for horizon in HORIZONS:
            fit_started = perf_counter()
            pair = _fit_pair(model_name, matrices["core"], core, matrices["calibration"], calibration, horizon)
            metrics = _evaluate(pair, validation, matrices["validation"], horizon)
            cell = _ranking_cell(metrics)
            experiment = {"model": model_name, "horizon_seconds": horizon, "feature_groups": list(groups),
                          "strategy": "two_stage_move_direction", "threshold": None,
                          "thresholds_tested": list(PROBABILITY_THRESHOLDS), "validation": metrics,
                          "ranking_cell": cell, "fit_seconds": perf_counter() - fit_started}
            experiment["experiment_id"] = registry.append(experiment)
            results["screening"].append(experiment)
            print(json.dumps({"model": model_name, "horizon": horizon, "cell": cell}), flush=True)

    best = max(results["screening"], key=lambda row: (row["ranking_cell"]["precision"], row["ranking_cell"]["net_ev"], row["ranking_cell"]["signals"]))
    best_model, best_horizon = best["model"], best["horizon_seconds"]
    feature_sets = {"FULL": list(groups)}
    for group in groups:
        feature_sets[f"without_{group}"] = [name for name in groups if name != group]
    ablation_pairs = {}
    for label, included_groups in feature_sets.items():
        features = sorted({column for group in included_groups for column in groups[group]})
        core_x, cal_x, val_x, walk_x = _matrices([core, calibration, validation, walk], features)
        pair = _fit_pair(best_model, core_x, core, cal_x, calibration, best_horizon)
        metrics = _evaluate(pair, validation, val_x, best_horizon)
        record = {"label": label, "model": best_model, "horizon_seconds": best_horizon,
                  "feature_groups": included_groups, "ranking_cell": _ranking_cell(metrics), "validation": metrics}
        record["experiment_id"] = registry.append({**record, "strategy": "feature_ablation"})
        results["ablations"].append(record)
        ablation_pairs[label] = (pair, walk_x)

    full_pair, full_walk_x = ablation_pairs["FULL"]
    validation_cell = _ranking_cell(next(row["validation"] for row in results["ablations"] if row["label"] == "FULL"))
    selected_coverage = validation_cell["coverage"]
    for day in WALK_FORWARD:
        selected = walk.day == day.isoformat()
        metrics = _evaluate(full_pair, walk.loc[selected].reset_index(drop=True), full_walk_x[selected], best_horizon)
        cell = next((row for row in metrics["coverage_curve"] if row["coverage"] == selected_coverage), _ranking_cell(metrics))
        results["walk_forward"].append({"day": day.isoformat(), "metrics": metrics, "selected_cell": cell})

    stable = bool(selected_coverage is not None and validation_cell["signals"] >= MIN_SIGNALS and validation_cell["net_ev"] > 0 and
                  all(row["selected_cell"]["signals"] >= 20 and row["selected_cell"]["net_ev"] > 0 and row["selected_cell"]["precision"] >= 0.55
                      for row in results["walk_forward"]))
    results["selection"] = {"model": best_model, "horizon_seconds": best_horizon, "validation_cell": validation_cell,
                            "walk_forward_stable": stable, "candidate_frozen": False,
                            "holdout_decision": "ELIGIBLE_FOR_FREEZE" if stable else "KEEP_LOCKED"}
    results["multiple_testing"] = registry.counts()
    results["runtime_seconds"] = perf_counter() - started
    output = ROOT / "data" / "reports" / "waverun_precision_research.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"selection": results["selection"], "multiple_testing": results["multiple_testing"],
                      "runtime_seconds": results["runtime_seconds"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
