from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.pressure import macd_features, robust_score
from bitcoin_cycle_analyzer.short_term.research_protocol import (
    assert_days_allowed,
    wilson_interval,
)

START = date(2025, 1, 1)
END = date(2025, 3, 31)
CASE_DAYS = frozenset({date(2025, 1, 17), date(2025, 2, 2), date(2025, 2, 17)})
HORIZONS = (10, 30, 60, 90, 180, 300)
SAMPLE_SECONDS = 5
ASSUMED_COST_BP = 3.0
RAW = ROOT / "runtime" / "waverun_data" / "raw"
DERIVED = ROOT / "runtime" / "waverun_data" / "derived" / "q1_2025"
REPORT_DATA = ROOT / "data" / "reports" / "waverun_q1_2025"
MEMORY = ROOT / "runtime" / "waverun_research_memory.sqlite"

SPLITS = {
    "train": (date(2025, 1, 1), date(2025, 2, 9)),
    "calibration": (date(2025, 2, 10), date(2025, 2, 28)),
    "validation": (date(2025, 3, 1), date(2025, 3, 15)),
    "walk_forward": (date(2025, 3, 16), date(2025, 3, 31)),
}


def days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def raw_path(source: str, day: date) -> Path:
    return RAW / source / "BTCUSDT" / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def derived_path(day: date) -> Path:
    return DERIVED / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def _flow(day: date, source: str) -> tuple[pd.DataFrame, dict]:
    path = raw_path(source, day)
    frame = pd.read_parquet(path, columns=["exchange_timestamp", "price", "quantity", "buyer_is_maker"])
    timestamp = pd.to_datetime(frame.exchange_timestamp, utc=True)
    deltas = timestamp.diff().dt.total_seconds()
    quality = {
        "source": source,
        "day": day.isoformat(),
        "events": len(frame),
        "first_timestamp": timestamp.min().isoformat(),
        "last_timestamp": timestamp.max().isoformat(),
        "gaps_over_60s": int((deltas > 60).sum()),
        "backwards_timestamps": int((deltas < 0).sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
        "timestamp_anomalies": int(timestamp.isna().sum()),
    }
    quality["quality"] = "GOOD" if not any(quality[key] for key in ("gaps_over_60s", "backwards_timestamps", "timestamp_anomalies")) else "FLAGGED"
    frame["second"] = timestamp.dt.floor("s")
    frame["buy_volume"] = frame.quantity.where(~frame.buyer_is_maker, 0.0)
    frame["sell_volume"] = frame.quantity.where(frame.buyer_is_maker, 0.0)
    grouped = frame.groupby("second", sort=True).agg(
        price=("price", "last"),
        volume=("quantity", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        trades=("price", "size"),
    )
    grouped["delta"] = grouped.buy_volume - grouped.sell_volume
    return grouped, quality


def _align(index: pd.DatetimeIndex, flow: pd.DataFrame, prefix: str) -> pd.DataFrame:
    aligned = flow.reindex(index)
    aligned.price = aligned.price.ffill().bfill()
    for column in ("volume", "buy_volume", "sell_volume", "trades", "delta"):
        aligned[column] = aligned[column].fillna(0.0)
    aligned["imbalance"] = aligned.delta / aligned.volume.replace(0, np.nan)
    aligned["cvd_30s"] = aligned.delta.rolling(30, min_periods=10).sum()
    aligned["cvd_velocity"] = aligned.cvd_30s.diff(10)
    aligned["cvd_acceleration"] = aligned.cvd_velocity.diff(10)
    aligned["trade_intensity_30s"] = aligned.trades.rolling(30, min_periods=10).mean()
    aligned["trade_intensity_acceleration"] = aligned.trade_intensity_30s.diff(10)
    aligned["pressure_10s"] = aligned.delta.rolling(10, min_periods=3).sum() / aligned.volume.rolling(10, min_periods=3).sum().replace(0, np.nan)
    aligned["pressure_30s"] = aligned.delta.rolling(30, min_periods=10).sum() / aligned.volume.rolling(30, min_periods=10).sum().replace(0, np.nan)
    aligned["pressure_persistence"] = np.sign(aligned.pressure_10s).rolling(30, min_periods=10).mean()
    aligned["pressure_acceleration"] = aligned.pressure_10s.diff(10) - aligned.pressure_10s.diff(10).shift(10)
    return aligned.add_prefix(f"{prefix}_")


def build_day(day: date) -> dict:
    output = derived_path(day)
    quality_output = output.with_suffix(".quality.json")
    if output.exists() and quality_output.exists():
        return {"day": day.isoformat(), "status": "CHECKPOINT", "rows": len(pd.read_parquet(output, columns=["timestamp"]))}
    spot, spot_quality = _flow(day, "binance_spot")
    futures, futures_quality = _flow(day, "binance_futures")
    index = pd.date_range(pd.Timestamp(day, tz="UTC"), pd.Timestamp(day + timedelta(days=1), tz="UTC"), freq="1s", inclusive="left")
    spot = _align(index, spot, "spot")
    futures = _align(index, futures, "futures")
    frame = spot.join(futures)
    frame["mid"] = (frame.spot_price + frame.futures_price) / 2
    for seconds in (1, 5, 10, 30, 60, 180, 300):
        frame[f"price_return_{seconds}s"] = frame.mid.pct_change(seconds)
        frame[f"price_acceleration_{seconds}s"] = frame[f"price_return_{seconds}s"].diff(seconds)
    frame["price_pressure"] = robust_score(frame.price_return_10s, 300)
    frame["price_response_efficiency"] = frame.price_return_10s / ((frame.spot_pressure_10s + frame.futures_pressure_10s) / 2).replace(0, np.nan)
    frame["spot_futures_agreement"] = np.sign(frame.spot_pressure_10s) * np.sign(frame.futures_pressure_10s)
    frame["flow_pressure"] = (frame.spot_pressure_10s + frame.futures_pressure_10s) / 2
    frame["flow_pressure_acceleration"] = (frame.spot_pressure_acceleration + frame.futures_pressure_acceleration) / 2
    frame["flow_price_absorption"] = robust_score(frame.flow_pressure.abs(), 300).clip(0, 100) - robust_score(frame.price_return_10s.abs(), 300).clip(0, 100)
    frame["spot_lead_1s"] = frame.spot_price.pct_change().shift(1) - frame.futures_price.pct_change()
    frame["futures_lead_1s"] = frame.futures_price.pct_change().shift(1) - frame.spot_price.pct_change()
    for seconds in (10, 30, 60, 180, 300, 900):
        close = frame.mid.resample(f"{seconds}s", label="right", closed="left").last().dropna()
        macd = macd_features(close).add_prefix(f"macd_{seconds}s_")
        frame = frame.join(macd.reindex(frame.index).ffill())
    frame["macd_pressure"] = np.mean([robust_score(frame[f"macd_{seconds}s_histogram"], 300) for seconds in (10, 30, 60)], axis=0)
    frame["macd_acceleration"] = np.mean([frame[f"macd_{seconds}s_histogram_acceleration"] for seconds in (10, 30, 60)], axis=0)
    frame["macd_alignment"] = sum(np.sign(frame[f"macd_{seconds}s_histogram"]) for seconds in (10, 30, 60, 180, 300, 900))
    frame["volatility_60s"] = frame.mid.pct_change().rolling(60, min_periods=20).std()
    frame["volatility_score"] = robust_score(frame.volatility_60s, 900)
    frame["range_60s"] = frame.mid.rolling(60, min_periods=20).max() / frame.mid.rolling(60, min_periods=20).min() - 1
    frame["expansion_score"] = robust_score(frame.range_60s, 900)
    frame["mean_zscore"] = (frame.mid - frame.mid.rolling(300, min_periods=60).mean()) / frame.mid.rolling(300, min_periods=60).std().replace(0, np.nan)
    frame["exhaustion"] = -np.sign(frame.price_return_60s) * frame.flow_pressure_acceleration + frame.flow_price_absorption
    frame["structure_break"] = np.select([frame.mid > frame.mid.rolling(60, min_periods=20).max().shift(1), frame.mid < frame.mid.rolling(60, min_periods=20).min().shift(1)], [1, -1], default=0)
    frame["regime"] = np.select(
        [frame.expansion_score > 70, frame.expansion_score < -40, frame.price_return_300s > frame.volatility_60s * 5, frame.price_return_300s < -frame.volatility_60s * 5],
        ["EXPANSION", "COMPRESSION", "TREND_UP", "TREND_DOWN"],
        default="RANGE",
    )
    frame["origin"] = np.select(
        [
            (frame.spot_pressure_10s.abs() > frame.futures_pressure_10s.abs() * 1.5),
            (frame.futures_pressure_10s.abs() > frame.spot_pressure_10s.abs() * 1.5),
            frame.spot_futures_agreement > 0,
            frame.spot_futures_agreement < 0,
        ],
        ["SPOT_LED", "FUTURES_LED", "CONFIRMED", "DIVERGENT"],
        default="UNKNOWN",
    )
    labels = {}
    for horizon in HORIZONS:
        future = frame.mid.shift(-horizon) / frame.mid - 1
        labels[f"future_return_{horizon}s"] = future
        labels[f"direction_{horizon}s"] = (future > 0).astype("int8")
        labels[f"move_{horizon}s"] = (future.abs() * 10_000 > ASSUMED_COST_BP).astype("int8")
    frame = pd.concat([frame, pd.DataFrame(labels, index=frame.index)], axis=1)
    frame["hour_utc"] = frame.index.hour
    frame["weekday"] = frame.index.dayofweek
    frame["month"] = frame.index.month
    frame["case_anchor_day"] = day in CASE_DAYS
    frame = frame.iloc[::SAMPLE_SECONDS].copy()
    frame.insert(0, "timestamp", frame.index)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, compression="zstd", index=False)
    quality_output.write_text(json.dumps({"day": day.isoformat(), "spot": spot_quality, "futures": futures_quality, "vantage": {"status": "UNAVAILABLE", "reason": "MT5_IPC_TIMEOUT"}}, indent=2), encoding="utf-8")
    return {"day": day.isoformat(), "status": "BUILT", "rows": len(frame)}


FEATURE_GROUPS = {
    "price_response": ("price_return_", "price_acceleration_", "price_pressure", "price_response_efficiency"),
    "spot_flow": ("spot_imbalance", "spot_cvd_", "spot_trade_", "spot_pressure_"),
    "futures_flow": ("futures_imbalance", "futures_cvd_", "futures_trade_", "futures_pressure_"),
    "pressure": ("flow_pressure", "spot_futures_agreement", "spot_lead_", "futures_lead_"),
    "macd": ("macd_",),
    "expansion": ("volatility_", "range_", "expansion_"),
    "structure_reversion": ("mean_zscore", "exhaustion", "structure_break", "flow_price_absorption"),
    "time": ("hour_utc", "weekday"),
}


def split_days(name: str) -> list[date]:
    start, end = SPLITS[name]
    return [day for day in days(start, end) if day not in CASE_DAYS]


def available_features() -> tuple[list[str], dict[str, list[str]]]:
    names = pd.read_parquet(derived_path(split_days("train")[0])).columns.tolist()
    groups = {group: sorted({name for name in names if any(name.startswith(prefix) for prefix in prefixes)}) for group, prefixes in FEATURE_GROUPS.items()}
    blocked = ("future_return_", "direction_", "move_")
    groups = {group: [name for name in columns if not name.startswith(blocked)] for group, columns in groups.items()}
    return sorted(set().union(*groups.values())), groups


def load_split(name: str, features: list[str]) -> pd.DataFrame:
    labels = [item for horizon in HORIZONS for item in (f"future_return_{horizon}s", f"direction_{horizon}s", f"move_{horizon}s")]
    context = ["timestamp", "regime", "origin", "month", "hour_utc", "weekday", "case_anchor_day"]
    columns = list(dict.fromkeys([*context, *features, *labels]))
    return pd.concat([pd.read_parquet(derived_path(day), columns=columns) for day in split_days(name)], ignore_index=True)


def matrices(frames: list[pd.DataFrame], features: list[str]) -> list[np.ndarray]:
    arrays = [frame[features].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32) for frame in frames]
    medians = np.nanmedian(arrays[0], axis=0)
    medians[~np.isfinite(medians)] = 0
    for values in arrays:
        bad_rows, bad_columns = np.where(~np.isfinite(values))
        values[bad_rows, bad_columns] = medians[bad_columns]
    means, scales = arrays[0].mean(axis=0), arrays[0].std(axis=0)
    scales[scales == 0] = 1
    return [((values - means) / scales).astype(np.float32) for values in arrays]


