from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.data_lake import ParquetDataLake
from bitcoin_cycle_analyzer.short_term.mt5_ticks import MT5TickHistory


def main() -> None:
    parser = argparse.ArgumentParser(description="Download read-only MT5 tick history into WAVERUN raw Parquet")
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--root", type=Path, default=ROOT / "runtime" / "waverun_data")
    args = parser.parse_args()
    end = args.end or args.start
    if end < args.start:
        raise SystemExit("--end must be on or after --start")

    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        history = MT5TickHistory(mt5, args.symbol)
        lake = ParquetDataLake(args.root)
        results = []
        day = args.start
        while day <= end:
            start = datetime.combine(day, time.min, UTC)
            frame = history.range(start, start + timedelta(days=1))
            audit = history.audit(frame)
            if frame.empty:
                results.append({"day": day.isoformat(), "status": "UNAVAILABLE", **audit})
            else:
                path = lake.write(frame, "vantage", args.symbol, start)
                results.append({"day": day.isoformat(), "status": "AVAILABLE", "path": str(path), **audit})
            day += timedelta(days=1)
        print(json.dumps({"execution": "DISABLED", "results": results}, indent=2))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
