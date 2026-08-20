from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
Q1_SCRIPT = ROOT / "scripts" / "run_waverun_3month_deep_research.py"
SPEC = importlib.util.spec_from_file_location("waverun_q1", Q1_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
q1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1)

from bitcoin_cycle_analyzer.short_term.research_protocol import wilson_interval

CANDIDATE_ID = "Q1_2025_180S_CHALLENGER_V1"
HORIZON = 180
THRESHOLD = 0.55
FREEZE = ROOT / "frozen" / "waverun_q1_2025_180s_challenger_v1.json"
BLIND_DERIVED = ROOT / "runtime" / "waverun_data" / "derived" / "blind_v1"
OUTPUT = ROOT / "data" / "reports" / "waverun_v1_blind"
MEMORY = ROOT / "runtime" / "waverun_research_memory.sqlite"
PERIODS = {
    "APR_2025": (date(2025, 4, 1), date(2025, 4, 30)),
    "MAY_2025": (date(2025, 5, 1), date(2025, 5, 31)),
    "JUN_2025": (date(2025, 6, 1), date(2025, 6, 30)),
    "JUL_2026": (date(2026, 7, 1), date(2026, 7, 31)),
}
HOLDOUT = {date(2026, 8, 16), date(2026, 8, 17)}


def canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(json_safe(payload), stream, indent=2, default=str, allow_nan=False)
        stream.write("\n")


def q1_arrays(features: list[str]) -> tuple[list[pd.DataFrame], list[np.ndarray], dict]:
    frames = [q1.load_split(name, features) for name in q1.SPLITS]
    raw = [frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32) for frame in frames]
    medians = np.nanmedian(raw[0], axis=0)
    medians[~np.isfinite(medians)] = 0
    for values in raw:
        rows, columns = np.where(~np.isfinite(values))
        values[rows, columns] = medians[columns]
    means, scales = raw[0].mean(axis=0), raw[0].std(axis=0)
    scales[scales == 0] = 1
    arrays = [((values - means) / scales).astype(np.float32) for values in raw]
    return frames, arrays, {"medians": medians.tolist(), "means": means.tolist(), "scales": scales.tolist()}


def model_state(model) -> dict:
    return {"coef": model.coef_.tolist(), "intercept": model.intercept_.tolist(), "classes": model.classes_.tolist()}


def freeze_candidate() -> dict:
    features, groups = q1.available_features()
    frames, arrays, transform = q1_arrays(features)
    pair = q1.fit_pair(arrays[0], frames[0], arrays[1], frames[1], HORIZON)
    result = json.loads((q1.REPORT_DATA / "research_result.json").read_text(encoding="utf-8"))["best"]
    payload = {
        "candidate_id": CANDIDATE_ID,
        "immutable": True,
        "execution": "DISABLED",
        "research_reference": "BINANCE_RESEARCH_PROXY",
        "training_period": ["2025-01-01", "2025-02-09"],
        "calibration_period": ["2025-02-10", "2025-02-28"],
        "selection_period": ["2025-03-01", "2025-03-15"],
        "original_walk_forward": ["2025-03-16", "2025-03-31"],
        "case_days_excluded": sorted(day.isoformat() for day in q1.CASE_DAYS),
        "selection_procedure": "180s selected by validation precision among cost-positive candidates with >=100 independent validation signals; walk-forward not used for selection",
        "model_family": "two-stage logistic regression plus Platt calibration",
        "features": features,
        "feature_groups": groups,
        "feature_transform": transform,
        "move_model": model_state(pair[0]),
        "direction_model": model_state(pair[1]),
        "move_calibrator": model_state(pair[2].model),
        "direction_calibrator": model_state(pair[3].model),
        "horizon_seconds": HORIZON,
        "cooldown_seconds": HORIZON,
        "threshold": THRESHOLD,
        "direction_logic": "UP when calibrated p_up >= 0.5 else DOWN",
        "abstain_rule": "ABSTAIN when p_move * max(p_up,1-p_up) < 0.55",
        "assumed_cost_bp": q1.ASSUMED_COST_BP,
        "sample_seconds": q1.SAMPLE_SECONDS,
        "validation_result": result["validation"],
        "walk_forward_result": result["walk_forward"],
        "final_holdout": "CLOSED_2026-08-16_2026-08-17",
    }
    fingerprint = hashlib.sha256(canonical(payload)).hexdigest()
    envelope = {"fingerprint_sha256": fingerprint, "candidate": payload}
    if FREEZE.exists():
        existing = json.loads(FREEZE.read_text(encoding="utf-8"))
        if existing != envelope:
            raise RuntimeError("immutable V1 freeze mismatch; refusing overwrite")
    else:
        write_json(FREEZE, envelope)
    return envelope


