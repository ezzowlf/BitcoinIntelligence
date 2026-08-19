from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_waverun_precision_research import (
    CALIBRATION,
    CORE_TRAIN,
    SLIPPAGE_ROUNDTRIP,
    VALIDATION,
    WALK_FORWARD,
    _columns,
    _fit_pair,
    _load,
    _matrices,
    _predictions,
)

from bitcoin_cycle_analyzer.short_term.research_protocol import (
    PROBABILITY_THRESHOLDS,
    ExperimentRegistry,
    wilson_interval,
)

HORIZON = 300
COVERAGE = 0.01


def _summary(selected: pd.DataFrame) -> dict:
    count = len(selected)
    wins = int(selected.correct.sum())
    ci = wilson_interval(wins, count) if count else (None, None)
    return {"signals": count, "wins": wins, "losses": count - wins, "precision": wins / count if count else None,
            "precision_ci95": list(ci), "net_ev": float(selected.net_return.mean()) if count else None}


def _top(predictions: pd.DataFrame) -> pd.DataFrame:
    valid = predictions[predictions.valid].nlargest(max(1, int(np.ceil(predictions.valid.sum() * COVERAGE))), "confidence")
    return valid


def _grouped(selected: pd.DataFrame, key: str, minimum: int = 30) -> list[dict]:
    output = []
    for value, group in selected.groupby(key):
        if len(group) >= minimum:
            output.append({key: int(value) if isinstance(value, (int, np.integer)) else str(value), **_summary(group)})
    return sorted(output, key=lambda row: (row["precision"], row["net_ev"]), reverse=True)


def _rule_metrics(frame: pd.DataFrame, mask: pd.Series, direction: np.ndarray) -> dict:
    gross = frame.gross_return_300s_d3.to_numpy()
    actual = (gross > 0).astype(int)
    long_net = frame.long_net_300s_d3.to_numpy() - SLIPPAGE_ROUNDTRIP
    short_net = frame.short_net_300s_d3.to_numpy() - SLIPPAGE_ROUNDTRIP
    valid = mask.to_numpy() & np.isfinite(gross) & np.isfinite(long_net) & np.isfinite(short_net)
    selected = pd.DataFrame({"correct": direction[valid] == actual[valid],
                             "net_return": np.where(direction[valid] == 1, long_net[valid], short_net[valid])})
    return _summary(selected)


def main() -> None:
    all_features, groups = _columns()
    core, calibration, validation, walk = (_load(days, all_features) for days in (CORE_TRAIN, CALIBRATION, VALIDATION, WALK_FORWARD))
    core_x, cal_x, val_x, walk_x = _matrices([core, calibration, validation, walk], all_features)
    pair = _fit_pair("logistic", core_x, core, cal_x, calibration, HORIZON)
    val_predictions = _predictions(pair, validation, val_x, HORIZON, 3)
    walk_predictions = _predictions(pair, walk, walk_x, HORIZON, 3)
    for column in ("day", "hour_utc", "weekday", "session", "regime", "spread_regime"):
        walk_predictions[column] = walk[column].to_numpy()
    walk_predictions["hour_berlin"] = (walk_predictions.hour_utc + 2) % 24
    selected = _top(walk_predictions)

    registry = ExperimentRegistry(ROOT / "runtime" / "waverun_data" / "derived" / "research" / "experiment_registry.jsonl")
    ablation_walk = []
    feature_sets = {"FULL": list(groups)}
    feature_sets.update({f"without_{excluded}": [group for group in groups if group != excluded] for excluded in groups})
    for label, included in feature_sets.items():
        features = sorted({column for group in included for column in groups[group]})
        core_subset, cal_subset, val_subset, walk_subset = _matrices([core, calibration, validation, walk], features)
        subset_pair = _fit_pair("logistic", core_subset, core, cal_subset, calibration, HORIZON)
        val_selected = _top(_predictions(subset_pair, validation, val_subset, HORIZON, 3))
        walk_all = _predictions(subset_pair, walk, walk_subset, HORIZON, 3)
        folds = []
        for day in WALK_FORWARD:
            mask = walk.day == day.isoformat()
            folds.append({"day": day.isoformat(), **_summary(_top(walk_all.loc[mask].reset_index(drop=True)))})
        record = {"label": label, "validation": _summary(val_selected), "walk_forward_combined": _summary(_top(walk_all)),
                  "walk_forward_folds": folds}
        ablation_walk.append(record)
        registry.append({"model": "logistic", "horizon_seconds": HORIZON, "feature_groups": included,
                         "strategy": "walk_forward_ablation", "thresholds_tested": list(PROBABILITY_THRESHOLDS),
                         "result": record})

    delay_sensitivity = []
    for delay in (0, 1, 2, 3, 5, 10):
        delay_predictions = _predictions(pair, walk, walk_x, HORIZON, delay)
        chosen = delay_predictions.loc[selected.index]
        delay_sensitivity.append({"reaction_delay_seconds": delay, **_summary(chosen[chosen.valid])})
    cost_sensitivity = []
    for bps in (0, 1, 2):
        adjusted = selected.copy()
        adjusted["net_return"] += SLIPPAGE_ROUNDTRIP - bps / 10_000
        cost_sensitivity.append({"slippage_roundtrip_bps": bps, **_summary(adjusted)})

    z = walk.mean_zscore.fillna(0)
    countertrend = (z < 0).astype(int).to_numpy()
    mr = {
        "MR_0_naive_zscore": _rule_metrics(walk, z.abs() >= 2, countertrend),
        "MR_1_displacement": _rule_metrics(walk, walk.mean_displacement >= 70, countertrend),
        "MR_2_plus_exhaustion": _rule_metrics(walk, (walk.mean_displacement >= 70) & (walk.exhaustion >= 60), countertrend),
        "MR_3_plus_absorption": _rule_metrics(walk, (walk.mean_displacement >= 70) & (walk.exhaustion >= 60) & (walk.absorption >= 60), countertrend),
        "MR_4_full_confirmation": _rule_metrics(walk, (walk.mean_displacement >= 70) & (walk.exhaustion >= 60) &
                                                (walk.absorption >= 60) & (walk.reversion_confirmation == 1), countertrend),
    }
    report = {"execution": "DISABLED", "status": "RESEARCH_ONLY", "holdout_opened": False,
              "selected_model": "logistic", "horizon_seconds": HORIZON, "coverage": COVERAGE,
              "validation": _summary(_top(val_predictions)), "walk_forward_combined": _summary(selected),
              "by_utc_hour": _grouped(selected, "hour_utc"), "by_berlin_hour": _grouped(selected, "hour_berlin"),
              "by_session": _grouped(selected, "session"), "by_regime": _grouped(selected, "regime"),
              "by_spread_regime": _grouped(selected, "spread_regime"), "by_weekday": _grouped(selected, "weekday"),
              "reaction_delay": delay_sensitivity, "cost_sensitivity": cost_sensitivity, "mean_reversion": mr,
              "ablation_walk_forward": ablation_walk, "multiple_testing": registry.counts(),
              "feature_groups": {key: len(value) for key, value in groups.items()},
              "time_filters_are_diagnostic_only": True}
    output = ROOT / "data" / "reports" / "waverun_selected_diagnostics.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
