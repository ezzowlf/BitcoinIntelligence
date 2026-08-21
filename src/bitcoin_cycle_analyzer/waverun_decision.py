"""Fast, explainable WAVERUN market-decision synthesis.

The decision layer consumes already computed causal features only.  It is a
deterministic reducer, not an LLM and not an execution engine.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from .waverun_v5 import EXECUTION, fingerprint

GROUPS = frozenset({"PRICE", "FLOW", "L2", "DERIVATIVES", "CROSS_EXCHANGE", "STRUCTURE", "REGIME", "EVENT"})
DECISIONS = ("BLOCKED", "WATCH", "ARMED", "APPROVED", "INVALIDATED")


@dataclass(frozen=True)
class DecisionSignal:
    group: str
    name: str
    direction: str  # BULLISH, BEARISH, or NEUTRAL
    strength: float  # 0..1, computed upstream from causal features
    explanation: str
    available: bool = True

    def __post_init__(self) -> None:
        if self.group not in GROUPS:
            raise ValueError(f"unknown evidence group: {self.group}")
        if self.direction not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            raise ValueError("direction must be BULLISH, BEARISH, or NEUTRAL")
        if not 0 <= self.strength <= 1:
            raise ValueError("strength must be between 0 and 1")


@dataclass(frozen=True)
class DecisionInput:
    symbol: str
    timestamp: str
    signals: tuple[DecisionSignal, ...]
    data_quality: float
    freshness_seconds: float
    timing: str  # EARLY, MATURE, LATE, UNKNOWN
    regime: str
    expected_edge_after_cost: float | None
    calibrated: bool
    model_version: str = "deterministic-v5-decision-1"


@dataclass(frozen=True)
class MarketDecision:
    symbol: str
    timestamp: str
    state: str
    decision: str
    direction: str
    confidence: float
    directional_edge: float
    signal_quality: float
    timing_quality: float
    data_quality: float
    regime: str
    supporting_factors: tuple[str, ...] = ()
    opposing_factors: tuple[str, ...] = ()
    strongest_signal: str = ""
    biggest_risk: str = ""
    invalidation_reason: str = ""
    contradictions: tuple[str, ...] = ()
    data_freshness_seconds: float = 0.0
    execution: str = EXECUTION
    record_id: str = ""

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record["record_id"] = self.record_id or fingerprint(record)
        return record


def _sign(signal: DecisionSignal) -> float:
    return signal.strength if signal.direction == "BULLISH" else -signal.strength if signal.direction == "BEARISH" else 0.0


def _contradictions(signals: Iterable[DecisionSignal]) -> list[str]:
    by_group: dict[str, list[DecisionSignal]] = {}
    for signal in signals:
        if signal.available:
            by_group.setdefault(signal.group, []).append(signal)
    found: list[str] = []
    for group, rows in by_group.items():
        bullish = max((_sign(row) for row in rows), default=0)
        bearish = min((_sign(row) for row in rows), default=0)
        if bullish > 0.55 and bearish < -0.55:
            found.append(f"{group}: bullish and bearish evidence conflict")
    all_scores = [_sign(signal) for signal in signals if signal.available]
    if len(by_group) >= 2 and max(all_scores, default=0) > 0.65 and min(all_scores, default=0) < -0.65:
        found.append("cross-group directional conflict: independent evidence disagrees")
    return found


def fast_decision(inp: DecisionInput) -> MarketDecision:
    """Return a fail-closed decision from precomputed causal evidence."""
    available = [s for s in inp.signals if s.available and s.direction != "NEUTRAL"]
    missing = sorted(GROUPS.intersection({"L2", "FLOW", "DERIVATIVES", "CROSS_EXCHANGE"}) - {s.group for s in available})
    contradictions = _contradictions(inp.signals)
    scores = [_sign(s) for s in available]
    edge = sum(scores) / len(scores) if scores else 0.0
    direction = "LONG" if edge > 0 else "SHORT" if edge < 0 else "NONE"
    confidence = min(1.0, abs(edge) * min(1.0, len({s.group for s in available}) / 4))
    quality = min(1.0, len({s.group for s in available}) / 4) * (1 - min(1.0, len(contradictions) * .25))
    timing_quality = {"EARLY": 1.0, "MATURE": .7, "LATE": .2, "UNKNOWN": 0.0}.get(inp.timing, 0.0)
    hard_missing = len(missing) >= 2
    hard_block = inp.data_quality < .8 or inp.freshness_seconds > 5 or bool(contradictions) or inp.timing in {"LATE", "UNKNOWN"}
    positive_cost_edge = inp.expected_edge_after_cost is not None and inp.expected_edge_after_cost > 0
    if not available or hard_missing or inp.data_quality <= 0:
        decision, state = "BLOCKED", "NO_TRADE"
    elif hard_block:
        decision, state = "BLOCKED", "CONFLICTED" if contradictions else "NO_TRADE"
    elif abs(edge) < .25 or len({s.group for s in available}) < 2:
        decision, state = "WATCH", "NEUTRAL"
    elif not positive_cost_edge or not inp.calibrated:
        decision, state = "ARMED", "BULLISH" if direction == "LONG" else "BEARISH"
    else:
        decision, state = "APPROVED", "BULLISH" if direction == "LONG" else "BEARISH"
    supporting = tuple(s.explanation for s in available if (direction == "LONG" and _sign(s) > 0) or (direction == "SHORT" and _sign(s) < 0))
    opposing = tuple(s.explanation for s in available if s.explanation not in supporting)
    strongest = max(available, key=lambda s: s.strength).explanation if available else ""
    invalidation = contradictions[0] if contradictions else ("insufficient calibrated edge after costs" if decision != "APPROVED" else "")
    return MarketDecision(inp.symbol, inp.timestamp, state, decision, direction, confidence, edge, quality, timing_quality,
                          inp.data_quality, inp.regime, supporting, opposing, strongest,
                          opposing[0] if opposing else "", invalidation, tuple(contradictions), inp.freshness_seconds)
