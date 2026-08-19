from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np

FINAL_HOLDOUT = frozenset({date(2026, 8, 16), date(2026, 8, 17)})
EXPLORATORY = frozenset({date(2026, 8, 18)})
CONFIDENCE_COVERAGE = (0.50, 0.25, 0.10, 0.05, 0.02, 0.01)
PROBABILITY_THRESHOLDS = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


class HoldoutLockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateFreeze:
    model: str
    horizon_seconds: int
    feature_groups: tuple[str, ...]
    parameters: dict[str, Any]
    threshold: float
    cost_model: dict[str, Any]
    validation_summary: dict[str, Any]
    frozen_at: str
    execution: str = "DISABLED"

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_manifest(self) -> dict[str, Any]:
        return {**asdict(self), "candidate_frozen": True, "fingerprint": self.fingerprint()}


def assert_days_allowed(days: list[date], freeze_manifest: dict[str, Any] | None = None) -> None:
    requested_holdout = FINAL_HOLDOUT.intersection(days)
    if requested_holdout and not (freeze_manifest and freeze_manifest.get("candidate_frozen") is True):
        raise HoldoutLockedError(f"final holdout is locked: {sorted(day.isoformat() for day in requested_holdout)}")


def wilson_interval(wins: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or wins < 0 or wins > total:
        raise ValueError("wins/total are invalid")
    p = wins / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def selective_metrics(confidence: np.ndarray, correct: np.ndarray, net_returns: np.ndarray) -> list[dict[str, Any]]:
    if not (len(confidence) == len(correct) == len(net_returns)):
        raise ValueError("metric arrays must have equal length")
    finite = np.isfinite(confidence) & np.isfinite(net_returns)
    confidence, correct, net_returns = confidence[finite], correct[finite].astype(bool), net_returns[finite]
    order = np.argsort(-confidence, kind="stable")
    output = []
    for coverage in CONFIDENCE_COVERAGE:
        count = max(1, math.ceil(len(order) * coverage)) if len(order) else 0
        selected = order[:count]
        wins = int(correct[selected].sum()) if count else 0
        low, high = wilson_interval(wins, count) if count else (None, None)
        output.append({"coverage": coverage, "signals": count, "wins": wins, "losses": count - wins,
                       "precision": wins / count if count else None, "precision_ci95": [low, high],
                       "net_ev": float(net_returns[selected].mean()) if count else None})
    return output


class ExperimentRegistry:
    """Append-only JSONL registry; entries are immutable facts about attempted variants."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, payload: dict[str, Any]) -> str:
        entry = {"registered_at": datetime.now(UTC).isoformat(), "execution": "DISABLED", **payload}
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["experiment_id"] = hashlib.sha256(canonical.encode()).hexdigest()[:20]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry["experiment_id"]

    def counts(self) -> dict[str, int]:
        if not self.path.exists():
            return {"experiments": 0, "models": 0, "feature_sets": 0, "thresholds": 0, "strategy_candidates": 0}
        entries = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
        thresholds = {threshold for row in entries for threshold in row.get("thresholds_tested", [])}
        thresholds.update(row.get("threshold") for row in entries if row.get("threshold") is not None)
        return {"experiments": len(entries), "models": len({row.get("model") for row in entries}),
                "feature_sets": len({tuple(row.get("feature_groups", [])) for row in entries}),
                "thresholds": len(thresholds),
                "strategy_candidates": len({row.get("strategy") for row in entries if row.get("strategy")})}
