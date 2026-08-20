from __future__ import annotations

import gzip
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / "scripts" / "run_waverun_v1_blind_validation.py"
SPEC = importlib.util.spec_from_file_location("waverun_v1", V1_PATH)
assert SPEC is not None and SPEC.loader is not None
v1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v1)

TARGETS_USD = (200, 300, 400, 500, 600, 800)
ADVERSE_USD = (50, 75, 100, 150, 200)
HORIZONS = (30, 60, 90, 180, 300, 600)
HISTORY_OFFSETS = (300, 180, 120, 60, 30, 10, 0)
PRIMARY_ADVERSE_USD = 100
SAMPLE_SECONDS = 5
COST_BP = 3.0
OUTPUT = ROOT / "data" / "reports" / "waverun_v2_hard_moves"
REPORT = ROOT / "WAVERUN_V2_HARD_MOVE_REPORT.md"

SNAPSHOT_COLUMNS = (
    "spot_pressure_10s", "futures_pressure_10s", "spot_pressure_persistence",
    "futures_pressure_persistence", "flow_pressure_acceleration",
    "spot_futures_agreement", "spot_cvd_acceleration", "futures_cvd_acceleration",
    "price_response_efficiency", "volatility_score", "expansion_score",
    "structure_break", "flow_price_absorption", "macd_pressure",
    "macd_acceleration", "macd_alignment", "regime", "origin", "hour_utc",
)


def write_gzip_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as stream,
    ):
        json.dump(v1.json_safe(payload), stream, separators=(",", ":"), default=str, allow_nan=False)
        stream.write("\n")


def crossing_seconds(values: np.ndarray, level: float, above: bool = True) -> int | None:
    hits = np.flatnonzero(values >= level if above else values <= -level)
    return None if not len(hits) else int(hits[0] * SAMPLE_SECONDS)


def barrier_result(prices: np.ndarray, direction: int, target: float, adverse: float) -> dict:
    signed = direction * (prices - prices[0])
    target_time = crossing_seconds(signed, target)
    adverse_time = crossing_seconds(signed, adverse, above=False)
    success = target_time is not None and (adverse_time is None or target_time < adverse_time)
    return {"success": success, "target_time_seconds": target_time, "adverse_time_seconds": adverse_time}


def load_frames(features: list[str]) -> dict[str, pd.DataFrame]:
    columns = list(dict.fromkeys(["timestamp", "mid", "future_return_180s", "direction_180s", *SNAPSHOT_COLUMNS, *features]))
    frames: dict[str, pd.DataFrame] = {}
    for split, bounds in v1.q1.SPLITS.items():
        split_days = [day for day in v1.q1.days(*bounds) if day not in v1.q1.CASE_DAYS]
        frames[f"Q1_{split.upper()}"] = pd.concat(
            [pd.read_parquet(v1.q1.derived_path(day), columns=columns) for day in split_days], ignore_index=True
        )
    for period, bounds in v1.PERIODS.items():
        frames[period] = pd.concat(
            [pd.read_parquet(v1.blind_path(day), columns=columns) for day in v1.q1.days(*bounds)], ignore_index=True
        )
    return frames


