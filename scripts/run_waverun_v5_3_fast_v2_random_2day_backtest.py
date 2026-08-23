"""Deterministic two-day historical sanity check for frozen V5.3 Fast V2."""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.v5_3_forward import (
    ACCEL_THRESHOLD,
    HISTOGRAM_THRESHOLD,
    HYPOTHESIS_SHA256,
    TARGETS,
    VETO_THRESHOLD,
)

OUT = ROOT / "data/reports/waverun_v5_3_fast_v2_random_2day"
SELECTION = OUT / "selection.json"
RESULT = OUT / "random_2day_backtest.json"
REPORT = ROOT / "WAVERUN_V5_3_FAST_V2_RANDOM_2DAY_BACKTEST.md"
SEED = 20260824
COST = 8.5


def inventory() -> list[Path]:
    return sorted((ROOT / "runtime/waverun_data/derived").rglob("*.parquet"))


def freeze_selection(paths: list[Path]) -> dict:
    dates = [path.stem for path in paths if path.stem not in {"2026-08-16", "2026-08-17"}]
    digest = hashlib.sha256("\n".join(dates).encode()).hexdigest()
    chosen = sorted(random.Random(SEED).sample(dates, 2))
    payload = {"seed": SEED, "eligible_dates": dates, "eligible_universe_sha256": digest,
               "selected_dates": chosen, "selected_before_performance_access": True}
    OUT.mkdir(parents=True, exist_ok=True)
    if SELECTION.exists():
        old = json.loads(SELECTION.read_text(encoding="utf-8"))
        if old != payload:
            raise RuntimeError("Frozen two-day selection changed")
    else:
        SELECTION.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def candidates(frame: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (frame.macd_30s_cross_direction < 0) & (frame.macd_30s_histogram < 0)
        & (frame.macd_30s_histogram_slope < 0) & (frame.macd_30s_histogram_acceleration < 0)
        & (frame.macd_30s_histogram_acceleration.abs() >= ACCEL_THRESHOLD)
        & (frame.macd_30s_histogram.abs() >= HISTOGRAM_THRESHOLD)
    )
    selected = frame.loc[mask].copy()
    keep, last = [], None
    for index, row in selected.iterrows():
        stamp = pd.Timestamp(row.timestamp)
        if last is None or (stamp - last).total_seconds() >= 180:
            keep.append(index); last = stamp
    return selected.loc[keep]


def path_result(frame: pd.DataFrame, row: pd.Series) -> dict | None:
    stamp = pd.Timestamp(row.timestamp)
    path = frame[(pd.to_datetime(frame.timestamp, utc=True) > stamp) &
                 (pd.to_datetime(frame.timestamp, utc=True) <= stamp + pd.Timedelta(seconds=300))]
    if len(path) < 60:
        return None
    favorable = float(row.mid) - path.mid.to_numpy(dtype=float) - COST
    times = (pd.to_datetime(path.timestamp, utc=True) - stamp).dt.total_seconds().to_numpy()
    hits = {str(t): bool(np.any(favorable >= t)) for t in TARGETS}
    hit_times = {str(t): float(times[np.flatnonzero(favorable >= t)[0]]) if hits[str(t)] else None for t in TARGETS}
    t100 = hit_times["100"]
    pre = favorable[times <= t100] if t100 is not None else favorable
    return {"timestamp": stamp.isoformat(), "spot_pressure_10s": float(row.spot_pressure_10s),
            "accepted": bool(row.spot_pressure_10s <= VETO_THRESHOLD), "target_hits": hits,
            "target_times_s": hit_times, "mfe": float(favorable.max()),
            "mae": float(max(0, -favorable.min())), "mae_before_100": float(max(0, -pre.min())),
            "time_to_first_positive_s": float(times[np.flatnonzero(favorable > 0)[0]]) if np.any(favorable > 0) else None}


