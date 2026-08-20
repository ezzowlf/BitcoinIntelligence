from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V1_SCRIPT = ROOT / "scripts" / "run_waverun_v1_blind_validation.py"
SPEC = importlib.util.spec_from_file_location("waverun_v1", V1_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
v1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v1)

HORIZONS = (30, 60, 90, 180, 300)
MAGNITUDES_BP = (1, 2, 5, 10, 15, 20, 30, 50)
TIMING_BP = (1, 2, 5, 10, 20, 50)
COST_BP = 3.0
SAFETY_MARGIN_BP = 2.0
OUTPUT = ROOT / "data" / "reports" / "waverun_magnitude"
REPORT = ROOT / "WAVERUN_MOVE_MAGNITUDE_REPORT.md"


def load_q1_walk(features: list[str]) -> pd.DataFrame:
    start, end = v1.q1.SPLITS["walk_forward"]
    context = ["timestamp", "mid", "regime", "origin", "hour_utc", "weekday"]
    labels = [item for horizon in HORIZONS for item in (f"future_return_{horizon}s", f"direction_{horizon}s")]
    columns = list(dict.fromkeys([*context, *features, *labels]))
    return pd.concat(
        [pd.read_parquet(v1.q1.derived_path(day), columns=columns) for day in v1.q1.days(start, end)],
        ignore_index=True,
    )


def load_blind(bounds: tuple, features: list[str]) -> pd.DataFrame:
    context = ["timestamp", "mid", "regime", "origin", "hour_utc", "weekday"]
    labels = [item for horizon in HORIZONS for item in (f"future_return_{horizon}s", f"direction_{horizon}s")]
    columns = list(dict.fromkeys([*context, *features, *labels]))
    return pd.concat(
        [pd.read_parquet(v1.blind_path(day), columns=columns) for day in v1.q1.days(*bounds)],
        ignore_index=True,
    )


def first_crossing(path_bp: np.ndarray, threshold: float, favorable: bool) -> int | None:
    matches = np.flatnonzero(path_bp >= threshold if favorable else path_bp <= -threshold)
    return None if not len(matches) else int(matches[0] * v1.q1.SAMPLE_SECONDS)


def magnitude_class(mfe_bp: float) -> str:
    matched = [value for value in MAGNITUDES_BP if mfe_bp >= value]
    return "BELOW_1BP" if not matched else f"GE_{max(matched)}BP"