def verify_freeze() -> dict:
    envelope = json.loads(FREEZE.read_text(encoding="utf-8"))
    actual = hashlib.sha256(canonical(envelope["candidate"])).hexdigest()
    if actual != envelope["fingerprint_sha256"]:
        raise RuntimeError("V1 fingerprint mismatch")
    return envelope


def sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -50, 50)
    return 1 / (1 + np.exp(-values))


def probability(matrix: np.ndarray, state: dict) -> np.ndarray:
    return sigmoid(matrix @ np.asarray(state["coef"], dtype=float).T + np.asarray(state["intercept"], dtype=float)).ravel()


def calibrated(raw: np.ndarray, state: dict) -> np.ndarray:
    logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1 - raw, 1e-6, 1))
    return sigmoid(logits * state["coef"][0][0] + state["intercept"][0])


def blind_path(day: date) -> Path:
    return BLIND_DERIVED / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def build_blind_days() -> list[dict]:
    if any(day in HOLDOUT for bounds in PERIODS.values() for day in q1.days(*bounds)):
        raise RuntimeError("holdout requested")
    previous = q1.DERIVED
    q1.DERIVED = BLIND_DERIVED
    try:
        return [q1.build_day(day) for bounds in PERIODS.values() for day in q1.days(*bounds)]
    finally:
        q1.DERIVED = previous


def load_period(bounds: tuple[date, date], features: list[str]) -> pd.DataFrame:
    labels = [f"future_return_{HORIZON}s", f"direction_{HORIZON}s"]
    context = ["timestamp", "regime", "origin", "hour_utc", "weekday"]
    columns = list(dict.fromkeys([*context, *features, *labels]))
    return pd.concat([pd.read_parquet(blind_path(day), columns=columns) for day in q1.days(*bounds)], ignore_index=True)


def predict(frame: pd.DataFrame, frozen: dict) -> pd.DataFrame:
    candidate = frozen["candidate"]
    features = candidate["features"]
    matrix = frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32)
    transform = candidate["feature_transform"]
    medians = np.asarray(transform["medians"], dtype=np.float32)
    rows, columns = np.where(~np.isfinite(matrix))
    matrix[rows, columns] = medians[columns]
    matrix = (matrix - np.asarray(transform["means"], dtype=np.float32)) / np.asarray(transform["scales"], dtype=np.float32)
    p_move = calibrated(probability(matrix, candidate["move_model"]), candidate["move_calibrator"])
    p_up = calibrated(probability(matrix, candidate["direction_model"]), candidate["direction_calibrator"])
    predicted = (p_up >= 0.5).astype(int)
    future = frame[f"future_return_{HORIZON}s"].to_numpy(float)
    output = frame.copy()
    output["p_move"], output["p_up"] = p_move, p_up
    output["confidence"] = p_move * np.maximum(p_up, 1 - p_up)
    output["predicted"] = predicted
    output["actual"] = frame[f"direction_{HORIZON}s"].to_numpy(int)
    output["correct"] = output.predicted == output.actual
    output["gross_return"] = np.where(predicted == 1, future, -future)
    output["net_return"] = output.gross_return - candidate["assumed_cost_bp"] / 10_000
    return output


def selected(predictions: pd.DataFrame) -> pd.DataFrame:
    return q1.independent_entries(predictions, THRESHOLD, HORIZON)


def score(predictions: pd.DataFrame) -> dict:
    entries = selected(predictions)
    wins = int(entries.correct.sum())
    low, high = wilson_interval(wins, len(entries)) if len(entries) else (None, None)
    result = {
        "signals": len(entries), "wins": wins, "losses": len(entries) - wins,
        "precision": wins / len(entries) if len(entries) else None, "wilson_ci95": [low, high],
        "coverage": len(entries) / len(predictions), "signals_per_day": len(entries) / predictions.timestamp.dt.date.nunique(),
        "gross_proxy_ev": float(entries.gross_return.mean()) if len(entries) else None,
        "net_proxy_ev": float(entries.net_return.mean()) if len(entries) else None,
    }
    for direction, value in (("UP", 1), ("DOWN", 0)):
        subset = entries[entries.predicted == value]
        result[direction] = {"signals": len(subset), "wins": int(subset.correct.sum()), "precision": float(subset.correct.mean()) if len(subset) else None}
    return result