def summarize(rows: list[dict]) -> dict:
    accepted = [r for r in rows if r["accepted"]]
    original = rows
    def target(group, value):
        wins = sum(r["target_hits"][str(value)] for r in group)
        return {"wins": wins, "n": len(group), "rate": wins / len(group) if group else None}
    blocked = [r for r in rows if not r["accepted"]]
    return {"original_signals": len(original), "v2_signals": len(accepted),
            "targets_300s": {str(t): target(accepted, t) for t in TARGETS},
            "original_100_5m": target(original, 100),
            "veto": {"blocked": len(blocked), "blocked_winners": sum(r["target_hits"]["100"] for r in blocked),
                     "blocked_failures": sum(not r["target_hits"]["100"] for r in blocked)},
            "rows": rows}


def main() -> None:
    paths = inventory(); selection = freeze_selection(paths)
    lookup = {path.stem: path for path in paths}
    all_rows, days, base_wins, base_n = [], {}, 0, 0
    for day in selection["selected_dates"]:
        frame = pd.read_parquet(lookup[day]).sort_values("timestamp").reset_index(drop=True)
        rows = [result for _, row in candidates(frame).iterrows() if (result := path_result(frame, row))]
        day_summary = summarize(rows); days[day] = day_summary; all_rows.extend(rows)
        for index in range(len(frame) - 60):
            favorable = float(frame.iloc[index].mid) - frame.iloc[index + 1:index + 61].mid.min() - COST
            base_wins += favorable >= 100; base_n += 1
    combined = summarize(all_rows)
    combined["comparable_short_base_rate"] = {"wins": int(base_wins), "n": base_n, "rate": base_wins / base_n}
    rate = combined["targets_300s"]["100"]["rate"]
    base = base_wins / base_n
    combined["absolute_lift_percentage_points"] = None if rate is None else 100 * (rate - base)
    combined["relative_lift_times"] = None if rate is None else rate / base
    payload = {"label": "RANDOM-DAY HISTORICAL SANITY CHECK / NOT OOS VALIDATION",
               "hypothesis_sha256": HYPOTHESIS_SHA256, "selection": selection, "days": days,
               "combined": combined, "holdout": "CLOSED", "execution": "DISABLED"}
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    t = combined["targets_300s"]
    lines = ["# WAVERUN V5.3 FAST V2 RANDOM 2-DAY BACKTEST", "",
             "**RANDOM-DAY HISTORICAL SANITY CHECK / NOT OOS VALIDATION**", "",
             f"- Seed: `{SEED}`", f"- Universe SHA-256: `{selection['eligible_universe_sha256']}`",
             f"- Selected dates: **{', '.join(selection['selected_dates'])}**", "",
             "## Combined", "", f"- Original V5.3 signals: **{combined['original_signals']}**",
             f"- Accepted V2 signals: **{combined['v2_signals']}**"]
    lines += [f"- ${x}/5m: **{t[str(x)]['wins']}/{t[str(x)]['n']} = {t[str(x)]['rate']:.2%}**" if t[str(x)]["n"] else f"- ${x}/5m: **0/0**" for x in TARGETS]
    absolute = combined["absolute_lift_percentage_points"]
    relative = combined["relative_lift_times"]
    lines += [f"- Comparable random SHORT base $100/5m: **{base_wins}/{base_n} = {base:.2%}**",
              f"- Absolute lift: **{'NOT ESTIMABLE (N=0)' if absolute is None else f'{absolute:.2f} pp'}**",
              f"- Relative lift: **{'NOT ESTIMABLE (N=0)' if relative is None else f'{relative:.2f}x'}**",
              "", "## Day-by-day", ""]
    for day, summary in days.items():
        value = summary["targets_300s"]["100"]
        lines.append(f"- {day}: original={summary['original_signals']}, V2={summary['v2_signals']}, $100/5m={value['wins']}/{value['n']}")
    lines += ["", "HOLDOUT: CLOSED", "EXECUTION: DISABLED", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