class Calibrator:
    def fit(self, probability: np.ndarray, target: np.ndarray) -> Calibrator:
        from sklearn.linear_model import LogisticRegression

        clipped = np.clip(probability, 1e-6, 1 - 1e-6)
        self.model = LogisticRegression(max_iter=100).fit(np.log(clipped / (1 - clipped)).reshape(-1, 1), target)
        return self

    def predict(self, probability: np.ndarray) -> np.ndarray:
        clipped = np.clip(probability, 1e-6, 1 - 1e-6)
        return self.model.predict_proba(np.log(clipped / (1 - clipped)).reshape(-1, 1))[:, 1]


def fit_pair(train_x: np.ndarray, train: pd.DataFrame, cal_x: np.ndarray, calibration: pd.DataFrame, horizon: int):
    from sklearn.linear_model import LogisticRegression

    move_train = train[f"move_{horizon}s"].to_numpy(dtype=int)
    direction_train = train[f"direction_{horizon}s"].to_numpy(dtype=int)
    move_cal = calibration[f"move_{horizon}s"].to_numpy(dtype=int)
    direction_cal = calibration[f"direction_{horizon}s"].to_numpy(dtype=int)
    move_model = LogisticRegression(max_iter=150, class_weight="balanced", C=0.25).fit(train_x, move_train)
    directional = move_train == 1
    direction_model = LogisticRegression(max_iter=150, class_weight="balanced", C=0.25).fit(train_x[directional], direction_train[directional])
    move_calibrator = Calibrator().fit(move_model.predict_proba(cal_x)[:, 1], move_cal)
    direction_calibrator = Calibrator().fit(direction_model.predict_proba(cal_x)[:, 1], direction_cal)
    return move_model, direction_model, move_calibrator, direction_calibrator