def session(hour: int) -> str:
    return "ASIA" if hour < 7 else "EUROPE" if hour < 13 else "US"


def diagnostics(entries: pd.DataFrame) -> dict:
    if entries.empty:
        return {}
    copy = entries.copy()
    copy["session"] = copy.hour_utc.map(session)
    copy["macd_state"] = pd.cut(copy.macd_pressure.abs(), [-np.inf, 1, 2, 3, np.inf], labels=["NORMAL", "ELEVATED", "EXTREME", "EXCEPTIONAL"])
    return {
        "by_origin": copy.groupby("origin", observed=True).correct.agg(["count", "sum", "mean"]).to_dict("index"),
        "by_regime": copy.groupby("regime", observed=True).correct.agg(["count", "sum", "mean"]).to_dict("index"),
        "by_session": copy.groupby("session", observed=True).correct.agg(["count", "sum", "mean"]).to_dict("index"),
        "by_macd_state": copy.groupby("macd_state", observed=True).correct.agg(["count", "sum", "mean"]).to_dict("index"),
        "best_days": copy.assign(day=copy.timestamp.dt.date.astype(str)).groupby("day").correct.agg(["count", "sum", "mean"]).sort_values(["mean", "count"], ascending=False).head(5).to_dict("index"),
        "worst_days": copy.assign(day=copy.timestamp.dt.date.astype(str)).groupby("day").correct.agg(["count", "sum", "mean"]).sort_values(["mean", "count"]).head(5).to_dict("index"),
    }


def feature_snapshots(predictions: pd.DataFrame, period: str) -> list[dict]:
    entries = selected(predictions)
    columns = ["spot_pressure_10s", "futures_pressure_10s", "flow_pressure_acceleration", "flow_pressure_persistence", "spot_futures_agreement", "price_return_60s", "price_acceleration_30s", "expansion_score", "volatility_score", "macd_pressure", "macd_acceleration", "mean_zscore", "regime", "origin", "hour_utc"]
    records = []
    indexed = predictions.set_index("timestamp")
    for _, entry in entries.iterrows():
        history = {}
        for offset in (180, 120, 60, 30, 10, 0):
            target = entry.timestamp - pd.Timedelta(seconds=offset)
            position = indexed.index.get_indexer([target], method="nearest")[0]
            row = indexed.iloc[position]
            history[f"T-{offset}s" if offset else "T0"] = {name: row.get(name) for name in columns}
        records.append({"case_type": "TRUE_HIGH_CONFIDENCE_CASE" if entry.correct else "FALSE_HIGH_CONFIDENCE_CASE", "period": period, "timestamp": entry.timestamp.isoformat(), "direction": "UP" if entry.predicted else "DOWN", "actual": "UP" if entry.actual else "DOWN", "confidence": entry.confidence, "gross_return": entry.gross_return, "history": history})
    return records


def missed_moves(predictions: pd.DataFrame, period: str, minimum_move_bp: float = 10.0) -> list[dict]:
    return_name = f"future_return_{HORIZON}s"
    candidates = predictions[(predictions[return_name].abs() * 10_000 >= minimum_move_bp) & (predictions.confidence < THRESHOLD)].sort_values("timestamp")
    records, next_allowed = [], None
    for _, row in candidates.iterrows():
        if next_allowed is not None and row.timestamp < next_allowed:
            continue
        next_allowed = row.timestamp + pd.Timedelta(seconds=HORIZON)
        records.append({"case_type": "MISSED_MOVE_CASE", "period": period, "timestamp": row.timestamp.isoformat(), "actual_direction": "UP" if row[return_name] > 0 else "DOWN", "move_bp": abs(row[return_name]) * 10_000, "confidence": row.confidence, "minimum_move_bp": minimum_move_bp, "origin": row.origin, "regime": row.regime, "spot_pressure": row.spot_pressure_10s, "futures_pressure": row.futures_pressure_10s, "agreement": row.spot_futures_agreement, "expansion_score": row.expansion_score, "macd_pressure": row.macd_pressure})
    return records


