from __future__ import annotations

from datetime import UTC, date, datetime
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import requests

try:
    import truststore
except ImportError:  # pragma: no cover - optional outside Windows
    truststore = None

if truststore is not None:
    truststore.inject_into_ssl()

from .data_lake import ParquetDataLake


class BinanceVisionHistory:
    """Downloader for the official public Binance Vision daily archives."""

    BASE = "https://data.binance.vision/data"

    def __init__(self, lake: ParquetDataLake, timeout: int = 60):
        self.lake, self.timeout = lake, timeout

    @classmethod
    def url(cls, market: str, symbol: str, data_type: str, day: date) -> str:
        if market == "spot":
            prefix = "spot"
        elif market in {"um", "futures"}:
            market = "um"
            prefix = "futures/um"
        else:
            raise ValueError("market must be spot or um")
        if data_type not in {"aggTrades", "trades", "klines"}:
            raise ValueError("unsupported Binance Vision data type")
        suffix = f"{symbol}-{data_type}-{day:%Y-%m-%d}.zip"
        return f"{cls.BASE}/{prefix}/daily/{data_type}/{symbol}/{suffix}"

    @staticmethod
    def parse_csv(content: bytes, market: str, data_type: str, downloaded_at: datetime | None = None) -> pd.DataFrame:
        with ZipFile(BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if len(names) != 1:
                raise ValueError("Binance Vision archive must contain exactly one data file")
            with archive.open(names[0]) as handle:
                if data_type == "aggTrades":
                    columns = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "timestamp", "buyer_is_maker", "best_match"]
                    frame = pd.read_csv(handle, header=None, names=columns, low_memory=False)
                elif data_type == "trades":
                    columns = ["trade_id", "price", "quantity", "quote_quantity", "timestamp", "buyer_is_maker", "best_match"]
                    frame = pd.read_csv(handle, header=None, names=columns)
                else:
                    frame = pd.read_csv(handle, header=None)
        if data_type == "klines":
            return frame
        frame = frame[pd.to_numeric(frame.iloc[:, 0], errors="coerce").notna()].copy()
        frame["price"] = pd.to_numeric(frame["price"], errors="raise")
        frame["quantity"] = pd.to_numeric(frame["quantity"], errors="raise")
        frame["buyer_is_maker"] = frame["buyer_is_maker"].astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False})
        if frame["buyer_is_maker"].isna().any():
            raise ValueError("invalid buyer_is_maker value")
        timestamps = pd.to_numeric(frame.pop("timestamp"), errors="raise")
        unit = "us" if float(timestamps.max()) >= 10**14 else "ms"
        frame["exchange_timestamp"] = pd.to_datetime(timestamps, unit=unit, utc=True)
        frame["source"] = f"BINANCE_{market.upper()}"
        frame["market"] = market
        frame["event_type"] = "AGG_TRADE" if data_type == "aggTrades" else "TRADE"
        frame["downloaded_at"] = downloaded_at or datetime.now(UTC)
        frame = frame.sort_values(["exchange_timestamp", frame.columns[0]]).reset_index(drop=True)
        return frame

    def download_day(self, market: str, symbol: str, data_type: str, day: date, *, session: requests.Session | None = None) -> dict:
        url = self.url(market, symbol, data_type, day)
        client = session or requests.Session()
        response = client.get(url, timeout=self.timeout)
        if response.status_code == 404:
            return {"status": "UNAVAILABLE", "url": url, "reason": "ARCHIVE_NOT_FOUND"}
        response.raise_for_status()
        frame = self.parse_csv(response.content, market, data_type)
        if frame.empty:
            return {"status": "EMPTY", "url": url, "rows": 0}
        instrument = symbol.upper()
        source_name = "binance_spot" if market == "spot" else "binance_futures"
        path = self.lake.partition_path(source_name, instrument, day, derived=False)
        existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        combined = pd.concat([existing, frame], ignore_index=True)
        keys = [key for key in ("agg_trade_id", "trade_id", "exchange_timestamp", "price", "quantity") if key in combined]
        combined = combined.drop_duplicates(subset=keys, keep="last").sort_values("exchange_timestamp").reset_index(drop=True)
        self.lake.write(combined, source_name, instrument, datetime(day.year, day.month, day.day, tzinfo=UTC))
        return {"status": "AVAILABLE", "url": url, "rows": len(combined), "start": frame.exchange_timestamp.min().isoformat(), "end": frame.exchange_timestamp.max().isoformat(), "l2_status": "HISTORICAL_L2_UNAVAILABLE"}
