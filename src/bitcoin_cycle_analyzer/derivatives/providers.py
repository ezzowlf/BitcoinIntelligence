from __future__ import annotations
import pandas as pd
import requests
from ..data_contracts import MarketDataRecord


class BinanceFuturesProvider:
    name = "binance-usdm-public"
    funding_url = "https://fapi.binance.com/fapi/v1/fundingRate"
    oi_url = "https://fapi.binance.com/futures/data/openInterestHist"

    def __init__(self, symbol: str = "BTCUSDT", timeout: int = 30):
        self.symbol, self.timeout = symbol, timeout

    @staticmethod
    def _utc(value) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")

    def funding_history(self, start=None, end=None) -> list[MarketDataRecord]:
        start_ms = int(self._utc(start or "2019-09-10").timestamp() * 1000)
        end_ms = int(self._utc(end or pd.Timestamp.now(tz="UTC")).timestamp() * 1000)
        records = []
        while start_ms <= end_ms:
            response = requests.get(self.funding_url, params={"symbol":self.symbol,"startTime":start_ms,"endTime":end_ms,"limit":1000}, timeout=self.timeout)
            response.raise_for_status(); rows = response.json()
            if not rows: break
            for row in rows:
                event = pd.to_datetime(int(row["fundingTime"]), unit="ms", utc=True)
                records.append(MarketDataRecord("funding_rate_8h", float(row["fundingRate"]), event, event, event + pd.Timedelta(milliseconds=1), self.name, f"{self.symbol}:{row['fundingTime']}", "HIGH", "initial"))
            last = int(rows[-1]["fundingTime"])
            if last < start_ms: break
            start_ms = last + 1
            if len(rows) < 1000: break
        return records

    def recent_open_interest(self, period: str = "1h", limit: int = 500) -> list[MarketDataRecord]:
        response = requests.get(self.oi_url, params={"symbol":self.symbol,"period":period,"limit":min(limit,500)}, timeout=self.timeout)
        response.raise_for_status(); records = []
        for row in response.json():
            event = pd.to_datetime(int(row["timestamp"]), unit="ms", utc=True)
            records.append(MarketDataRecord("open_interest_usd", float(row["sumOpenInterestValue"]), event, event, event + pd.Timedelta(milliseconds=1), self.name, f"{self.symbol}:{row['timestamp']}", "HIGH", "initial"))
        return records