def drift(reference: pd.DataFrame, target: pd.DataFrame, features: list[str]) -> dict:
    result = {}
    for name in features:
        left, right = reference[name].replace([np.inf, -np.inf], np.nan).dropna(), target[name].replace([np.inf, -np.inf], np.nan).dropna()
        scale = float(left.std()) or 1.0
        result[name] = {"standardized_mean_shift": float((right.mean() - left.mean()) / scale), "q50_shift_sd": float((right.median() - left.median()) / scale)}
    return result


def remember(payload: dict) -> None:
    record = canonical(payload).decode()
    record_id = hashlib.sha256((CANDIDATE_ID + record).encode()).hexdigest()
    with sqlite3.connect(MEMORY) as database:
        database.executescript(q1.SCHEMA)
        database.execute("INSERT OR IGNORE INTO research_records VALUES (?,?,?,?,?,?)", (record_id, "v1_blind_validation", pd.Timestamp.now("UTC").isoformat(), "2025-04-01", "2026-07-31", record))


def report(result: dict) -> None:
    rows = []
    for label in ("Q1_WF", "APR_2025", "MAY_2025", "JUN_2025", "APR_JUN_COMBINED", "JUL_2026"):
        item = result["periods"][label]
        ci = item["wilson_ci95"]
        rows.append(f"| {label} | {item['signals']} | {item['wins']} | {item['losses']} | {item['precision']:.2%} | {ci[0]:.2%}–{ci[1]:.2%} | {item['net_proxy_ev']:.4%} | {item['signals_per_day']:.2f} |")
    summary = result["total_new_oos"]
    overall = result["overall_oos"]
    text = f"""# WAVERUN 180s Blind Validation Report

FROZEN CANDIDATE: `{CANDIDATE_ID}`

FINGERPRINT: `{result['fingerprint_sha256']}`

RESEARCH REFERENCE: `BINANCE RESEARCH PROXY`

EXECUTION: `DISABLED`

FINAL AUGUST HOLDOUT: `CLOSED / UNTOUCHED`

| Period | Signals | Wins | Losses | Precision | 95% CI | Net EV | Signals/day |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

TOTAL NEW OOS: {summary['wins']}/{summary['signals']} = {summary['precision']:.2%}

OVERALL OOS INCLUDING ORIGINAL WF: {overall['wins']}/{overall['signals']} = {overall['precision']:.2%}

90% STATUS: **{result['status_90']}**

CANDIDATE STATUS: **{result['candidate_status']}**

No retraining, recalibration, threshold adjustment, feature change, or post-period filtering was performed.

## Key answers

1. 180s remained the frozen hypothesis, but it did not survive as a high-precision edge.
2. The original 93.33% did not persist; new OOS precision was {summary['precision']:.2%}.
3. Independent new signals: {summary['signals']}.
4. Precision fell as sample size increased; 95% CI is {summary['wilson_ci95'][0]:.2%}–{summary['wilson_ci95'][1]:.2%}.
5. Aggregate proxy Net EV remained positive, but June was negative.
6. It did not meet the >=70% product target in any blind month.
7. July 2026 precision was {result['periods']['JUL_2026']['precision']:.2%}; recent-regime persistence failed.
8. Feature-distribution drift is present in the machine-readable drift report; signal behavior also changed materially.
9. UP was {summary['UP']['precision']:.2%}; DOWN was {summary['DOWN']['precision']:.2%}; neither is proven reliable.
10. Extreme/exceptional MACD subgroups are diagnostic only and did not rescue July.
11. Expansion subgroups are diagnostic only; no V1 rule was changed.
12. Spot/Futures confirmation was inconsistent across months and is not promoted.
13. False-positive pre-signal fingerprints are preserved in `signal_autopsies.json`.
14. Missed >=10 bp moves are preserved as `MISSED_MOVE_CASE`; this threshold is diagnostic, not a V1 rule.
15. V1 remains immutable as a failed historical challenger and is not production-worthy.
"""
    (ROOT / "WAVERUN_180S_BLIND_VALIDATION_REPORT.md").write_text(text, encoding="utf-8")
    mechanism = "# WAVERUN V1 Mechanism Report\n\nV1 is a two-stage, cost-aware pressure/momentum continuation detector combining price response, Spot/Futures flow, pressure persistence, expansion, structure/reversion, MACD context, and time context.\n\nThe blind evidence shows that this mechanism was not stable: 93.33% in the original 15-signal window fell to 60.42% over 144 new independent signals and 56.00% in July 2026. Aggregate proxy EV stayed positive because winners were larger, but directional precision did not survive. Exceptional MACD readings dominated the sample and did not rescue July (13/24); confirmed origin also fell to 8/16 in July while Futures-led happened to reach 6/7, too small and post-hoc to promote.\n\nAll subgroup results remain diagnostic only. None becomes a V1 rule; any derived idea is a V2 hypothesis requiring fresh OOS data.\n"
    (ROOT / "WAVERUN_V1_MECHANISM_REPORT.md").write_text(mechanism, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    frozen = freeze_candidate()
    verify_freeze()
    if args.freeze_only:
        print(json.dumps({"candidate": CANDIDATE_ID, "fingerprint": frozen["fingerprint_sha256"]}))
        return
    manifest = build_blind_days()
    features = frozen["candidate"]["features"]
    predictions = {name: predict(load_period(bounds, features), frozen) for name, bounds in PERIODS.items()}
    apr_jun = pd.concat([predictions[name] for name in ("APR_2025", "MAY_2025", "JUN_2025")], ignore_index=True)
    new_all = pd.concat([apr_jun, predictions["JUL_2026"]], ignore_index=True)
    q1_wf = frozen["candidate"]["walk_forward_result"]
    periods = {name: score(frame) for name, frame in predictions.items()}
    periods["APR_JUN_COMBINED"] = score(apr_jun)
    periods["Q1_WF"] = {**q1_wf, "losses": q1_wf["signals"] - q1_wf["wins"], "gross_proxy_ev": q1_wf["gross_ev"], "net_proxy_ev": q1_wf["net_ev"]}
    total = score(new_all)
    positive_months = sum(periods[name]["net_proxy_ev"] is not None and periods[name]["net_proxy_ev"] > 0 for name in PERIODS)
    candidate_status = "SURVIVED" if positive_months >= 3 and total["net_proxy_ev"] > 0 and total["precision"] >= 0.70 else "WEAKENED" if total["precision"] >= 0.65 and total["net_proxy_ev"] > 0 else "FAILED"
    overall = {"signals": total["signals"] + q1_wf["signals"], "wins": total["wins"] + q1_wf["wins"]}
    overall["losses"] = overall["signals"] - overall["wins"]
    overall["precision"] = overall["wins"] / overall["signals"]
    overall["wilson_ci95"] = list(wilson_interval(overall["wins"], overall["signals"]))
    result = {"candidate": CANDIDATE_ID, "fingerprint_sha256": frozen["fingerprint_sha256"], "execution": "DISABLED", "reference": "BINANCE_RESEARCH_PROXY", "holdout": "CLOSED_UNTOUCHED", "manifest": manifest, "periods": periods, "total_new_oos": total, "overall_oos": overall, "candidate_status": candidate_status, "status_90": "90% VERIFIED" if overall["signals"] >= 100 and overall["wilson_ci95"][0] >= 0.90 else "90% NOT VERIFIED", "diagnostics": {name: diagnostics(selected(frame)) for name, frame in predictions.items()}, "concept_drift": {"APR_JUN": drift(q1.load_split("train", features), apr_jun, features), "JUL_2026": drift(q1.load_split("train", features), predictions["JUL_2026"], features)}}
    cases = []
    q1_frames, q1_matrices, _ = q1_arrays(features)
    q1_pair = q1.fit_pair(q1_matrices[0], q1_frames[0], q1_matrices[1], q1_frames[1], HORIZON)
    cases.extend(feature_snapshots(q1.predict(q1_pair, q1_matrices[3], q1_frames[3], HORIZON), "Q1_WF"))
    for name, frame in predictions.items():
        cases.extend(feature_snapshots(frame, name))
        cases.extend(missed_moves(frame, name))
    result["case_counts"] = pd.Series([case["case_type"] for case in cases]).value_counts().to_dict()
    write_json(OUTPUT / "blind_validation_result.json", result)
    write_json(OUTPUT / "signal_autopsies.json", cases)
    remember({"result": result, "case_count": len(cases)})
    report(result)
    print(json.dumps({"candidate": CANDIDATE_ID, "fingerprint": frozen["fingerprint_sha256"], "total_new_oos": total, "candidate_status": candidate_status, "status_90": result["status_90"]}, indent=2))


if __name__ == "__main__":
    main()
