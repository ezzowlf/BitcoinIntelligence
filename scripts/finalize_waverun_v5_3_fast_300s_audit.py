"""Finalize and freeze the V5.3 fast-path discovery audit."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import run_waverun_v5_3_fast_300s_autopsy as source
from scipy.ndimage import minimum_filter1d

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = (
    ROOT / "data/reports/waverun_v5_3_fast_300s_autopsy/fast_300s_autopsy.json"
)
REPORT_PATH = ROOT / "WAVERUN_V5_3_FAST_300S_AUTOPSY.md"
PROTOCOL_PATH = ROOT / "WAVERUN_V5_3_FAST_INDEPENDENT_VALIDATION_PROTOCOL.md"
DEFINITION_PATH = ROOT / "frozen/waverun_v5_3_fast_challenger_definition.json"
TARGETS = (25, 50, 75, 100, 150, 200, 300, 400, 500)
TIME_TARGETS = (25, 50, 75, 100, 150, 200)


def quantiles(values: list[float], include_max: bool = False) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    result = {f"p{q}": float(np.percentile(array, q)) for q in (50, 75, 90)}
    if include_max:
        result["max"] = float(array.max())
    return result


def first_hit(path: np.ndarray, level: float) -> int | None:
    hits = np.flatnonzero(path >= level)
    return None if not len(hits) else int(hits[0])


def order(path: np.ndarray, level: float) -> str:
    favorable = np.flatnonzero(path >= level)
    adverse = np.flatnonzero(path <= -level)
    if not len(favorable) and not len(adverse):
        return "NO_RELEVANT_MOVE"
    if len(favorable) and (not len(adverse) or favorable[0] < adverse[0]):
        return "FAVORABLE_FIRST"
    if len(adverse) and (not len(favorable) or adverse[0] < favorable[0]):
        return "ADVERSE_FIRST"
    return "MIXED"


def shape(path: np.ndarray) -> str:
    mfe = float(path.max())
    mae = max(0.0, -float(path.min()))
    hit_50 = first_hit(path, 50)
    hit_100 = first_hit(path, 100)
    if mfe < 25 and mae < 25:
        return "NO_MOVE"
    if hit_100 is not None:
        mae_before = max(0.0, -float(path[: hit_100 + 1].min()))
        return (
            "IMMEDIATE_CONTINUATION"
            if mae_before <= 50
            else "PULLBACK_THEN_CONTINUATION"
        )
    if hit_50 is not None and path[-1] <= 0:
        return "SPIKE_THEN_REVERSAL"
    if mfe < 50 and mae >= 100:
        return "WRONG_DIRECTION"
    return "CHOP"


def sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def compatible_base_rate(frame: pd.DataFrame) -> dict[str, float | int | str]:
    prices = frame.spot_price.to_numpy(float)
    timestamps = frame.timestamp.to_numpy(dtype="datetime64[s]")
    rows = 60
    reversed_future = prices[1:][::-1]
    lows = minimum_filter1d(
        reversed_future, rows, origin=(rows - 1) // 2, mode="nearest"
    )[::-1]
    future_low = np.full(len(frame), np.nan)
    future_low[:-1] = lows
    valid = np.zeros(len(frame), dtype=bool)
    valid[:-rows] = timestamps[rows:] - timestamps[:-rows] <= np.timedelta64(300, "s")
    excursion = prices - source.COST / 2 - future_low
    hits = valid & np.isfinite(excursion) & (excursion >= 100)
    n = int(valid.sum())
    hit_n = int(hits.sum())
    return {
        "definition": "all valid 5-second timestamps in the same loaded periods; SHORT; same exchange proxy, $8.50 entry adjustment, and MFE >= $100 within 300s",
        "n": n,
        "hits": hit_n,
        "rate": hit_n / n,
    }


def main() -> None:
    frame = source.load()
    indices = source.decluster(frame, source.signal_mask(frame))
    prices = frame.spot_price.to_numpy(float)
    records: list[dict[str, Any]] = []
    for index in indices:
        if index + 720 >= len(frame):
            continue
        path = prices[index] - source.COST / 2 - prices[index + 1 : index + 61]
        path_60m = prices[index] - source.COST / 2 - prices[index + 1 : index + 721]
        mfe_60m = float(path_60m.max())
        mae_60m = max(0.0, -float(path_60m.min()))
        group = (
            "STRONG_WINNER"
            if mfe_60m >= 500
            else "MODERATE_WINNER"
            if mfe_60m >= 300
            else "LATE_WINNER"
            if mfe_60m >= 100
            else "ABSORBED"
            if mae_60m > 100
            else "FAILED_CONTINUATION"
        )
        record: dict[str, Any] = {
            "candidate_index": int(index),
            "timestamp": frame.timestamp.iloc[index].isoformat(),
            "period": frame.period.iloc[index],
            "mfe_300s": float(path.max()),
            "mae_300s_magnitude": max(0.0, -float(path.min())),
            "mfe_60m": mfe_60m,
            "group": group,
            "path_shape": shape(path),
        }
        for target in TARGETS:
            hit = first_hit(path, target)
            record[f"reached_{target}"] = hit is not None
            if target in TIME_TARGETS:
                record[f"time_to_{target}_s"] = None if hit is None else (hit + 1) * 5
                record[f"mae_before_{target}_magnitude"] = (
                    None if hit is None else max(0.0, -float(path[: hit + 1].min()))
                )
        positive = first_hit(path, 0)
        record["time_to_first_positive_s"] = (
            None if positive is None else (positive + 1) * 5
        )
        for target in (25, 50, 75, 100):
            record[f"path_order_{target}"] = order(path, target)
        records.append(record)

    cases = pd.DataFrame(records)
    if len(cases) != 47 or int((cases.mfe_60m >= 100).sum()) != 41:
        raise RuntimeError(
            "Frozen V5.3 population no longer reproduces 47 candidates / 41 winners"
        )
    fast = cases[cases.reached_100]
    if len(fast) != 29:
        raise RuntimeError(f"Expected 29 fast winners, found {len(fast)}")

    cumulative = {
        str(target): {
            "n": int(cases[f"reached_{target}"].sum()),
            "pct": float(cases[f"reached_{target}"].mean() * 100),
        }
        for target in TARGETS
    }
    target_times = {
        str(target): quantiles(
            cases.loc[cases[f"reached_{target}"], f"time_to_{target}_s"].tolist()
        )
        for target in TIME_TARGETS
    }
    path_orders = {
        str(target): dict(Counter(cases[f"path_order_{target}"].tolist()))
        for target in (25, 50, 75, 100)
    }
    path_shapes = dict(Counter(cases.path_shape.tolist()))
    base = compatible_base_rate(frame)
    candidate_rate = len(fast) / len(cases)
    base_rate = float(base["rate"])
    base.update(
        {
            "candidate_rate": candidate_rate,
            "absolute_lift_percentage_points": (candidate_rate - base_rate) * 100,
            "relative_lift_times": candidate_rate / base_rate,
            "relative_lift_percent": (candidate_rate / base_rate - 1) * 100,
        }
    )
    q1 = frame[frame.period == "Q1_2025"]
    frozen_thresholds = {
        "abs_macd_30s_histogram_acceleration_q80": float(
            q1.macd_30s_histogram_acceleration.abs().quantile(0.80)
        ),
        "abs_macd_30s_histogram_q80": float(q1.macd_30s_histogram.abs().quantile(0.80)),
    }
    definition_core = {
        "name": "WAVERUN_V5_3_FAST_CHALLENGER_DEFINITION",
        "status": "FROZEN_DISCOVERY_DEFINITION_NOT_APPROVED",
        "direction": "SHORT",
        "conditions": [
            "macd_30s_cross_direction < 0",
            "macd_30s_histogram < 0",
            "macd_30s_histogram_slope < 0",
            "macd_30s_histogram_acceleration < 0",
            "abs(macd_30s_histogram_acceleration) >= Q1_2025 80th percentile",
            "abs(macd_30s_histogram) >= Q1_2025 80th percentile",
        ],
        "threshold_quantile": 0.80,
        "frozen_numeric_thresholds": frozen_thresholds,
        "decluster_seconds": 180,
        "candidate_count": 47,
        "candidate_timestamps": cases.timestamp.tolist(),
        "outcome": "SHORT MFE >= $100 within 300s; EXCHANGE RESEARCH PROXY; $8.50 entry adjustment",
        "holdout": "CLOSED",
        "execution": "DISABLED",
        "group_counts": dict(Counter(cases.group.tolist())),
    }
    definition = {**definition_core, "sha256": sha256(definition_core)}
    output = {
        "study_status": "DISCOVERY_FAST_PATH_RATE",
        "oos_verified": False,
        "holdout": "CLOSED",
        "execution": "DISABLED",
        "cumulative_300s": cumulative,
        "short_base_rate_100_300s": base,
        "mae_before_100_fast_winners_magnitude": quantiles(
            fast.mae_before_100_magnitude.tolist(), include_max=True
        ),
        "time_to_first_positive_fast_winners_s": quantiles(
            fast.time_to_first_positive_s.tolist()
        ),
        "time_to_target_s": target_times,
        "mfe_300s_all_cases": quantiles(cases.mfe_300s.tolist()),
        "mae_300s_all_cases_magnitude": quantiles(cases.mae_300s_magnitude.tolist()),
        "path_order": path_orders,
        "path_shapes": path_shapes,
        "fast_conversion": {
            "fast": 29,
            "old_winners": 41,
            "rate": 29 / 41,
            "depended_on_more_than_300s": 12,
            "depended_on_more_than_300s_rate": 12 / 41,
        },
        "definition_sha256": definition["sha256"],
        "cases": records,
    }
    RESULT_PATH.write_bytes((json.dumps(output, indent=2) + "\n").encode("utf-8"))
    DEFINITION_PATH.write_bytes(
        (json.dumps(definition, indent=2) + "\n").encode("utf-8")
    )
    REPORT_PATH.write_bytes(render_report(output).encode("utf-8"))
    PROTOCOL_PATH.write_bytes(render_protocol(definition).encode("utf-8"))


def render_report(data: dict[str, Any]) -> str:
    base = data["short_base_rate_100_300s"]
    mae = data["mae_before_100_fast_winners_magnitude"]
    green = data["time_to_first_positive_fast_winners_s"]
    t100 = data["time_to_target_s"]["100"]
    mfe = data["mfe_300s_all_cases"]
    mae_300 = data["mae_300s_all_cases_magnitude"]
    lines = [
        "# WAVERUN V5.3 FAST 300S AUTOPSY",
        "",
        "**DISCOVERY FAST-PATH RATE — NOT OOS VERIFIED.** Historical Vantage Bid/Ask was unavailable; paths are EXCHANGE RESEARCH PROXY.",
        "",
        "## Cumulative target reach within 300 seconds",
        "",
        "| Target | Count | Rate |",
        "|---:|---:|---:|",
    ]
    for target, cell in data["cumulative_300s"].items():
        lines.append(f"| >= ${target} | {cell['n']}/47 | {cell['pct']:.2f}% |")
    lines += [
        "",
        "## Comparable SHORT base rate",
        "",
        f"Candidate: **61.70%**. Base: **{base['hits']}/{base['n']} = {base['rate'] * 100:.2f}%**. Absolute lift: **{base['absolute_lift_percentage_points']:.2f} pp**. Relative lift: **{base['relative_lift_times']:.2f}x / {base['relative_lift_percent']:.2f}%**.",
        "",
        "## Entry quality",
        "",
        f"MAE before $100, adverse magnitude: P50 **${mae['p50']:.2f}**, P75 **${mae['p75']:.2f}**, P90 **${mae['p90']:.2f}**, max **${mae['max']:.2f}**.",
        f"Time to first positive: P50 **{green['p50']:.1f}s**, P75 **{green['p75']:.1f}s**, P90 **{green['p90']:.1f}s**.",
        f"Time to $100: P50 **{t100['p50']:.1f}s**, P75 **{t100['p75']:.1f}s**, P90 **{t100['p90']:.1f}s**.",
        f"First-300s MFE: P50 **${mfe['p50']:.2f}**, P75 **${mfe['p75']:.2f}**, P90 **${mfe['p90']:.2f}**.",
        f"First-300s MAE adverse magnitude: P50 **${mae_300['p50']:.2f}**, P75 **${mae_300['p75']:.2f}**, P90 **${mae_300['p90']:.2f}**.",
        "",
        "### Time to target among cases reaching that target by 300s",
        "",
        "| Target | P50 | P75 | P90 |",
        "|---:|---:|---:|---:|",
        *[
            f"| ${target} | {data['time_to_target_s'][str(target)]['p50']:.1f}s | {data['time_to_target_s'][str(target)]['p75']:.1f}s | {data['time_to_target_s'][str(target)]['p90']:.1f}s |"
            for target in TIME_TARGETS
        ],
        "",
        "## Path order",
        "",
    ]
    for target, counts in data["path_order"].items():
        lines.append(
            f"- ${target}: "
            + ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))
        )
    lines += ["", "## Path classes", ""]
    lines += [
        "Deterministic rules: NO_MOVE means both MFE and adverse magnitude < $25; a $100 hit is IMMEDIATE_CONTINUATION when MAE-before-target <= $50 and PULLBACK_THEN_CONTINUATION otherwise; SPIKE_THEN_REVERSAL reaches $50 without $100 and finishes non-positive; WRONG_DIRECTION has MFE < $50 and adverse magnitude >= $100; all remaining paths are CHOP.",
        "",
    ]
    for name in (
        "IMMEDIATE_CONTINUATION",
        "PULLBACK_THEN_CONTINUATION",
        "SPIKE_THEN_REVERSAL",
        "CHOP",
        "WRONG_DIRECTION",
        "NO_MOVE",
    ):
        lines.append(f"- {name}: **{data['path_shapes'].get(name, 0)}**")
    lines += [
        "",
        "## Interpretation",
        "",
        "The 60-minute window did **not** create most of the old 87.2% result: 29/41 (70.73%) old winners reached $100 within five minutes; 12/41 (29.27%) depended on more than five minutes. This remains discovery evidence, not verified OOS precision or execution evidence.",
        "",
        f"Frozen definition SHA-256: `{data['definition_sha256']}`",
        "",
        "HOLDOUT: CLOSED",
        "EXECUTION: DISABLED",
        "",
    ]
    return "\n".join(lines)


def render_protocol(definition: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# WAVERUN V5.3 FAST INDEPENDENT VALIDATION PROTOCOL",
            "",
            "Status: READY, NOT RUN.",
            f"Definition: `{definition['name']}`",
            f"SHA-256: `{definition['sha256']}`",
            "",
            "- Apply the exact frozen SHORT definition and 180-second declustering rule; no threshold changes or candidate re-selection.",
            "- Primary outcome: SHORT MFE >= $100 within 300 seconds under the identical proxy/cost convention.",
            "- Use an independent chronological period absent from all periods that generated the 47 discovery cases.",
            "- Require at least 100 independent candidates overall and 30 per reported major regime; otherwise INSUFFICIENT_DATA.",
            "- Compare against the compatible SHORT $100/300s base population from the same validation period.",
            "- Report Wilson intervals, absolute/relative lift, MAE-before-$100, and time-to-green/$100.",
            "- Do not open the closed holdout or authorize execution in this protocol.",
            "",
            "HOLDOUT: CLOSED",
            "EXECUTION: DISABLED",
            "",
        ]
    )


if __name__ == "__main__":
    main()
