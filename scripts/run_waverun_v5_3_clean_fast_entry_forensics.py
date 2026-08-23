"""Pre-T0 forensics for the frozen V5.3 fast-path discovery cases."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
FAST_PATH = ROOT / "data/reports/waverun_v5_3_fast_300s_autopsy/fast_300s_autopsy.json"
OUT = ROOT / "data/reports/waverun_v5_3_clean_fast_entry_forensics"
DEFINITION_HASH = "cbeb17ec5e2bc819fc54e01da0ed8a70bc319cb248d4aa6b225147b56a946f60"

REPORTS = {
    "master": ROOT / "WAVERUN_V5_3_CLEAN_FAST_ENTRY_FORENSICS.md",
    "primary": ROOT / "WAVERUN_V5_3_IMMEDIATE_VS_WRONG_DIRECTION.md",
    "pullback": ROOT / "WAVERUN_V5_3_PULLBACK_TIMING_REPORT.md",
    "veto": ROOT / "WAVERUN_V5_3_VETO_ANALYSIS.md",
    "hypothesis": ROOT / "WAVERUN_V5_3_FAST_V2_HYPOTHESIS.md",
}

GROUPS = (
    "IMMEDIATE_CONTINUATION",
    "PULLBACK_THEN_CONTINUATION",
    "WRONG_DIRECTION",
    "SPIKE_THEN_REVERSAL",
    "CHOP",
)
PRIMARY_A = "IMMEDIATE_CONTINUATION"
PRIMARY_C = "WRONG_DIRECTION"
WINDOWS = (30, 60, 180, 300)
TIMEPOINTS = (-300, -180, -120, -90, -60, -45, -30, -20, -15, -10, -5, 0)

RAW_COLUMNS = [
    "timestamp",
    "spot_price",
    "spot_volume",
    "futures_price",
    "spot_pressure_10s",
    "spot_pressure_30s",
    "spot_pressure_persistence",
    "spot_pressure_acceleration",
    "futures_pressure_10s",
    "futures_pressure_30s",
    "futures_pressure_persistence",
    "futures_pressure_acceleration",
    "spot_cvd_30s",
    "spot_cvd_velocity",
    "spot_cvd_acceleration",
    "futures_cvd_30s",
    "futures_cvd_velocity",
    "futures_cvd_acceleration",
    "spot_trade_intensity_30s",
    "spot_trade_intensity_acceleration",
    "futures_trade_intensity_30s",
    "futures_trade_intensity_acceleration",
    "spot_futures_agreement",
    "spot_lead_1s",
    "futures_lead_1s",
    "flow_pressure",
    "flow_pressure_acceleration",
    "price_response_efficiency",
    "flow_price_absorption",
    "volatility_60s",
    "volatility_score",
    "range_60s",
    "expansion_score",
    "mean_zscore",
    "exhaustion",
    "structure_break",
    "regime",
]
for horizon in (5, 10, 30, 60, 180, 300):
    RAW_COLUMNS.extend([f"price_return_{horizon}s", f"price_acceleration_{horizon}s"])
for horizon in (30, 60, 180, 300):
    RAW_COLUMNS.extend(
        [
            f"macd_{horizon}s_macd",
            f"macd_{horizon}s_signal",
            f"macd_{horizon}s_histogram",
            f"macd_{horizon}s_histogram_slope",
            f"macd_{horizon}s_histogram_acceleration",
            f"macd_{horizon}s_cross_age",
        ]
    )


def read_fast_cases() -> pd.DataFrame:
    payload = json.loads(FAST_PATH.read_text(encoding="utf-8"))
    if payload["definition_sha256"] != DEFINITION_HASH:
        raise RuntimeError("Frozen V5.3 fingerprint mismatch")
    cases = pd.DataFrame(payload["cases"])
    cases["timestamp"] = pd.to_datetime(cases["timestamp"], utc=True)
    counts = Counter(cases["path_shape"])
    expected = {
        "IMMEDIATE_CONTINUATION": 19,
        "PULLBACK_THEN_CONTINUATION": 10,
        "WRONG_DIRECTION": 13,
        "SPIKE_THEN_REVERSAL": 4,
        "CHOP": 1,
    }
    if counts != expected:
        raise RuntimeError(f"Frozen path groups changed: {counts}")
    return cases


def load_candidate_days(cases: pd.DataFrame) -> pd.DataFrame:
    needed = set(cases.timestamp.dt.strftime("%Y-%m-%d"))
    needed.update((cases.timestamp - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d"))
    frames: list[pd.DataFrame] = []
    for path in sorted((ROOT / "runtime/waverun_data/derived").rglob("*.parquet")):
        if path.stem not in needed:
            continue
        try:
            frame = pd.read_parquet(path, columns=RAW_COLUMNS)
        except (OSError, ValueError):
            available = pd.read_parquet(path).columns
            frame = pd.read_parquet(
                path, columns=[c for c in RAW_COLUMNS if c in available]
            )
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frames.append(frame)
    if not frames:
        raise RuntimeError("No candidate-day parquet data found")
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values("timestamp")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )


def trailing_age(values: np.ndarray, index: int, predicate: Any) -> float | None:
    if index < 0 or not predicate(values[index]):
        return None
    start = index
    while start > 0 and predicate(values[start - 1]):
        start -= 1
    return float((index - start + 1) * 5)


def efficiency(prices: np.ndarray) -> float | None:
    if len(prices) < 2:
        return None
    travel = float(np.abs(np.diff(prices)).sum())
    return None if travel == 0 else float(abs(prices[-1] - prices[0]) / travel)


def session(timestamp: pd.Timestamp) -> str:
    hour = timestamp.hour
    if 0 <= hour < 7:
        return "EUROPE"
    if 7 <= hour < 13:
        return "US"
    if 13 <= hour < 18:
        return "OVERLAP"
    return "ASIA"


def expansion_phase(score: float, exhaustion: float) -> str:
    if np.isfinite(exhaustion) and exhaustion > 0:
        return "EXHAUSTION"
    if not np.isfinite(score):
        return "UNKNOWN"
    if score <= 20:
        return "COMPRESSION"
    if score <= 40:
        return "PRE_EXPANSION"
    if score <= 70:
        return "EARLY_EXPANSION"
    return "MATURE_EXPANSION"


def build_features(
    cases: pd.DataFrame, frame: pd.DataFrame
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    lookup = {timestamp: index for index, timestamp in enumerate(frame.timestamp)}
    prices = frame.spot_price.to_numpy(float)
    rows: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    for case in cases.itertuples():
        index = lookup.get(case.timestamp)
        if index is None or index < 60:
            raise RuntimeError(f"Missing pre-T0 path for {case.timestamp}")
        row = frame.iloc[index]
        record: dict[str, Any] = {
            "timestamp": case.timestamp.isoformat(),
            "group": case.path_shape,
            "session": session(case.timestamp),
            "expansion_phase": expansion_phase(
                float(row.get("expansion_score", np.nan)),
                float(row.get("exhaustion", np.nan)),
            ),
            "outcome_100_300s": bool(case.reached_100),
            "mae_before_100_magnitude": case.mae_before_100_magnitude,
            "time_to_first_positive_s": case.time_to_first_positive_s,
            "time_to_100_s": case.time_to_100_s,
        }
        path_record = {
            "timestamp": case.timestamp.isoformat(),
            "group": case.path_shape,
            "points": {},
        }
        for offset in TIMEPOINTS:
            point = frame.iloc[index + offset // 5]
            path_record["points"][str(offset)] = {
                "timestamp": point.timestamp.isoformat(),
                "spot_price": float(point.spot_price),
                "macd_30s_histogram": finite(point.get("macd_30s_histogram")),
                "flow_pressure": finite(point.get("flow_pressure")),
                "volatility_score": finite(point.get("volatility_score")),
                "price_response_efficiency": finite(
                    point.get("price_response_efficiency")
                ),
            }
        for column in RAW_COLUMNS:
            if column not in {"timestamp", "regime"} and column in row.index:
                value = finite(row[column])
                if value is not None:
                    record[column] = value
        for seconds in WINDOWS:
            count = seconds // 5
            history = prices[index - count : index + 1]
            record[f"short_favorable_move_{seconds}s"] = float(history[0] - history[-1])
            record[f"trend_efficiency_{seconds}s"] = efficiency(history)
            low = float(history.min())
            high = float(history.max())
            record[f"range_position_{seconds}s"] = (
                None if high == low else float((history[-1] - low) / (high - low))
            )
            record[f"realized_volatility_{seconds}s"] = float(np.std(np.diff(history)))
            record[f"range_usd_{seconds}s"] = high - low
        for seconds in (300, 900, 3600):
            count = seconds // 5
            history = prices[max(0, index - count + 1) : index + 1]
            low = float(history.min())
            high = float(history.max())
            record[f"range_position_{seconds}s"] = (
                None if high == low else float((history[-1] - low) / (high - low))
            )
        day = frame.timestamp.dt.floor("D") == case.timestamp.floor("D")
        day_indices = np.flatnonzero(day.to_numpy() & (frame.index.to_numpy() <= index))
        day_frame = frame.iloc[day_indices]
        volume = (
            day_frame.get("spot_volume", pd.Series(dtype=float))
            .fillna(0)
            .to_numpy(float)
        )
        day_prices = day_frame.spot_price.to_numpy(float)
        vwap = (
            float(np.average(day_prices, weights=volume))
            if volume.sum() > 0
            else float(day_prices.mean())
        )
        record["daily_vwap_distance_bp"] = float((prices[index] / vwap - 1) * 10_000)
        hist = frame.macd_30s_histogram.to_numpy(float)
        accel = frame.macd_30s_histogram_acceleration.to_numpy(float)
        price_accel = frame.price_acceleration_30s.to_numpy(float)
        expansion = frame.expansion_score.to_numpy(float)
        record["macd_histogram_negative_age_s"] = trailing_age(
            hist, index, lambda x: np.isfinite(x) and x < 0
        )
        record["macd_acceleration_negative_age_s"] = trailing_age(
            accel, index, lambda x: np.isfinite(x) and x < 0
        )
        record["price_acceleration_negative_age_s"] = trailing_age(
            price_accel, index, lambda x: np.isfinite(x) and x < 0
        )
        record["range_expansion_positive_age_s"] = trailing_age(
            expansion, index, lambda x: np.isfinite(x) and x > 0
        )
        record["distance_from_recent_high_300s"] = float(
            prices[index - 60 : index + 1].max() - prices[index]
        )
        record["distance_from_recent_low_300s"] = float(
            prices[index] - prices[index - 60 : index + 1].min()
        )
        rows.append(record)
        paths.append(path_record)
    return pd.DataFrame(rows), paths


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def effect_table(features: pd.DataFrame) -> list[dict[str, Any]]:
    excluded = {
        "timestamp",
        "group",
        "session",
        "expansion_phase",
        "outcome_100_300s",
        "mae_before_100_magnitude",
        "time_to_first_positive_s",
        "time_to_100_s",
    }
    numeric = [
        column
        for column in features.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(features[column])
    ]
    groups = {name: features[features.group == name] for name in GROUPS}
    result: list[dict[str, Any]] = []
    for column in numeric:
        immediate = groups[PRIMARY_A][column].dropna().to_numpy(float)
        wrong = groups[PRIMARY_C][column].dropna().to_numpy(float)
        if (
            len(immediate) < 8
            or len(wrong) < 8
            or np.all(immediate == immediate[0])
            and np.all(wrong == wrong[0])
        ):
            continue
        pullback = groups["PULLBACK_THEN_CONTINUATION"][column].dropna().to_numpy(float)
        u = float(mannwhitneyu(immediate, wrong, alternative="two-sided").statistic)
        effect = 2 * u / (len(immediate) * len(wrong)) - 1
        quality = (
            "STRONG"
            if abs(effect) >= 0.50
            else "MODERATE"
            if abs(effect) >= 0.30
            else "WEAK"
        )
        result.append(
            {
                "feature": column,
                "immediate_median": float(np.median(immediate)),
                "pullback_median": None
                if not len(pullback)
                else float(np.median(pullback)),
                "wrong_direction_median": float(np.median(wrong)),
                "rank_biserial_effect": effect,
                "direction": "HIGHER_IN_IMMEDIATE"
                if effect > 0
                else "LOWER_IN_IMMEDIATE",
                "separation_quality": quality,
                "data_quality": f"A={len(immediate)}, B={len(pullback)}, C={len(wrong)}; causal T0/pre-T0 proxy",
                "interpretation": interpretation(column, effect),
            }
        )
    return sorted(
        result, key=lambda item: abs(item["rank_biserial_effect"]), reverse=True
    )


def interpretation(feature: str, effect: float) -> str:
    direction = "higher" if effect > 0 else "lower"
    if "vwap" in feature:
        return f"Immediate cases had {direction} point-in-time VWAP displacement; discovery-only."
    if "volatility" in feature or "range_usd" in feature:
        return f"Immediate cases had {direction} pre-entry volatility/range; possible chaos veto only if retention is acceptable."
    if "age" in feature:
        return f"Immediate cases had {direction} causal momentum age; tests freshness versus lateness."
    if "efficiency" in feature:
        return f"Immediate cases had {direction} pre-entry response efficiency."
    return (
        f"Immediate median was {direction}; descriptive single-feature separation only."
    )


def threshold_search(
    features: pd.DataFrame,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    primary = features[features.group.isin([PRIMARY_A, PRIMARY_C])].copy()
    excluded = {
        "timestamp",
        "group",
        "session",
        "expansion_phase",
        "outcome_100_300s",
        "mae_before_100_magnitude",
        "time_to_first_positive_s",
        "time_to_100_s",
    }
    candidates: list[dict[str, Any]] = []
    for column in primary.columns:
        if column in excluded or not pd.api.types.is_numeric_dtype(primary[column]):
            continue
        values = np.sort(primary[column].dropna().unique())
        if len(values) < 4:
            continue
        thresholds = (values[:-1] + values[1:]) / 2
        for threshold in thresholds:
            for operator in ("<", ">"):
                blocked = (
                    primary[column] < threshold
                    if operator == "<"
                    else primary[column] > threshold
                )
                a_lost = int((blocked & (primary.group == PRIMARY_A)).sum())
                c_blocked = int((blocked & (primary.group == PRIMARY_C)).sum())
                a_kept = 19 - a_lost
                c_kept = 13 - c_blocked
                precision = a_kept / (a_kept + c_kept) if a_kept + c_kept else 0.0
                candidates.append(
                    {
                        "feature": column,
                        "block_operator": operator,
                        "threshold": float(threshold),
                        "immediate_kept": a_kept,
                        "immediate_blocked": a_lost,
                        "wrong_blocked": c_blocked,
                        "wrong_kept": c_kept,
                        "primary_precision": precision,
                        "primary_coverage": (a_kept + c_kept) / 32,
                        "score": c_blocked - 2 * a_lost,
                    }
                )
    eligible_veto = [
        c for c in candidates if c["wrong_blocked"] >= 4 and c["immediate_blocked"] <= 3
    ]
    veto = max(
        eligible_veto,
        key=lambda c: (c["score"], c["primary_precision"], c["primary_coverage"]),
        default=None,
    )
    eligible_booster = [
        c
        for c in candidates
        if c["immediate_kept"] >= 10
        and c["primary_precision"] > 19 / 32
        and (veto is None or c["feature"] != veto["feature"])
    ]
    booster = max(
        eligible_booster,
        key=lambda c: (c["primary_precision"], c["immediate_kept"], -c["wrong_kept"]),
        default=None,
    )
    return veto, booster


def applies(frame: pd.DataFrame, rule: dict[str, Any] | None) -> pd.Series:
    if rule is None:
        return pd.Series(True, index=frame.index)
    blocked = (
        frame[rule["feature"]] < rule["threshold"]
        if rule["block_operator"] == "<"
        else frame[rule["feature"]] > rule["threshold"]
    )
    return ~blocked.fillna(False)


def filter_metrics(
    features: pd.DataFrame,
    veto: dict[str, Any] | None,
    booster: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keep = applies(features, veto)
    if booster is not None:
        keep &= applies(features, booster)
    retained = features[keep]
    winners = retained[retained.group.isin([PRIMARY_A, "PULLBACK_THEN_CONTINUATION"])]
    return {
        "signals_retained": len(retained),
        "fast_winners_retained": len(winners),
        "discovery_rate": None if retained.empty else len(winners) / len(retained),
        "median_mae_before_100": None
        if winners.empty
        else finite(winners.mae_before_100_magnitude.dropna().median()),
        "median_time_to_100_s": None
        if winners.empty
        else finite(winners.time_to_100_s.dropna().median()),
    }


def matched_pairs(features: pd.DataFrame) -> list[dict[str, Any]]:
    immediate = features[features.group == PRIMARY_A].copy()
    wrong = features[features.group == PRIMARY_C].copy()
    match_columns = [
        "volatility_score",
        "price_return_30s",
        "macd_30s_histogram",
        "macd_30s_cross_age",
    ]
    combined = (
        pd.concat([immediate[match_columns], wrong[match_columns]])
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )
    mean = combined.mean()
    std = combined.std().replace(0, 1)
    a = (immediate[match_columns].fillna(0) - mean) / std
    c = (wrong[match_columns].fillna(0) - mean) / std
    distances = cdist(a.to_numpy(float), c.to_numpy(float))
    pairs = []
    for ai, row in enumerate(immediate.itertuples()):
        same_session = np.asarray(
            [session_value == row.session for session_value in wrong.session]
        )
        candidate_distances = distances[ai].copy()
        candidate_distances[~same_session] += 1.0
        ci = int(np.argmin(candidate_distances))
        pairs.append(
            {
                "immediate_timestamp": row.timestamp,
                "wrong_timestamp": wrong.iloc[ci].timestamp,
                "distance": float(candidate_distances[ci]),
                "same_session": bool(same_session[ci]),
            }
        )
    return pairs


def matched_differences(
    features: pd.DataFrame,
    pairs: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_timestamp = features.set_index("timestamp")
    result = []
    for comparison in comparisons:
        feature = comparison["feature"]
        differences = []
        for pair in pairs:
            immediate = by_timestamp.loc[pair["immediate_timestamp"], feature]
            wrong = by_timestamp.loc[pair["wrong_timestamp"], feature]
            if pd.notna(immediate) and pd.notna(wrong):
                differences.append(float(immediate - wrong))
        if differences:
            result.append(
                {
                    "feature": feature,
                    "matched_median_immediate_minus_wrong": float(
                        np.median(differences)
                    ),
                    "positive_pairs": int((np.asarray(differences) > 0).sum()),
                    "negative_pairs": int((np.asarray(differences) < 0).sum()),
                    "pair_count": len(differences),
                }
            )
    return result


def subgroup_quality(features: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for group in GROUPS:
        subset = features[features.group == group]
        winners = subset[subset.outcome_100_300s]
        result[group] = {
            "n": len(subset),
            "rate_100_300s": None
            if subset.empty
            else float(subset.outcome_100_300s.mean()),
            "mae_before_100": distributions(
                winners.mae_before_100_magnitude.dropna().tolist()
            ),
            "time_to_first_positive_s": distributions(
                subset.time_to_first_positive_s.dropna().tolist()
            ),
            "time_to_100_s": distributions(winners.time_to_100_s.dropna().tolist()),
        }
    return result


def distributions(values: list[float]) -> dict[str, float | None]:
    return {
        f"p{q}": None if not values else float(np.percentile(values, q))
        for q in (50, 75, 90)
    }


def wrong_casebook(
    features: pd.DataFrame,
    veto: dict[str, Any] | None,
    top_features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wrong = features[features.group == PRIMARY_C]
    immediate = features[features.group == PRIMARY_A]
    vol_median = immediate.volatility_score.median()
    efficiency_median = immediate.price_response_efficiency.median()
    cross_median = immediate.macd_30s_cross_age.median()
    result = []
    for row in wrong.itertuples():
        vetoed = (
            False
            if veto is None
            else bool(applies(pd.DataFrame([row._asdict()]), veto).iloc[0] is False)
        )
        result.append(
            {
                "timestamp": row.timestamp,
                "looked_bearish": "All frozen V5.3 negative MACD cross/histogram/slope/acceleration conditions held.",
                "pre_t0_contradiction": [
                    f"{item['feature']}={getattr(row, item['feature'], None)}"
                    for item in top_features[:3]
                ],
                "candidate_veto_triggered": vetoed,
                "late_signal_proxy": bool(row.macd_30s_cross_age > cross_median),
                "excessive_volatility_proxy": bool(row.volatility_score > vol_median),
                "weak_price_response_proxy": bool(
                    row.price_response_efficiency < efficiency_median
                ),
                "structure_location": "UNKNOWN where deterministic source fields are absent",
            }
        )
    return result


def main() -> None:
    cases = read_fast_cases()
    frame = load_candidate_days(cases)
    features, pre_t0_paths = build_features(cases, frame)
    comparisons = effect_table(features)
    veto, booster = threshold_search(features)
    veto_metrics = filter_metrics(features, veto)
    combined_metrics = filter_metrics(features, veto, booster)
    matched = matched_pairs(features)
    matched_feature_differences = matched_differences(
        features, matched, comparisons[:30]
    )
    quality = subgroup_quality(features)
    wrong = wrong_casebook(features, veto, comparisons)
    veto_justified = (
        veto is not None
        and veto["wrong_blocked"] >= 4
        and veto["immediate_blocked"] <= 3
    )
    booster_justified = (
        booster is not None
        and booster["primary_precision"] >= 0.70
        and booster["immediate_kept"] >= 15
    )
    hypothesis = {
        "name": "WAVERUN_V5_3_FAST_V2_HYPOTHESIS",
        "status": "DEFINED_DISCOVERY_ONLY" if veto_justified else "NOT_JUSTIFIED",
        "base_definition_sha256": DEFINITION_HASH,
        "veto": veto if veto_justified else None,
        "booster": booster if booster_justified else None,
        "holdout": "CLOSED",
        "execution": "DISABLED",
    }
    hypothesis["sha256"] = hashlib.sha256(
        json.dumps(hypothesis, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "study_status": "DISCOVERY_PRE_T0_FORENSICS",
        "base_definition_sha256": DEFINITION_HASH,
        "groups": dict(Counter(features.group)),
        "primary_rate_100_300s": 29 / 47,
        "feature_comparisons": comparisons,
        "matched_pairs": matched,
        "matched_feature_differences": matched_feature_differences,
        "best_veto": veto,
        "best_booster": booster,
        "veto_metrics_all_47": veto_metrics,
        "veto_plus_booster_metrics_all_47": combined_metrics,
        "subgroup_entry_quality": quality,
        "wrong_direction_casebook": wrong,
        "pre_t0_paths": pre_t0_paths,
        "features": features.replace({np.nan: None}).to_dict(orient="records"),
        "data_limits": [
            "No historical Vantage Bid/Ask; outcome remains EXCHANGE RESEARCH PROXY.",
            "No historical L2 path; absorption is a derived proxy, not order-book evidence.",
            "FVG, supply/demand, liquidity-pool, and sweep/reclaim fields are unavailable and remain UNKNOWN.",
            "All veto and booster effects are in-sample discovery on the same 47 cases.",
        ],
        "hypothesis": hypothesis,
        "oos_verified": False,
        "holdout": "CLOSED",
        "execution": "DISABLED",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "clean_fast_entry_forensics.json").write_bytes(
        (json.dumps(payload, indent=2) + "\n").encode()
    )
    write_reports(payload)


def rule_text(rule: dict[str, Any] | None) -> str:
    if rule is None:
        return "NONE"
    return f"block when `{rule['feature']} {rule['block_operator']} {rule['threshold']:.8g}`"


def write_reports(data: dict[str, Any]) -> None:
    top = data["feature_comparisons"][:20]
    veto = data["best_veto"]
    booster = data["best_booster"]
    lines = [
        "# WAVERUN V5.3 CLEAN FAST ENTRY FORENSICS",
        "",
        "Discovery-only causal pre-T0 comparison of the exact frozen 47 SHORT candidates.",
        "",
        f"- Frozen definition: `{DEFINITION_HASH}`",
        "- Immediate continuation: **19**",
        "- Pullback then continuation: **10**",
        "- Wrong direction: **13**",
        "- Primary $100/5m discovery rate: **29/47 = 61.70%**",
        "- OOS verified: **NO**",
        "",
        "## Core difference table",
        "",
        "| Feature | Immediate median | Pullback median | Wrong median | Effect | Direction | Separation | Data quality | Interpretation |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for item in top:
        lines.append(
            f"| {item['feature']} | {item['immediate_median']:.6g} | {fmt(item['pullback_median'])} | {item['wrong_direction_median']:.6g} | {item['rank_biserial_effect']:.3f} | {item['direction']} | {item['separation_quality']} | {item['data_quality']} | {item['interpretation']} |"
        )
    lines += [
        "",
        "## Single-factor findings",
        "",
        f"- Best veto: **{rule_text(veto)}**",
        f"- Best booster: **{rule_text(booster)}**",
        "- These are discovery hypotheses selected on the same 47 cases and are not validated.",
        "",
        "## Matched-pair residual differences",
        "",
        "Pairs match approximately on volatility, recent return, MACD histogram/cross age, and session. Reuse of wrong-direction controls is allowed; this is confounder reduction, not independent validation.",
        "",
        "| Feature | Median immediate - wrong | Positive pairs | Negative pairs |",
        "|---|---:|---:|---:|",
        *[
            f"| {item['feature']} | {item['matched_median_immediate_minus_wrong']:.6g} | {item['positive_pairs']}/{item['pair_count']} | {item['negative_pairs']}/{item['pair_count']} |"
            for item in data["matched_feature_differences"][:10]
        ],
        "",
        "## Requested evidence domains",
        "",
        domain_line(data, "Momentum age", "macd_acceleration_negative_age_s"),
        domain_line(data, "MACD cross age", "macd_60s_cross_age"),
        domain_line(data, "Price response", "price_response_efficiency"),
        domain_line(data, "Move already consumed", "short_favorable_move_180s"),
        domain_line(data, "Volatility", "volatility_score"),
        domain_line(data, "VWAP", "daily_vwap_distance_bp"),
        domain_line(data, "Range position", "range_position_3600s"),
        domain_line(data, "Spot/Futures", "spot_futures_agreement"),
        domain_line(data, "Flow-price efficiency", "price_response_efficiency"),
        domain_line(data, "Absorption", "flow_price_absorption"),
        domain_line(data, "Expansion phase", "expansion_score"),
        "- Structural FVG / supply-demand / liquidity-pool / sweep-reclaim: **UNKNOWN**; no deterministic historical fields exist in this layer.",
        "",
        "## Data limits",
        "",
        *[f"- {limit}" for limit in data["data_limits"]],
        "",
        "HOLDOUT: CLOSED",
        "EXECUTION: DISABLED",
        "",
    ]
    REPORTS["master"].write_bytes("\n".join(lines).encode())
    REPORTS["primary"].write_bytes(render_primary(data).encode())
    REPORTS["pullback"].write_bytes(render_pullback(data).encode())
    REPORTS["veto"].write_bytes(render_veto(data).encode())
    REPORTS["hypothesis"].write_bytes(render_hypothesis(data).encode())


def fmt(value: Any) -> str:
    return "UNKNOWN" if value is None else f"{value:.6g}"


def domain_line(data: dict[str, Any], label: str, feature: str) -> str:
    item = next(
        (entry for entry in data["feature_comparisons"] if entry["feature"] == feature),
        None,
    )
    if item is None:
        return f"- {label}: **NO MEASURABLE SEPARATION / UNAVAILABLE**."
    return (
        f"- {label}: immediate `{item['immediate_median']:.6g}`, pullback "
        f"`{fmt(item['pullback_median'])}`, wrong `{item['wrong_direction_median']:.6g}`, "
        f"effect `{item['rank_biserial_effect']:.3f}` ({item['separation_quality']})."
    )


def render_primary(data: dict[str, Any]) -> str:
    lines = [
        "# WAVERUN V5.3 IMMEDIATE VS WRONG DIRECTION",
        "",
        "Primary pre-T0 comparison: 19 immediate continuations versus 13 wrong-direction cases.",
        "",
    ]
    for number, item in enumerate(data["feature_comparisons"][:10], 1):
        lines.append(
            f"{number}. `{item['feature']}`: effect {item['rank_biserial_effect']:.3f}, immediate median {item['immediate_median']:.6g}, wrong median {item['wrong_direction_median']:.6g}."
        )
    lines += [
        "",
        f"Matched pairs created: **{len(data['matched_pairs'])}**. Matching used volatility, recent return, MACD histogram/cross age and session penalty; it does not create an independent sample.",
        "",
        "OOS VERIFIED: NO",
        "HOLDOUT: CLOSED",
        "EXECUTION: DISABLED",
        "",
    ]
    return "\n".join(lines)


def render_pullback(data: dict[str, Any]) -> str:
    immediate = data["subgroup_entry_quality"][PRIMARY_A]
    pullback = data["subgroup_entry_quality"]["PULLBACK_THEN_CONTINUATION"]
    return "\n".join(
        [
            "# WAVERUN V5.3 PULLBACK TIMING REPORT",
            "",
            "The ten pullback winners remain valid $100/5m outcomes; this report does not discard them.",
            "",
            f"Immediate MAE-before-$100: `{immediate['mae_before_100']}`",
            f"Pullback MAE-before-$100: `{pullback['mae_before_100']}`",
            f"Immediate time-to-$100: `{immediate['time_to_100_s']}`",
            f"Pullback time-to-$100: `{pullback['time_to_100_s']}`",
            "",
            "Any future WATCH/ARMED timing logic requires independent validation.",
            "",
            "HOLDOUT: CLOSED",
            "EXECUTION: DISABLED",
            "",
        ]
    )


def render_veto(data: dict[str, Any]) -> str:
    veto = data["best_veto"]
    booster = data["best_booster"]
    return "\n".join(
        [
            "# WAVERUN V5.3 VETO ANALYSIS",
            "",
            f"Best single veto: **{rule_text(veto)}**",
            f"Best single booster: **{rule_text(booster)}**",
            "",
            f"Veto primary-group counts: `{veto}`",
            f"Applied to all 47: `{data['veto_metrics_all_47']}`",
            f"Veto + booster applied to all 47: `{data['veto_plus_booster_metrics_all_47']}`",
            "",
            "Thresholds were searched on discovery data and must not be interpreted as OOS precision.",
            "",
            "HOLDOUT: CLOSED",
            "EXECUTION: DISABLED",
            "",
        ]
    )


def render_hypothesis(data: dict[str, Any]) -> str:
    hypothesis = data["hypothesis"]
    return "\n".join(
        [
            "# WAVERUN V5.3 FAST V2 HYPOTHESIS",
            "",
            f"Status: **{hypothesis['status']}**",
            f"Original frozen definition: `{DEFINITION_HASH}`",
            f"Veto: `{hypothesis['veto']}`",
            f"Optional booster: `{hypothesis['booster']}`",
            f"Hypothesis SHA-256: `{hypothesis['sha256']}`",
            "",
            "This is a discovery-only hypothesis. It is not activated, approved, or OOS verified.",
            "",
            "HOLDOUT: CLOSED",
            "EXECUTION: DISABLED",
            "",
        ]
    )


if __name__ == "__main__":
    main()
