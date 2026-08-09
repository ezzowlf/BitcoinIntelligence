from __future__ import annotations
from typing import Protocol
from ..data_contracts import MetricObservation, unavailable
from ..data_contracts import DataStatus


class OnChainProvider(Protocol):
    name: str
    def latest(self, metric: str, as_of) -> MetricObservation: ...


class UnavailableOnChainProvider:
    name = "not configured"
    def latest(self, metric: str, as_of) -> MetricObservation:
        return unavailable(metric, self.name, "No licensed point-in-time on-chain feed configured")


class StoreOnChainProvider:
    """Adapts causality-filtered external records to the stable on-chain interface."""
    name = "external metric store"

    aliases = {"exchange_balance": "exchange_balance_btc", "exchange_inflows": "exchange_inflows_usd",
               "exchange_outflows": "exchange_outflows_usd"}

    def __init__(self, store):
        self.store = store

    def latest(self, metric: str, as_of) -> MetricObservation:
        stored_metric = self.aliases.get(metric, metric)
        frame = self.store.load(stored_metric, as_of=as_of)
        if frame.empty:
            return unavailable(metric, self.name, "No causally visible record")
        row = frame.iloc[-1]
        return MetricObservation(metric, float(row.value), row.event_timestamp, row.available_at,
                                 row.provider, DataStatus.AVAILABLE, source_url=row.source_id,
                                 note=f"quality={row.quality}; revision={row.revision}")
