from __future__ import annotations
from typing import Protocol
from ..data_contracts import MetricObservation, unavailable


class OnChainProvider(Protocol):
    name: str
    def latest(self, metric: str, as_of) -> MetricObservation: ...


class UnavailableOnChainProvider:
    name = "not configured"
    def latest(self, metric: str, as_of) -> MetricObservation:
        return unavailable(metric, self.name, "No licensed point-in-time on-chain feed configured")