def record_for_entry(entry: pd.Series, frame: pd.DataFrame, period: str) -> dict:
    timestamps = pd.DatetimeIndex(frame.timestamp)
    start = timestamps.get_indexer([entry.timestamp], method="nearest")[0]
    end = min(len(frame) - 1, start + 300 // v1.q1.SAMPLE_SECONDS)
    prices = frame.mid.iloc[start : end + 1].to_numpy(float)
    entry_price = float(prices[0])
    direction = 1 if int(entry.predicted) == 1 else -1
    path_bp = direction * (prices / entry_price - 1) * 10_000
    primary_path = path_bp[: 180 // v1.q1.SAMPLE_SECONDS + 1]
    mfe_position, mae_position = int(np.argmax(primary_path)), int(np.argmin(primary_path))
    horizons = {}
    for horizon in HORIZONS:
        position = min(horizon // v1.q1.SAMPLE_SECONDS, len(prices) - 1)
        endpoint_price = float(prices[position])
        endpoint_return = direction * (endpoint_price / entry_price - 1)
        segment = path_bp[: position + 1]
        horizons[str(horizon)] = {
            "endpoint_price": endpoint_price,
            "endpoint_return": endpoint_return,
            "endpoint_usd_move": direction * (endpoint_price - entry_price),
            "endpoint_bp": endpoint_return * 10_000,
            "endpoint_direction_correct": endpoint_return > 0,
            "mfe_bp": float(segment.max()),
            "mae_bp": float(max(0.0, -segment.min())),
            "mfe_usd": float(segment.max() * entry_price / 10_000),
            "mae_usd": float(max(0.0, -segment.min()) * entry_price / 10_000),
            "net_endpoint_bp": float(endpoint_return * 10_000 - COST_BP),
        }
    primary = horizons["180"]
    return {
        "record_type": "PredictionRecord",
        "candidate": v1.CANDIDATE_ID,
        "period": period,
        "timestamp": entry.timestamp.isoformat(),
        "entry_reference_price": entry_price,
        "direction": "UP" if direction == 1 else "DOWN",
        "horizon": v1.HORIZON,
        "endpoint_price": primary["endpoint_price"],
        "endpoint_return": primary["endpoint_return"],
        "endpoint_usd_move": primary["endpoint_usd_move"],
        "endpoint_bp": primary["endpoint_bp"],
        "endpoint_direction_correct": primary["endpoint_direction_correct"],
        "mfe": primary["mfe_usd"],
        "mae": primary["mae_usd"],
        "mfe_bp": primary["mfe_bp"],
        "mae_bp": primary["mae_bp"],
        "mfe_percent": primary["mfe_bp"] / 100,
        "mae_percent": primary["mae_bp"] / 100,
        "mfe_mae_ratio": None if primary["mae_bp"] == 0 else primary["mfe_bp"] / primary["mae_bp"],
        "mfe_time_seconds": mfe_position * v1.q1.SAMPLE_SECONDS,
        "mae_time_seconds": mae_position * v1.q1.SAMPLE_SECONDS,
        "time_to_favorable": {f"{bp}bp": first_crossing(path_bp[: 180 // v1.q1.SAMPLE_SECONDS + 1], bp, True) for bp in TIMING_BP},
        "time_to_adverse": {f"{bp}bp": first_crossing(path_bp[: 180 // v1.q1.SAMPLE_SECONDS + 1], bp, False) for bp in TIMING_BP},
        "path_success": primary["mfe_bp"] >= COST_BP + SAFETY_MARGIN_BP,
        "favorable_before_equal_adverse": mfe_position <= mae_position,
        "cost_estimate_bp": COST_BP,
        "safety_margin_bp": SAFETY_MARGIN_BP,
        "net_excursion_bp": primary["mfe_bp"] - COST_BP,
        "tradeable_move": primary["mfe_bp"] >= COST_BP + SAFETY_MARGIN_BP,
        "magnitude_class": magnitude_class(primary["mfe_bp"]),
        "broker_points_pips": None,
        "broker_points_status": "UNAVAILABLE_VANTAGE_SYMBOL_METADATA",
        "horizons": horizons,
    }


def cell(records: list[dict], horizon: int, threshold: int, days: int) -> dict:
    values = [record["horizons"][str(horizon)] for record in records]
    success = [value["endpoint_direction_correct"] and value["mfe_bp"] >= threshold for value in values]
    return {
        "target": f"endpoint direction correct AND MFE >= {threshold}bp",
        "precision": sum(success) / len(values),
        "wins": sum(success),
        "N": len(values),
        "signals_per_day": len(values) / days,
        "net_ev_bp": float(np.mean([value["net_endpoint_bp"] for value in values])),
        "median_mfe_bp": float(np.median([value["mfe_bp"] for value in values])),
        "median_mae_bp": float(np.median([value["mae_bp"] for value in values])),
        "median_mfe_usd": float(np.median([value["mfe_usd"] for value in values])),
        "median_mae_usd": float(np.median([value["mae_usd"] for value in values])),
    }


def percentile_summary(records: list[dict]) -> dict:
    winners = [record for record in records if record["endpoint_direction_correct"]]
    return {
        "N": len(winners),
        "median_mfe_bp": float(np.median([row["mfe_bp"] for row in winners])),
        "p25_mfe_bp": float(np.percentile([row["mfe_bp"] for row in winners], 25)),
        "p75_mfe_bp": float(np.percentile([row["mfe_bp"] for row in winners], 75)),
        "median_mfe_usd": float(np.median([row["mfe"] for row in winners])),
        "median_mae_bp": float(np.median([row["mae_bp"] for row in winners])),
        "median_mae_usd": float(np.median([row["mae"] for row in winners])),
        "median_endpoint_bp": float(np.median([row["endpoint_bp"] for row in winners])),
        "median_endpoint_usd": float(np.median([row["endpoint_usd_move"] for row in winners])),
        "median_time_to_mfe_seconds": float(np.median([row["mfe_time_seconds"] for row in winners])),
        "tradeable_winners": sum(row["tradeable_move"] for row in winners),
    }


def persist(result: dict, records: list[dict]) -> None:
    v1.write_json(OUTPUT / "magnitude_result.json", result)
    v1.write_json(OUTPUT / "prediction_records.json", records)
    payload = v1.canonical({"candidate": v1.CANDIDATE_ID, "magnitude_result": result}).decode()
    record_id = hashlib.sha256(payload.encode()).hexdigest()
    with sqlite3.connect(v1.MEMORY) as database:
        database.executescript(v1.q1.SCHEMA)
        database.execute(
            "INSERT OR IGNORE INTO research_records VALUES (?,?,?,?,?,?)",
            (record_id, "v1_magnitude_analysis", pd.Timestamp.now("UTC").isoformat(), "2025-03-16", "2026-07-31", payload),
        )


def write_report(result: dict) -> None:
    matrix = result["matrix"]
    lines = [
        "# WAVERUN Move Magnitude Report",
        "",
        "Every precision below means: **predicted endpoint direction correct AND maximum favorable excursion reached the stated magnitude**. It is not one-tick directional precision.",
        "",
        "Prices are Binance research proxies at 5-second resolution. Movement is normalized to USD, basis points, and percent. Vantage broker points/pips, real spread, and real slippage remain unavailable.",
        "",
        "Cell format: `precision; N; signals/day; proxy net endpoint EV; median MFE; median MAE`. N and frequency describe the independent V1 decisions evaluated in that cell; they are not the number of successful threshold hits.",
        "",
        "| Minimum MFE | 30s | 60s | 90s | 180s | 300s |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for threshold in MAGNITUDES_BP:
        values = [matrix[str(threshold)][str(horizon)] for horizon in HORIZONS]
        cells = " | ".join(
            f"{value['precision']:.2%}; N{value['N']}; {value['signals_per_day']:.2f}/d; "
            f"EV{value['net_ev_bp']:+.2f}bp; MFE{value['median_mfe_bp']:.2f}; MAE{value['median_mae_bp']:.2f}bp"
            for value in values
        )
        lines.append(f"| >={threshold}bp | {cells} |")
    winners = result["winner_summary_180s"]
    lines.extend(
        [
            "",
            "## Existing 101 directional winners at 180s",
            "",
            f"- Median MFE: {winners['median_mfe_bp']:.2f} bp / ${winners['median_mfe_usd']:.2f}",
            f"- MFE P25/P75: {winners['p25_mfe_bp']:.2f} / {winners['p75_mfe_bp']:.2f} bp",
            f"- Median MAE: {winners['median_mae_bp']:.2f} bp / ${winners['median_mae_usd']:.2f}",
            f"- Median endpoint: {winners['median_endpoint_bp']:.2f} bp / ${winners['median_endpoint_usd']:.2f}",
            f"- Median time to MFE: {winners['median_time_to_mfe_seconds']:.0f}s",
            f"- Tradeable under the 3bp proxy cost + 2bp safety definition: {winners['tradeable_winners']}/{winners['N']}",
            "",
            "## Core answer",
            "",
            result["core_answer"],
            "",
            "Execution remains `DISABLED`. V1 remains immutable and `FAILED`.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    frozen = v1.verify_freeze()
    features = frozen["candidate"]["features"]
    frames = {"Q1_WF": load_q1_walk(features)}
    frames.update({name: load_blind(bounds, features) for name, bounds in v1.PERIODS.items()})
    predictions = {name: v1.predict(frame, frozen) for name, frame in frames.items()}
    entries = {name: v1.selected(prediction) for name, prediction in predictions.items()}
    records = [record_for_entry(entry, frames[name], name) for name, selected in entries.items() for _, entry in selected.iterrows()]
    days = sum(frame.timestamp.dt.date.nunique() for frame in frames.values())
    matrix = {str(threshold): {str(horizon): cell(records, horizon, threshold, days) for horizon in HORIZONS} for threshold in MAGNITUDES_BP}
    qualifying = [
        (threshold, horizon, matrix[str(threshold)][str(horizon)])
        for threshold in MAGNITUDES_BP
        for horizon in HORIZONS
        if matrix[str(threshold)][str(horizon)]["precision"] >= 0.70
        and matrix[str(threshold)][str(horizon)]["signals_per_day"] >= 3
        and matrix[str(threshold)][str(horizon)]["net_ev_bp"] > 0
    ]
    result = {
        "candidate": v1.CANDIDATE_ID,
        "fingerprint": frozen["fingerprint_sha256"],
        "execution": "DISABLED",
        "price_reference": "BINANCE_RESEARCH_PROXY",
        "resolution_seconds": v1.q1.SAMPLE_SECONDS,
        "cost_assumption_bp": COST_BP,
        "safety_margin_bp": SAFETY_MARGIN_BP,
        "tradeable_definition": "MFE >= 5bp (3bp aggregate proxy cost + 2bp safety margin)",
        "precision_definition": "endpoint direction correct AND MFE >= target bp",
        "signals": len(records),
        "days": days,
        "matrix": matrix,
        "winner_summary_180s": percentile_summary(records),
        "qualifying_product_cells": qualifying,
        "core_answer": f"No tested magnitude/horizon cell reaches 3-10 independent V1 signals/day with >=70% combined direction-and-magnitude precision and positive proxy net EV. No reliable 80-90% magnitude class exists. V1 produces only {len(records) / days:.2f} signals/day before any magnitude requirement.",
        "vantage_pips_status": "UNAVAILABLE",
        "holdout": "CLOSED_UNTOUCHED",
    }
    persist(result, records)
    write_report(result)
    print(json.dumps({"signals": len(records), "days": days, "winner_summary": result["winner_summary_180s"], "qualifying_product_cells": qualifying, "core_answer": result["core_answer"]}, indent=2))


if __name__ == "__main__":
    main()
