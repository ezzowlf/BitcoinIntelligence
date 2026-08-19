from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def inspect(path: Path, source: str, market: str, instrument: str) -> dict:
    row = {"source": source, "market": market, "instrument": instrument, "path": str(path), "exists": path.exists(), "resolution": "UNKNOWN", "event_count": 0, "timestamp_precision": None, "start": None, "end": None, "bid_ask_available": False, "trades_available": False, "orderbook_available": False, "liquidations_available": False, "availability_timestamp": None, "gaps": None, "quality": "UNAVAILABLE", "research_usability": "NO_DATA"}
    if not path.exists():
        return row
    try:
        frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path, nrows=100_000)
    except Exception as exc:
        row.update({"quality": "ERROR", "research_usability": "UNAVAILABLE", "error": type(exc).__name__})
        return row
    row["event_count"] = int(len(frame)); row["quality"] = "OBSERVED" if len(frame) else "EMPTY"
    time_col = next((c for c in ("timestamp", "time_msc", "time", "exchange_event_time") if c in frame), None)
    if time_col:
        values = pd.to_datetime(frame[time_col], unit="ms" if time_col == "time_msc" else None, utc=True, errors="coerce")
        row["start"] = None if values.dropna().empty else values.min().isoformat(); row["end"] = None if values.dropna().empty else values.max().isoformat()
        row["timestamp_precision"] = "milliseconds" if time_col == "time_msc" else "unknown"
    columns = set(frame.columns)
    row["bid_ask_available"] = {"bid", "ask"}.issubset(columns); row["trades_available"] = {"price", "quantity"}.issubset(columns) or "last" in columns
    row["orderbook_available"] = any(c in columns for c in ("bid_depth", "ask_depth", "bids", "asks")); row["liquidations_available"] = "liquidation" in " ".join(columns).lower()
    row["research_usability"] = "USABLE_WITH_AUDIT" if row["event_count"] and time_col else "INSUFFICIENT_TIMESTAMP"
    return row


def build_report(root: Path) -> dict:
    data = root / "runtime" / "waverun_data"
    rows = []
    for path in sorted(data.rglob("*.parquet")) if data.exists() else []:
        relative = path.relative_to(data).parts
        row = inspect(path, relative[1] if len(relative) > 1 else "unknown", "unknown", relative[2] if len(relative) > 2 else "unknown")
        row["path"] = str(path.relative_to(root))
        rows.append(row)
    for path, source, market, instrument in ((data / "vantage" / "BTCUSD", "vantage", "broker", "BTCUSD"), (data / "binance_spot", "binance", "spot", "BTCUSDT"), (data / "binance_futures", "binance", "futures", "BTCUSDT")):
        row = inspect(path, source, market, instrument)
        row["path"] = str(path.relative_to(root))
        rows.append(row)
    return {"generated_at": datetime.now(UTC).isoformat(), "execution": "DISABLED", "rows": rows, "notes": ["No provider credentials or paid datasets were accessed.", "Missing data remains unavailable; this report does not infer history."]}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1]); parser.add_argument("--output", type=Path)
    args = parser.parse_args(); output = args.output or args.root / "runtime" / "waverun_data_inventory.json"; output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(build_report(args.root), indent=2), encoding="utf-8"); print(output)


if __name__ == "__main__":
    main()