def snapshot(frame: pd.DataFrame, position: int) -> dict:
    output = {}
    timestamps = pd.DatetimeIndex(frame.timestamp)
    day_start = int(timestamps.normalize().searchsorted(timestamps[position].normalize(), side="left"))
    for offset in HISTORY_OFFSETS:
        row = frame.iloc[max(day_start, position - offset // SAMPLE_SECONDS)]
        output[f"T-{offset}s" if offset else "T0"] = {name: row.get(name) for name in SNAPSHOT_COLUMNS}
    return output


def classify_family(row: pd.Series) -> str:
    if row.expansion_score > 70:
        return "VOLATILITY_EXPANSION"
    if row.origin == "CONFIRMED":
        return "SPOT_FUTURES_CONFIRMATION"
    if row.origin == "SPOT_LED":
        return "SPOT_LED_BREAKOUT"
    if row.origin == "FUTURES_LED":
        return "FUTURES_LED_BREAKOUT"
    if abs(row.flow_pressure_acceleration) > 0.25:
        return "PRESSURE_EXPANSION"
    if row.structure_break:
        return "FAILED_PULLBACK_CONTINUATION"
    return "UNCLASSIFIED_HYPOTHESIS"


def independent_moves(frame: pd.DataFrame, period: str) -> list[dict]:
    records: list[dict] = []
    prices = frame.mid.to_numpy(float)
    timestamps = pd.DatetimeIndex(frame.timestamp)
    window = 600 // SAMPLE_SECONDS
    next_allowed = 0
    position = 0
    while position < len(frame) - window:
        if position < next_allowed or timestamps[position].date() != timestamps[position + window].date():
            position += 1
            continue
        path = prices[position : position + window + 1]
        up_time = crossing_seconds(path - path[0], 200)
        down_time = crossing_seconds(path[0] - path, 200)
        available = [(up_time, 1), (down_time, -1)]
        available = [(time, direction) for time, direction in available if time is not None]
        if not available:
            position += 1
            continue
        time_200, direction = min(available)
        signed = direction * (path - path[0])
        maximum = float(signed.max())
        level_times = {str(target): crossing_seconds(signed, target) for target in TARGETS_USD}
        maximum_class = max((target for target in TARGETS_USD if maximum >= target), default=200)
        records.append(
            {
                "record_type": "HARD_MOVE_OPPORTUNITY",
                "period": period,
                "start_time": timestamps[position].isoformat(),
                "direction": "UP" if direction == 1 else "DOWN",
                "starting_price": float(path[0]),
                "maximum_move_usd": maximum,
                "magnitude_class": "MOVE_EXTREME" if maximum >= 1000 else f"MOVE_{maximum_class}",
                "duration_seconds": int(np.argmax(signed) * SAMPLE_SECONDS),
                "time_to_target_seconds": level_times,
                "early_warning_seconds": time_200,
                "pre_move_feature_trajectory": snapshot(frame, position),
                "mechanism_hypothesis": classify_family(frame.iloc[position]),
            }
        )
        # A nested continuation of the same 10-minute path is not a new opportunity.
        next_allowed = position + window
        position = next_allowed
    return records


def v1_entries(frames: dict[str, pd.DataFrame], frozen: dict) -> list[dict]:
    records = []
    allowed = {"Q1_WALK_FORWARD", *v1.PERIODS}
    for period, frame in frames.items():
        if period not in allowed:
            continue
        predicted = v1.predict(frame, frozen)
        for index, entry in v1.selected(predicted).iterrows():
            position = frame.index.get_loc(index)
            end = min(len(frame), position + 600 // SAMPLE_SECONDS + 1)
            if end - position < 600 // SAMPLE_SECONDS + 1:
                continue
            prices = frame.mid.iloc[position:end].to_numpy(float)
            direction = 1 if entry.predicted else -1
            signed = direction * (prices - prices[0])
            records.append(
                {
                    "record_type": "V2_HARD_MOVE_PRECURSOR_BASELINE",
                    "source_candidate": v1.CANDIDATE_ID,
                    "period": period,
                    "timestamp": entry.timestamp.isoformat(),
                    "direction": "UP" if direction == 1 else "DOWN",
                    "entry_price": float(prices[0]),
                    "confidence": float(entry.confidence),
                    "remaining_move_usd": float(signed.max()),
                    "mfe_usd_600s": float(signed.max()),
                    "mae_usd_600s": float(max(0, -signed.min())),
                    "history": snapshot(frame, position),
                    "mechanism_hypothesis": classify_family(entry),
                    "paths": {
                        str(horizon): {
                            str(target): {
                                str(adverse): barrier_result(
                                    prices[: horizon // SAMPLE_SECONDS + 1], direction, target, adverse
                                )
                                for adverse in ADVERSE_USD
                            }
                            for target in TARGETS_USD
                        }
                        for horizon in HORIZONS
                    },
                }
            )
    return records


def matrix_cell(records: list[dict], horizon: int, target: int, adverse: int, days: int) -> dict:
    outcomes = [record["paths"][str(horizon)][str(target)][str(adverse)] for record in records]
    wins = sum(outcome["success"] for outcome in outcomes)
    low, high = v1.wilson_interval(wins, len(outcomes)) if outcomes else (None, None)
    successes = [(record, outcome) for record, outcome in zip(records, outcomes, strict=True) if outcome["success"]]
    cost_usd = [record["entry_price"] * COST_BP / 10_000 for record in records]
    pnl = [target - cost if outcome["success"] else -adverse - cost for outcome, cost in zip(outcomes, cost_usd, strict=True)]

    def direction_precision(direction: str) -> float | None:
        subset = [(record, outcome) for record, outcome in zip(records, outcomes, strict=True) if record["direction"] == direction]
        return None if not subset else sum(outcome["success"] for _, outcome in subset) / len(subset)

    return {
        "evaluated_signals": len(records), "wins": wins,
        "precision": wins / len(records) if records else None,
        "wilson_ci95": [low, high], "signals_per_day": len(records) / days,
        "successful_opportunities_per_day": wins / days,
        "median_lead_time_seconds": None if not successes else float(np.median([outcome["target_time_seconds"] for _, outcome in successes])),
        "median_mfe_usd": float(np.median([record["mfe_usd_600s"] for record in records])),
        "median_mae_usd": float(np.median([record["mae_usd_600s"] for record in records])),
        "proxy_net_ev_usd": float(np.mean(pnl)),
        "UP_precision": direction_precision("UP"), "DOWN_precision": direction_precision("DOWN"),
    }


def diagnostic_group(records: list[dict], target: int = 200, horizon: int = 600, adverse: int = 100) -> dict:
    rows = []
    for record in records:
        success = record["paths"][str(horizon)][str(target)][str(adverse)]["success"]
        t0 = record["history"]["T0"]
        rows.append({"success": success, "family": record["mechanism_hypothesis"], "origin": t0["origin"], "regime": t0["regime"], "macd_extreme": abs(t0["macd_pressure"] or 0) >= 2, "early_expansion": (t0["expansion_score"] or 0) > 40})
    output = {}
    frame = pd.DataFrame(rows)
    for column in ("family", "origin", "regime", "macd_extreme", "early_expansion"):
        output[column] = {
            str(key): {"N": len(group), "wins": int(group.success.sum()), "precision": float(group.success.mean())}
            for key, group in frame.groupby(column, dropna=False)
        }
    return output


def write_report(result: dict) -> None:
    primary = result["primary_matrix"]
    lines = [
        "# WAVERUN V2 Hard Move Report", "",
        "Primary metric: **target hit before adverse barrier**. Endpoint direction is diagnostic only.", "",
        "This is a historical V1-baseline reconstruction for V2 design, not a trained or frozen V2 model. Prices and 3 bp costs are Binance research proxies; execution is disabled and the August holdout is untouched.", "",
        f"Primary displayed adverse barrier: **${PRIMARY_ADVERSE_USD}**. The complete predefined $50/$75/$100/$150/$200 grid is in `hard_move_result.json`.", "",
        "Cell format: `precision [Wilson 95% CI]; wins/N; successful opportunities/day; lead; MFE/MAE; proxy EV; UP/DOWN precision`.", "",
        "| Target | 30s | 60s | 90s | 180s | 300s | 600s |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for target in TARGETS_USD:
        cells = []
        for horizon in HORIZONS:
            cell = primary[str(target)][str(horizon)]
            ci = cell["wilson_ci95"]
            lead = "n/a" if cell["median_lead_time_seconds"] is None else f"{cell['median_lead_time_seconds']:.0f}s"
            up = "n/a" if cell["UP_precision"] is None else f"{cell['UP_precision']:.1%}"
            down = "n/a" if cell["DOWN_precision"] is None else f"{cell['DOWN_precision']:.1%}"
            cells.append(
                f"{cell['precision']:.1%} [{ci[0]:.1%},{ci[1]:.1%}]; {cell['wins']}/{cell['evaluated_signals']}; "
                f"{cell['successful_opportunities_per_day']:.2f}/d; {lead}; ${cell['median_mfe_usd']:.0f}/${cell['median_mae_usd']:.0f}; "
                f"${cell['proxy_net_ev_usd']:+.0f}; {up}/{down}"
            )
        lines.append(f"| ${target} | " + " | ".join(cells) + " |")
    counts = result["move_library_summary"]
    lines += ["", "## Independent hard-move availability", ""]
    for target in TARGETS_USD:
        item = counts[str(target)]
        lines.append(
            f"- ${target}: {item['moves']} independent nested opportunities, {item['moves_per_day']:.2f}/day; "
            f"median time from earliest qualifying anchor {item['median_time_seconds']:.0f}s"
        )
    lines += [
        "", "## Required conclusions", "",
        f"- Best diagnostic precision/frequency cell: {result['best_diagnostic_cell']}.",
        f"- Most predictable tested magnitude in the baseline: {result['most_predictable_magnitude']}.",
        f"- Best predefined adverse barrier by proxy EV: {result['best_adverse_barrier_diagnostic']} (post-hoc diagnostic, not a V2 rule).",
        f"- DOWN versus UP at $200/600s/$100: {result['direction_answer']}.",
        f"- Mechanism diagnostic: {result['mechanism_answer']}.",
        f"- False-positive mechanism diagnostic: {result['false_mechanism_answer']}.",
        f"- Extreme MACD diagnostic: {result['macd_answer']}.",
        f"- Spot/Futures confirmation diagnostic: {result['confirmation_answer']}.",
        f"- Early Expansion diagnostic: {result['expansion_answer']}.",
        f"- Elite 80–90% class: {result['elite_class_answer']}.",
        f"- Product target 3–10/day at >=70% OOS: {result['product_answer']}.",
        f"- Any setup family >=70% OOS: {result['setup_family_oos_answer']}.",
        "- Mechanism, MACD, Spot/Futures, expansion, true-precursor and false-precursor diagnostics are persisted machine-readably; no subgroup is promoted without fresh chronological OOS validation.",
        "", "V1 remains immutable and `FAILED`. V2 status: `RESEARCH_BASELINE_ONLY`. Execution: `DISABLED`.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    frozen = v1.verify_freeze()
    frames = load_frames(frozen["candidate"]["features"])
    moves = [record for period, frame in frames.items() for record in independent_moves(frame, period)]
    precursors = v1_entries(frames, frozen)
    days = sum(frame.timestamp.dt.date.nunique() for frame in frames.values())
    grid = {
        str(adverse): {
            str(target): {str(horizon): matrix_cell(precursors, horizon, target, adverse, days) for horizon in HORIZONS}
            for target in TARGETS_USD
        }
        for adverse in ADVERSE_USD
    }
    primary = grid[str(PRIMARY_ADVERSE_USD)]
    availability = {}
    for target in TARGETS_USD:
        qualifying_moves = [record for record in moves if record["maximum_move_usd"] >= target]
        target_times = [record["time_to_target_seconds"][str(target)] for record in qualifying_moves]
        availability[str(target)] = {
            "moves": len(qualifying_moves), "moves_per_day": len(qualifying_moves) / days,
            "median_time_seconds": float(np.median(target_times)),
        }
    candidates = [(cell["precision"], cell["successful_opportunities_per_day"], target, horizon, adverse, cell) for adverse in ADVERSE_USD for target in TARGETS_USD for horizon, cell in ((h, grid[str(adverse)][str(target)][str(h)]) for h in HORIZONS)]
    best = max(candidates, key=lambda item: (item[0], item[1]))
    ev_best = max(candidates, key=lambda item: item[5]["proxy_net_ev_usd"])
    direction = primary["200"]["600"]
    qualifiers = [item for item in candidates if item[0] >= 0.70 and 3 <= item[1] <= 10 and item[5]["proxy_net_ev_usd"] > 0]
    elites = [item for item in candidates if item[0] >= 0.80 and item[5]["wins"] >= 30]
    false_precursors = [record for record in precursors if not record["paths"]["600"]["200"]["100"]["success"]]
    diagnostics = diagnostic_group(precursors)

    def diagnostic_answer(group: str, key: str | None = None) -> str:
        values = diagnostics[group]
        if key is not None:
            item = values.get(key)
            return "unavailable" if item is None else f"{item['precision']:.2%}, N={item['N']} (post-hoc)"
        eligible = [(name, item) for name, item in values.items() if item["N"] >= 10]
        if not eligible:
            return "insufficient samples"
        name, item = max(eligible, key=lambda pair: pair[1]["precision"])
        return f"{name} highest at {item['precision']:.2%}, N={item['N']} (post-hoc)"

    def false_diagnostic_answer(group: str) -> str:
        eligible = [(name, item) for name, item in diagnostics[group].items() if item["N"] >= 10]
        if not eligible:
            return "insufficient samples"
        name, item = min(eligible, key=lambda pair: pair[1]["precision"])
        return f"{name} lowest at {item['precision']:.2%}, {item['N'] - item['wins']} false cases of N={item['N']} (post-hoc)"

    result = {
        "research_id": "WAVERUN_V2_HARD_MOVE_BASELINE", "status": "RESEARCH_BASELINE_ONLY",
        "execution": "DISABLED", "holdout": "CLOSED_UNTOUCHED", "v1_fingerprint": frozen["fingerprint_sha256"],
        "reference": "BINANCE_RESEARCH_PROXY", "cost_assumption_bp": COST_BP, "days": days,
        "target_definition": "target USD hit before adverse USD barrier within horizon",
        "targets_usd": TARGETS_USD, "adverse_grid_usd": ADVERSE_USD, "horizons_seconds": HORIZONS,
        "independent_move_definition": "greedy earliest $200 crossing in non-overlapping 600s windows; nested targets and continuations do not create independent moves",
        "move_library_summary": availability, "move_library_records": len(moves),
        "precursor_records": len(precursors), "false_precursor_records_200_600_100": len(false_precursors),
        "primary_matrix_adverse_usd": PRIMARY_ADVERSE_USD, "primary_matrix": primary, "full_barrier_grid": grid,
        "diagnostics_200_600_100": diagnostics,
        "best_diagnostic_cell": f"${best[2]}/{best[3]}s/${best[4]} adverse = {best[0]:.2%}, {best[1]:.2f} successes/day, N={best[5]['evaluated_signals']}",
        "most_predictable_magnitude": f"${best[2]} in the post-hoc V1 baseline; no V2 OOS proof",
        "best_adverse_barrier_diagnostic": f"${ev_best[4]} for ${ev_best[2]}/{ev_best[3]}s, proxy EV ${ev_best[5]['proxy_net_ev_usd']:+.2f}",
        "direction_answer": f"UP {direction['UP_precision']:.2%}, DOWN {direction['DOWN_precision']:.2%}",
        "mechanism_answer": diagnostic_answer("family"),
        "false_mechanism_answer": false_diagnostic_answer("family"),
        "macd_answer": diagnostic_answer("macd_extreme", "True"),
        "confirmation_answer": diagnostic_answer("origin", "CONFIRMED"),
        "expansion_answer": diagnostic_answer("early_expansion", "True"),
        "elite_class_answer": "NONE PROVEN" if not elites else "DIAGNOSTIC CELLS EXIST BUT ARE NOT OOS-PROVEN",
        "product_answer": "NOT ACHIEVED" if not qualifiers else "DIAGNOSTIC QUALIFIER EXISTS; NOT OOS-PROVEN",
        "setup_family_oos_answer": "NO; V2 has not yet been trained and chronologically validated",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    v1.write_json(OUTPUT / "hard_move_result.json", result)
    write_gzip_json(OUTPUT / "hard_move_library.json.gz", moves)
    write_gzip_json(OUTPUT / "precursor_library.json.gz", precursors)
    write_gzip_json(OUTPUT / "false_precursor_library.json.gz", false_precursors)
    write_report(result)
    print(json.dumps({key: result[key] for key in ("days", "move_library_records", "precursor_records", "false_precursor_records_200_600_100", "best_diagnostic_cell", "product_answer")}, indent=2))


if __name__ == "__main__":
    main()
