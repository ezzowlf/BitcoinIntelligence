from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.binance_history import BinanceVisionHistory
from bitcoin_cycle_analyzer.short_term.data_lake import ParquetDataLake


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official Binance Vision trade archives into WAVERUN raw Parquet")
    parser.add_argument("--market", choices=("spot", "um"), default="spot")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--data-type", choices=("aggTrades", "trades"), default="aggTrades")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--root", type=Path, default=ROOT / "runtime" / "waverun_data")
    args = parser.parse_args()
    end = args.end or args.start
    if end < args.start:
        raise SystemExit("--end must be on or after --start")
    downloader = BinanceVisionHistory(ParquetDataLake(args.root))
    results = []
    day = args.start
    while day <= end:
        result = downloader.download_day(args.market, args.symbol, args.data_type, day)
        results.append({"day": day.isoformat(), **result})
        day += timedelta(days=1)
    print(json.dumps({"execution": "DISABLED", "results": results}, indent=2))


if __name__ == "__main__":
    main()
