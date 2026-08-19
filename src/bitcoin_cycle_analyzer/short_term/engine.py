from __future__ import annotations

from datetime import UTC, datetime

from .contracts import HORIZONS_SECONDS, Costs, Forecast, MarketTick
from .features import FeatureEngine
from .fusion import fuse
from .predictors import order_flow, orderbook, price_action
from .quality_gate import quality_gate
from .state_machine import StateMachine


class ShortTermEngine:
    """Common multi-horizon pipeline for LIVE, REPLAY, and MOCK-labelled input."""

    def __init__(self, costs: Costs | None = None, stale_after_seconds: float = 15.0):
        self.features = FeatureEngine()
        self.costs = costs or Costs()
        self.stale_after_seconds = stale_after_seconds
        self.state_machine = StateMachine()

    def process(self, tick: MarketTick, mode: str = "LIVE", now: datetime | None = None) -> list[Forecast]:
        now = now or datetime.now(UTC)
        feature_values = self.features.update(tick)
        outputs = []
        decisions = []
        for horizon in HORIZONS_SECONDS:
            models = [price_action(feature_values, horizon), order_flow(feature_values, horizon), orderbook(feature_values, horizon)]
            fused = fuse(models, horizon)
            quality = quality_gate(fused, feature_values, self.costs, self.stale_after_seconds, tick.age_seconds(now))
            decisions.append((fused, quality))
        # The state machine is a single setup state, driven by the production
        # focus horizon (5m), while the forecast matrix remains multi-horizon.
        focus = HORIZONS_SECONDS.index(300)
        _, focus_quality = decisions[focus]
        focus_fused, _ = decisions[focus]
        _, state = self.state_machine.update(focus_quality, focus_fused, now)
        for horizon, (fused, quality) in zip(HORIZONS_SECONDS, decisions):
            direction = 1 if fused["p_up"] >= fused["p_down"] else -1
            expected_move = abs(float(fused["expected_return"]))
            reasons = fused["reasons"] + (("DATA_STALE",) if quality["stale"] else ())
            outputs.append(Forecast(now, horizon, fused["p_up"], fused["p_down"], fused["p_no_move"], fused["expected_return"], expected_move * direction, fused["confidence"], fused["uncertainty"], state, quality["status"], fused["agreement"], reasons, tick.latencies(now), mode, "DISABLED"))
        return outputs
