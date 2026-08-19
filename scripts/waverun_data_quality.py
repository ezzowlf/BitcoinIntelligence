from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "runtime" / "waverun_data" / "raw"
START, END = date(2026, 7, 20), date(2026, 8, 18)


def path(source: str, symbol: str, day: date) -> Path:
    return DATA / source / symbol / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def audit(source: str, frame: pd.DataFrame) -> dict:
    timestamp = "timestamp" if source == "vantage" else "exchange_timestamp"
    ts = pd.to_datetime(frame[timestamp], utc=True)
    deltas = ts.diff().dt.total_seconds()
    result = {
        "rows": len(frame), "start": ts.min().isoformat(), "end": ts.max().isoformat(),
        "duplicates": int(frame.duplicated().sum()), "backwards_timestamps": int((deltas < 0).sum()),
        "gaps_over_60s": int((deltas > 60).sum()),
        "timestamp_resolution": "microseconds" if ts.dt.microsecond.mod(1000).ne(0).any() else "milliseconds",
    }
    if source == "vantage":
        spread = frame.ask - frame.bid
        result.update({"zero_quotes": int(((frame.bid <= 0) | (frame.ask <= 0)).sum()),
                       "crossed_quotes": int((frame.ask < frame.bid).sum()),
                       "spread_median": float(spread.median()), "spread_p95": float(spread.quantile(0.95)),
                       "spread_max": float(spread.max())})
    else:
        result.update({"invalid_price": int((frame.price <= 0).sum()), "invalid_quantity": int((frame.quantity <= 0).sum())})
    result["quality"] = "FLAGGED" if any(result[key] for key in ("duplicates", "backwards_timestamps", "gaps_over_60s")) else "GOOD"
    return result


def main() -> None:
    sources = {"vantage": "BTCUSD", "binance_spot": "BTCUSDT", "binance_futures": "BTCUSDT"}
    report = {"requested_days": 0, "vantage_available_days": 0, "binance_spot_days": 0,
              "binance_futures_days": 0, "complete_overlap_days": 0, "totals": {}, "days": [],
              "exploratory_days": ["2026-08-18"], "execution": "DISABLED"}
    totals = {source: 0 for source in sources}
    day = START
    while day <= END:
        report["requested_days"] += 1
        row = {"day": day.isoformat(), "sources": {}}
        available = []
        for source, symbol in sources.items():
            partition = path(source, symbol, day)
            if not partition.exists():
                row["sources"][source] = {"status": "UNAVAILABLE"}
                available.append(False)
                continue
            frame = pd.read_parquet(partition)
            quality = audit(source, frame)
            row["sources"][source] = {"status": "AVAILABLE", **quality}
            totals[source] += len(frame)
            report[f"{source}_days" if source != "vantage" else "vantage_available_days"] += 1
            available.append(True)
        row["complete_overlap"] = all(available)
        report["complete_overlap_days"] += int(row["complete_overlap"])
        report["days"].append(row)
        day += timedelta(days=1)
    report["totals"] = {"vantage_ticks": totals["vantage"], "spot_events": totals["binance_spot"], "futures_events": totals["binance_futures"]}
    report["split"] = {"train": ["2026-07-20", "2026-08-06"], "validation": ["2026-08-07", "2026-08-11"],
                       "walk_forward": ["2026-08-12", "2026-08-15"], "final_holdout": ["2026-08-16", "2026-08-17"],
                       "excluded_exploratory": ["2026-08-18"]}
    output = ROOT / "data" / "reports" / "waverun_30d_data_quality.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("requested_days", "vantage_available_days", "binance_spot_days", "binance_futures_days", "complete_overlap_days", "totals", "split", "execution")}, indent=2))


if __name__ == "__main__":
    main()
