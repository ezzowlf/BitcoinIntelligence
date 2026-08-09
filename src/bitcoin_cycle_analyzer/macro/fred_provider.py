from __future__ import annotations
import pandas as pd
import requests
from ..data_contracts import MarketDataRecord


class FredVintageProvider:
    name = "fred-alfred-api"
    url = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None, timeout: int = 30): self.api_key, self.timeout = api_key, timeout

    def fetch_initial_releases(self, series_id: str) -> list[MarketDataRecord]:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is required for release-time/vintage-safe macro data")
        response = requests.get(self.url, params={"series_id":series_id,"api_key":self.api_key,"file_type":"json","output_type":4,"realtime_start":"1776-07-04","realtime_end":"9999-12-31"}, timeout=self.timeout)
        response.raise_for_status(); records=[]
        for row in response.json()["observations"]:
            if row["value"] == ".": continue
            event = pd.Timestamp(row["date"], tz="UTC"); available = pd.Timestamp(row["realtime_start"], tz="UTC")
            records.append(MarketDataRecord(series_id.lower(), float(row["value"]), event, available, available, self.name, f"{series_id}:{row['date']}:{row['realtime_start']}", "HIGH", "initial"))
        return records
