from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [
    "macd_30s_cross_direction",
    "macd_30s_histogram",
    "macd_30s_histogram_slope",
    "macd_30s_histogram_acceleration",
    "price_return_30s",
    "price_acceleration_30s",
    "volatility_score",
    "flow_pressure",
    "spot_futures_agreement",
    "expansion_score",
    "price_response_efficiency",
    "flow_price_absorption",
]
TARGETS = (25, 50, 75, 100, 150, 200, 300, 500)
HORIZONS = (30, 60, 90, 120, 180, 300)
COST = 17.0


def load():
    cols = [
        "timestamp",
        "spot_price",
        *FEATURES,
        "regime",
        "spot_pressure_10s",
        "futures_pressure_10s",
        "spot_cvd_acceleration",
        "futures_cvd_acceleration",
        "macd_60s_histogram",
        "macd_180s_histogram",
        "macd_300s_histogram",
    ]
    fs = []
    for p in sorted((ROOT / "runtime" / "waverun_data" / "derived").rglob("*.parquet")):
        if "2026\\08\\16" in str(p) or "2026\\08\\17" in str(p):
            continue
        try:
            d = pd.read_parquet(p)
            d = d[[c for c in cols if c in d.columns]].copy()
            if len(d.columns) < 3:
                continue
        except (OSError, ValueError):
            continue
        d["timestamp"] = pd.to_datetime(d.timestamp, utc=True)
        d["period"] = (
            "Q1_2025"
            if "q1_2025" in str(p)
            else ("JUL_2026" if "2026\\07" in str(p) else "OTHER")
        )
        fs.append(d)
    return (
        pd.concat(fs, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    )


def signal_mask(f, q=0.80):
    q1 = f[f.period == "Q1_2025"]
    return (
        (f.macd_30s_cross_direction.fillna(0) < 0)
        & (f.macd_30s_histogram.fillna(0) < 0)
        & (f.macd_30s_histogram_slope.fillna(0) < 0)
        & (f.macd_30s_histogram_acceleration.fillna(0) < 0)
        & (
            f.macd_30s_histogram_acceleration.abs()
            >= q1.macd_30s_histogram_acceleration.abs().quantile(q)
        )
        & (f.macd_30s_histogram.abs() >= q1.macd_30s_histogram.abs().quantile(q))
    )


def decluster(f, m):
    ix = np.flatnonzero(m.to_numpy())
    t = f.timestamp.to_numpy(dtype="datetime64[s]")
    keep = []
    for i in ix:
        if not keep or t[i] - t[keep[-1]] >= np.timedelta64(180, "s"):
            keep.append(int(i))
    return keep


def pct(a, q):
    a = np.asarray([x for x in a if x is not None and np.isfinite(x)], float)
    return None if not len(a) else float(np.percentile(a, q))


def main():
    f = load()
    ix = decluster(f, signal_mask(f))
    p = f.spot_price.to_numpy(float)
    f.timestamp.to_numpy(dtype="datetime64[s]")
    rows = []
    for i in ix:
        if i + 60 >= len(f):
            continue
        entry = p[i] - COST / 2
        fut60 = p[i + 1 : i + 721]
        fut = p[i + 1 : i + 61]
        fav = entry - fut
        p[i + 1 : i + 61] - entry
        r = {
            "candidate_index": i,
            "timestamp": f.timestamp.iloc[i].isoformat(),
            "direction": "SHORT",
            "group": None,
            "path": [],
            "sampled_prices": {},
        }
        fav60 = entry - fut60
        mfe60 = float(np.nanmax(fav60))
        mae60 = float(np.nanmin(fav60))
        r["mfe_60m_proxy"] = mfe60
        r["mae_60m_proxy"] = mae60
        r["group"] = (
            "STRONG_WINNER"
            if mfe60 >= 500
            else "MODERATE_WINNER"
            if mfe60 >= 300
            else "LATE_WINNER"
            if mfe60 >= 100
            else "ABSORBED"
            if mae60 < -100
            else "FAILED_CONTINUATION"
        )
        for s in (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300):
            j = min(i + s // 5, len(p) - 1)
            r["sampled_prices"][f"{s}s"] = None if j <= i else float(p[j])
        for h in HORIZONS:
            x = p[i + 1 : min(i + 1 + h // 5, len(p))]
            z = entry - x
            r[f"mfe_{h}s"] = None if not len(z) else float(np.max(z))
            r[f"mae_{h}s"] = None if not len(z) else float(np.min(z))
            for target in TARGETS:
                hit = np.flatnonzero(z >= target)
                r[f"reach_{target}_{h}s"] = bool(len(hit))
        for target in (0,) + TARGETS:
            hit = np.flatnonzero(fav >= target)
            r[f"time_to_{'first_positive' if target == 0 else target}"] = (
                None if not len(hit) else float((hit[0] + 1) * 5)
            )
            hit = np.flatnonzero(fav >= target)
            r[f"mae_before_{target if target else 'positive'}"] = (
                None if not len(hit) else float(np.min(fav[: hit[0] + 1]))
            )
        for target in (25, 50, 75, 100):
            fh = np.flatnonzero(fav >= target)
            ah = np.flatnonzero(fav <= -target)
            r[f"path_order_{target}"] = (
                "NO_RELEVANT_MOVE"
                if not len(fh) and not len(ah)
                else "FAVORABLE_FIRST"
                if len(fh) and (not len(ah) or fh[0] < ah[0])
                else "ADVERSE_FIRST"
                if len(ah) and (not len(fh) or ah[0] < fh[0])
                else "MIXED"
            )
        r["path_shape"] = (
            "NO_MOVE"
            if np.max(fav) < 25 and np.min(fav) > -25
            else "WRONG_DIRECTION"
            if np.min(fav) <= -100 and np.max(fav) < 50
            else "IMMEDIATE_CONTINUATION"
            if next((r[f"reach_100_{h}s"] for h in (30, 60, 90, 120, 180, 300)), False)
            and r["path_order_100"] == "FAVORABLE_FIRST"
            else "PULLBACK_THEN_CONTINUATION"
            if r["reach_100_300s"] and r["path_order_100"] == "ADVERSE_FIRST"
            else "SPIKE_THEN_REVERSAL"
            if np.max(fav) >= 100 and r["mfe_300s"] < 50
            else "CHOP"
        )
        r["clean_fast_win"] = bool(r["reach_100_300s"])
        r["early_but_correct"] = bool(
            r["clean_fast_win"] and r["path_order_100"] == "ADVERSE_FIRST"
        )
        rows.append(r)
    df = pd.DataFrame(rows)
    winners = df[df.group.isin(["STRONG_WINNER", "MODERATE_WINNER", "LATE_WINNER"])]
    cum = {
        str(t): {
            "n": int((df.mfe_300s >= t).sum()),
            "pct": float((df.mfe_300s >= t).mean() * 100),
        }
        for t in (100, 150, 200, 300, 400, 500)
    }
    reach = {
        str(t): {
            str(h): {
                "n": int(df[f"reach_{t}_{h}s"].sum()),
                "pct": float(df[f"reach_{t}_{h}s"].mean() * 100),
            }
            for h in HORIZONS
        }
        for t in TARGETS
    }

    def quant(col, sub=winners):
        return {
            "p50": pct(sub[col], 50),
            "p75": pct(sub[col], 75),
            "p90": pct(sub[col], 90),
            "max": pct(sub[col], 100),
        }

    payload = {
        "execution": "DISABLED",
        "holdout": "CLOSED",
        "direction": "SHORT",
        "candidate_count": len(df),
        "group_counts": df.group.value_counts().to_dict(),
        "cumulative_60m": cum,
        "reach": reach,
        "cases": rows,
        "winner_mae_before_100": quant("mae_before_100"),
        "winner_time_to_100": quant("time_to_100"),
        "winner_time_to_first_positive": quant("time_to_first_positive"),
        "path_shapes": df.path_shape.value_counts().to_dict(),
        "path_order": {
            str(t): df[f"path_order_{t}"].value_counts().to_dict()
            for t in (25, 50, 75, 100)
        },
        "fast_conversion": {
            "old_60m_winners": len(winners),
            "fast_300s": int(winners.reach_100_300s.sum()),
            "rate": float(winners.reach_100_300s.mean()),
        },
        "base_rate_note": "Comparable SHORT 5m base rate requires non-candidate population; not inferred from selected 47.",
    }
    out = ROOT / "data" / "reports" / "waverun_v5_3_fast_300s_autopsy"
    out.mkdir(parents=True, exist_ok=True)
    (out / "fast_300s_autopsy.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    lines = (
        [
            "# WAVERUN V5.3 FAST 300S AUTOPSY",
            "",
            f"- Frozen candidates: **{len(df)}**",
            "- Execution: **DISABLED**",
            "- Holdout: **CLOSED**",
            "",
            "## Cumulative 60m magnitude",
            "| Target | N | % |",
            "|---:|---:|---:|",
        ]
        + [f"| >= ${k} | {v['n']} | {v['pct']:.2f}% |" for k, v in cum.items()]
        + [
            "",
            "## Fast target reach",
            "| Target | 30s | 60s | 90s | 120s | 180s | 300s |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
        + [
            f"| ${t} | "
            + " | ".join(
                f"{reach[str(t)][str(h)]['n']}/{len(df)} ({reach[str(t)][str(h)]['pct']:.1f}%)"
                for h in HORIZONS
            )
            + " |"
            for t in TARGETS
        ]
        + [
            "",
            "## Interpretation",
            "This is descriptive forensic evidence only; no thresholds, model, or strategy was changed.",
        ]
    )
    (ROOT / "WAVERUN_V5_3_FAST_300S_AUTOPSY.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
