from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def inspect(path: Path, source: str, market: str, instrument: str) -> dict:
    row = {"source": source, "market": market, "instrument": instrument, "path": str(path), "exists": path.exists(), "resolution": "UNKNOWN", "event_count": 0, "timestamp_precision": None, "start": None, "end": None, "bid_ask_available": False, "trades_available": False, "orderbook_available": False, "liquidations_available": False, "l2_status": "HISTORICAL_L2_UNAVAILABLE", "availability_timestamp": None, "gaps": None, "quality": "UNAVAILABLE", "research_usability": "NO_DATA"}
    if not path.exists():
        return row
    try:
        frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path, nrows=100_000)
    except (OSError, ValueError, ImportError) as exc:
        row.update({"quality": "ERROR", "research_usability": "UNAVAILABLE", "error": type(exc).__name__})
        return row
    row["event_count"] = len(frame); row["quality"] = "OBSERVED" if len(frame) else "EMPTY"
    time_col = next((c for c in ("timestamp", "time_msc", "time", "exchange_event_time", "exchange_timestamp") if c in frame), None)
    if time_col:
        values = pd.to_datetime(frame[time_col], unit="ms" if time_col == "time_msc" else None, utc=True, errors="coerce")
        row["start"] = None if values.dropna().empty else values.min().isoformat(); row["end"] = None if values.dropna().empty else values.max().isoformat()
        if time_col == "time_msc":
            row["timestamp_precision"] = "milliseconds"
        elif "binance_spot" in source:
            row["timestamp_precision"] = "microseconds (source archive)"
        elif "binance" in source:
            row["timestamp_precision"] = "milliseconds (source archive)"
        else:
            row["timestamp_precision"] = "exchange_timestamp"
        if len(values.dropna()) > 1:
            row["gaps"] = int(values.sort_values().diff().dt.total_seconds().gt(60).sum())
    columns = set(frame.columns)
    row["bid_ask_available"] = {"bid", "ask"}.issubset(columns); row["trades_available"] = {"price", "quantity"}.issubset(columns) or "last" in columns
    row["orderbook_available"] = any(c in columns for c in ("bid_depth", "ask_depth", "bids", "asks")); row["liquidations_available"] = "liquidation" in " ".join(columns).lower()
    row["resolution"] = "event-level" if "event_type" in columns else "tick-level" if source == "vantage" else row["resolution"]
    row["market"] = market if market != "unknown" else "broker" if source == "vantage" else "spot" if "spot" in source else "futures" if source in {"binance_um", "binance_futures"} else market
    row["research_usability"] = "USABLE_WITH_AUDIT" if row["event_count"] and time_col else "INSUFFICIENT_TIMESTAMP"
    return row


def build_report(root: Path) -> dict:
    data = root / "runtime" / "waverun_data"
    rows = []
    for path in sorted(data.rglob("*.parquet")) if data.exists() else []:
        relative = path.relative_to(data).parts
        source = relative[1] if len(relative) > 1 else "unknown"
        if source not in {"vantage", "binance_spot", "binance_futures"}:
            continue
        row = inspect(path, source, "unknown", relative[2] if len(relative) > 2 else "unknown")
        row["path"] = str(path.relative_to(root))
        rows.append(row)
    existing_sources = {row["source"] for row in rows}
    for path, source, market, instrument in ((data / "vantage" / "BTCUSD", "vantage", "broker", "BTCUSD"), (data / "binance_spot", "binance_spot", "spot", "BTCUSDT"), (data / "binance_futures", "binance_futures", "futures", "BTCUSDT")):
        if source in existing_sources:
            continue
        row = inspect(path, source, market, instrument)
        row["path"] = str(path.relative_to(root))
        rows.append(row)
    return {"generated_at": datetime.now(UTC).isoformat(), "execution": "DISABLED", "rows": rows, "notes": ["No provider credentials or paid datasets were accessed.", "Missing data remains unavailable; this report does not infer history."]}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1]); parser.add_argument("--output", type=Path)
    args = parser.parse_args(); output = args.output or args.root / "runtime" / "waverun_data_inventory.json"; output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(build_report(args.root), indent=2))
    print(output)


if __name__ == "__main__":
    main()
