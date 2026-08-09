from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
import requests
from ..data_contracts import MarketDataRecord

COMMUNITY_METRICS = {"CapMVRVCur":"mvrv", "FlowInExUSD":"exchange_inflows_usd", "FlowOutExUSD":"exchange_outflows_usd", "SplyExNtv":"exchange_balance_btc"}


class CoinMetricsCommunityProvider:
    name = "coinmetrics-community-v4"
    url = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"

    def __init__(self, timeout: int = 60): self.timeout = timeout

    def fetch(self, start="2011-08-18", end=None) -> list[MarketDataRecord]:
        params = {"assets":"btc", "metrics":",".join(COMMUNITY_METRICS), "frequency":"1d", "start_time":start, "end_time":end or pd.Timestamp.now(tz="UTC").date().isoformat(), "page_size":10000, "paging_from":"start"}
        response = requests.get(self.url, params=params, timeout=self.timeout); response.raise_for_status()
        payload = response.json(); rows = payload.get("data", []); records = []
        retrieved = pd.Timestamp.now(tz="UTC")
        for row in rows:
            event = pd.Timestamp(row["time"])
            for source_metric, metric in COMMUNITY_METRICS.items():
                if row.get(source_metric) is None: continue
                status_time = row.get(f"{source_metric}-status-time")
                # Metrics without a historical status time are live/research only:
                # their past value was not proven available at the event date.
                available = pd.Timestamp(status_time) if status_time else retrieved
                revision = row.get(f"{source_metric}-status", "current-snapshot")
                quality = "HIGH" if status_time and revision == "reviewed" else "MEDIUM" if status_time else "LOW"
                records.append(MarketDataRecord(metric, float(row[source_metric]), event, available, available, self.name, f"btc:{source_metric}:{row['time']}", quality, revision))
        return records