def predict(pair, matrix: np.ndarray, frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    move_model, direction_model, move_calibrator, direction_calibrator = pair
    p_move = move_calibrator.predict(move_model.predict_proba(matrix)[:, 1])
    p_up = direction_calibrator.predict(direction_model.predict_proba(matrix)[:, 1])
    predicted = np.where(p_up >= 0.5, 1, 0)
    confidence = p_move * np.maximum(p_up, 1 - p_up)
    actual = frame[f"direction_{horizon}s"].to_numpy(dtype=int)
    future = frame[f"future_return_{horizon}s"].to_numpy(dtype=float)
    signed = np.where(predicted == 1, future, -future)
    return pd.DataFrame({"timestamp": frame.timestamp, "regime": frame.regime, "origin": frame.origin, "month": frame.month, "hour_utc": frame.hour_utc, "weekday": frame.weekday, "p_move": p_move, "p_up": p_up, "confidence": confidence, "predicted": predicted, "actual": actual, "correct": predicted == actual, "gross_return": signed, "net_return": signed - ASSUMED_COST_BP / 10_000})


def independent_entries(predictions: pd.DataFrame, threshold: float, horizon: int) -> pd.DataFrame:
    candidates = predictions[predictions.confidence >= threshold].sort_values("timestamp")
    accepted = []
    next_allowed = None
    for position, timestamp in zip(candidates.index, candidates.timestamp, strict=True):
        if next_allowed is None or timestamp >= next_allowed:
            accepted.append(position)
            next_allowed = timestamp + pd.Timedelta(seconds=horizon)
    return candidates.loc[accepted]


def metrics(predictions: pd.DataFrame, threshold: float, horizon: int) -> dict:
    selected = independent_entries(predictions, threshold, horizon)
    count = len(selected)
    wins = int(selected.correct.sum())
    low, high = wilson_interval(wins, count) if count else (None, None)
    period_days = max(1, (predictions.timestamp.max() - predictions.timestamp.min()).days + 1)
    return {
        "threshold": threshold,
        "signals": count,
        "wins": wins,
        "precision": wins / count if count else None,
        "wilson_ci95": [low, high],
        "coverage": count / len(predictions) if len(predictions) else 0,
        "cooldown_seconds": horizon,
        "signals_per_day": count / period_days,
        "gross_ev": float(selected.gross_return.mean()) if count else None,
        "net_ev": float(selected.net_return.mean()) if count else None,
    }


def research() -> dict:
    all_features, groups = available_features()
    train, calibration, validation, walk = [load_split(name, all_features) for name in SPLITS]
    train_x, cal_x, val_x, walk_x = matrices([train, calibration, validation, walk], all_features)
    experiments = []
    candidates = []
    for horizon in HORIZONS:
        pair = fit_pair(train_x, train, cal_x, calibration, horizon)
        val_predictions = predict(pair, val_x, validation, horizon)
        curves = [metrics(val_predictions, threshold, horizon) for threshold in np.arange(0.50, 0.951, 0.025)]
        eligible = [row for row in curves if row["signals"] >= 100 and row["net_ev"] is not None and row["net_ev"] > 0]
        best = max(eligible, key=lambda row: (row["precision"], row["net_ev"]), default=None)
        experiments.append({"experiment": f"Q1_TWO_STAGE_{horizon}s", "horizon": horizon, "validation_curve": curves, "best": best})
        if best:
            candidates.append({"horizon": horizon, "threshold": best["threshold"], "validation": best, "pair": pair})
    best_candidate = max(
        candidates,
        key=lambda row: (row["validation"]["precision"], row["validation"]["net_ev"], row["validation"]["signals"]),
        default=None,
    )
    if best_candidate:
        horizon = best_candidate["horizon"]
        walk_predictions = predict(best_candidate["pair"], walk_x, walk, horizon)
        best_candidate["walk_forward"] = metrics(walk_predictions, best_candidate["threshold"], horizon)
        best_candidate["folds"] = [
            {"day": day_value.isoformat(), **metrics(fold, best_candidate["threshold"], horizon)}
            for day_value, fold in walk_predictions.groupby(walk_predictions.timestamp.dt.date)
        ]
    ablations = []
    if best_candidate:
        horizon = best_candidate["horizon"]
        for excluded in (None, *groups):
            included = [group for group in groups if group != excluded]
            features = sorted({column for group in included for column in groups[group]})
            subset_arrays = matrices([train, calibration, validation, walk], features)
            pair = fit_pair(subset_arrays[0], train, subset_arrays[1], calibration, horizon)
            val_prediction = predict(pair, subset_arrays[2], validation, horizon)
            walk_prediction = predict(pair, subset_arrays[3], walk, horizon)
            threshold = best_candidate["threshold"]
            ablations.append({"label": "FULL" if excluded is None else f"WITHOUT_{excluded.upper()}", "validation": metrics(val_prediction, threshold, horizon), "walk_forward": metrics(walk_prediction, threshold, horizon)})
    return {"execution": "DISABLED", "status": "RESEARCH_ONLY", "period": [START.isoformat(), END.isoformat()], "case_days_excluded_from_model_proof": sorted(day.isoformat() for day in CASE_DAYS), "assumed_exchange_cost_bp": ASSUMED_COST_BP, "vantage_execution_status": "NOT_AVAILABLE_MT5_IPC_TIMEOUT", "feature_groups": groups, "experiments": experiments, "best": None if best_candidate is None else {key: value for key, value in best_candidate.items() if key not in {"pair", "walk_predictions"}}, "ablations": ablations}


SCHEMA = """
CREATE TABLE IF NOT EXISTS research_records (
    record_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def remember(category: str, payload: dict) -> None:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    record_id = hashlib.sha256(f"Q1_2025:{category}:{canonical}".encode()).hexdigest()
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(MEMORY) as database:
        database.executescript(SCHEMA)
        database.execute("INSERT OR IGNORE INTO research_records VALUES (?,?,?,?,?,?)", (record_id, category, datetime.now(UTC).isoformat(), START.isoformat(), END.isoformat(), canonical))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(payload, output, indent=2, default=str)
        output.write("\n")


def write_reports(result: dict, quality: list[dict]) -> None:
    REPORT_DATA.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_DATA / "research_result.json", result)
    write_json(REPORT_DATA / "data_quality.json", quality)
    best = result.get("best")
    best_metrics = None if best is None else best["walk_forward"]
    verified = bool(
        best_metrics
        and best_metrics["signals"] >= 100
        and best_metrics["wilson_ci95"][0] is not None
        and best_metrics["wilson_ci95"][0] >= 0.90
    )
    precision_text = f"{best_metrics['precision']:.2%}" if verified else "NOT FOUND"
    observed_text = "NOT AVAILABLE" if best_metrics is None else f"{best_metrics['precision']:.2%}"
    signals_per_day = 0.0 if best_metrics is None else best_metrics["signals_per_day"]
    horizon_text = "NOT AVAILABLE" if best is None else f"{best['horizon']}s"
    headline = [
        f"BEST VERIFIED PRECISION = {precision_text}",
        f"BEST OBSERVED WALK-FORWARD PRECISION = {observed_text} (PROVISIONAL)",
        f"SIGNALS = {0 if best_metrics is None else best_metrics['signals']}",
        f"SIGNALS/DAY = {signals_per_day:.2f}",
        f"BEST HORIZON = {horizon_text}",
        "BEST EARLY-WARNING LEAD = NOT ESTABLISHED",
        "BEST UTC WINDOW = DIAGNOSTIC ONLY",
        "BEST BERLIN WINDOW = DIAGNOSTIC ONLY",
        "BEST REGIME = NOT ESTABLISHED" if best is None else "BEST REGIME = SEE MACHINE-READABLE RESULTS",
        "BEST UP-TREND INDICATORS = NOT ESTABLISHED",
        "BEST DOWN-TREND INDICATORS = NOT ESTABLISHED",
        "BEST FAKE-TREND FILTER = NOT ESTABLISHED",
        "MACD HYPOTHESIS = NOT PROVEN" if best is None else "MACD HYPOTHESIS = SEE ABLATION",
        "MEAN REVERSION = NOT PROVEN",
        "90% STATUS = VERIFIED" if verified else "90% STATUS = 90% NOT FOUND",
        "PROMOTION STATUS = PROVEN EDGE" if verified else "PROMOTION STATUS = NO PROVEN EDGE YET",
    ]
    master = "# WAVERUN 3-Month Master Findings\n\n" + "\n\n".join(headline) + "\n\n## Data scope\n\nBinance Spot/Futures AggTrades: 90/90 days each. Vantage: NOT AVAILABLE (MT5 IPC timeout). Historical L2: NOT AVAILABLE. The three known screenshot days were excluded from fitting and proof.\n\nExecution remains `DISABLED`.\n"
    (ROOT / "WAVERUN_3_MONTH_MASTER_FINDINGS.md").write_text(master, encoding="utf-8")
    reports = {
        "WAVERUN_3_MONTH_PRECISION_LADDER.md": "# WAVERUN 3-Month Precision Ladder\n\nMachine-readable threshold curves, Wilson intervals, coverage, signals/day, gross EV and assumed-cost net EV are stored in `data/reports/waverun_q1_2025/research_result.json`.\n",
        "WAVERUN_3_MONTH_TREND_REPORT.md": "# WAVERUN 3-Month Trend Report\n\nTrend/fake-trend mechanisms remain research-only. No Vantage-executable trend claim is made.\n",
        "WAVERUN_3_MONTH_MACD_REPORT.md": "# WAVERUN 3-Month MACD Report\n\nStandard and normalized multi-scale MACD features were evaluated only through chronological model/ablation results. MACD is not promoted without positive walk-forward incremental value.\n",
        "WAVERUN_3_MONTH_MEAN_REVERSION_REPORT.md": "# WAVERUN 3-Month Mean Reversion Report\n\nNaive overbought/oversold logic is not promoted. Confirmed exhaustion/absorption remains a bounded research hypothesis.\n",
        "WAVERUN_3_MONTH_TIME_REPORT.md": "# WAVERUN 3-Month Time Report\n\nTime/session findings are diagnostic only until adequate OOS subgroup samples exist.\n",
        "WAVERUN_3_MONTH_FAILURE_AUTOPSY.md": "# WAVERUN 3-Month Failure Autopsy\n\nFalse positives, cost-killed signals and missed moves are persisted in the canonical SQLite research memory when identified.\n",
        "WAVERUN_3_MONTH_RESEARCH_QUEUE.md": "# WAVERUN 3-Month Research Queue\n\n1. Pressure-building versus already-mature expansion.\n2. Spot-led versus Futures-led causal lead/lag.\n3. MACD acceleration conditional on independent flow confirmation.\n4. Flow-price absorption as fake-trend blocker.\n5. Failed pullback and reacceleration.\n6. Continuation versus confirmed reversion.\n7. Reaction-delay robustness.\n8. Exchange proxy versus real Vantage execution once MT5 works.\n9. March-only stability.\n10. Bull/bear directional asymmetry.\n11. Volatility-regime transfer.\n12. Weekend versus weekday.\n13. Origin confidence.\n14. Pressure persistence thresholds.\n15. Early-expansion state transitions.\n16. Missed-move detector.\n17. High-confidence failure clustering.\n18. Cost-stress ladder.\n19. Calibration drift.\n20. Independent new-data shadow validation.\n",
    }
    for name, content in reports.items():
        (ROOT / name).write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    assert_days_allowed(days(START, END))
    DERIVED.mkdir(parents=True, exist_ok=True)
    build_manifest = []
    started = perf_counter()
    for day in days(START, END):
        row = build_day(day)
        build_manifest.append(row)
        print(json.dumps(row), flush=True)
    quality = [json.loads(derived_path(day).with_suffix(".quality.json").read_text(encoding="utf-8")) for day in days(START, END)]
    (DERIVED / "build_manifest.json").write_text(json.dumps({"period": [START.isoformat(), END.isoformat()], "sample_seconds": SAMPLE_SECONDS, "days": build_manifest, "execution": "DISABLED"}, indent=2), encoding="utf-8")
    remember("data_quality", {"days": quality})
    if args.build_only:
        return
    result = research()
    remember("model_results", result)
    remember("ablation_results", {"ablations": result["ablations"]})
    remember("precision_results", {"experiments": result["experiments"], "best": result["best"]})
    remember("negative_findings", {"vantage": "MT5_IPC_TIMEOUT", "historical_l2": "NOT_AVAILABLE", "case_days_not_proof": True})
    write_reports(result, quality)
    print(json.dumps({"status": result["status"], "best": result["best"], "runtime_seconds": perf_counter() - started, "memory": str(MEMORY)}, default=str), flush=True)


if __name__ == "__main__":
    main()
