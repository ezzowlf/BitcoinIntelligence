from __future__ import annotations

from .contracts import Costs


def quality_gate(fused: dict, features: dict, costs: Costs | None = None, max_age_seconds: float = 15.0, data_age_seconds: float | None = None) -> dict:
    """Fail closed when edge, data quality, or latency is insufficient."""
    costs = costs or Costs()
    gross = abs(float(fused.get("expected_return", 0.0)))
    net = gross - costs.round_trip
    stale = data_age_seconds is not None and data_age_seconds > max_age_seconds
    directional_edge = max(float(fused.get("p_up", .5)), float(fused.get("p_down", .5))) - .5
    eligible = bool(fused.get("available")) and not stale and directional_edge >= .08 and net > 0 and float(fused.get("confidence", 0)) >= .45
    return {"status": "EDGE" if eligible else "NO_EDGE", "gross_expected_return": gross, "net_expected_return": net, "stale": stale, "reason": "DATA_STALE" if stale else "INSUFFICIENT_EDGE" if not eligible else "COST_ADJUSTED_EDGE"}
