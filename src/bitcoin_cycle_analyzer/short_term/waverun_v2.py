from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class OpportunityRecord:
    opportunity_id: str
    timestamp: str
    direction: str
    setup_family: str
    primary_horizon: int
    primary_target: int
    adverse_barrier: int
    calibrated_probability: float | None
    expected_remaining_move: float
    evidence: dict[str, Any]
    contradictions: list[str]
    state: str
    outcome: str
    execution: str = "DISABLED"


def opportunity_id(timestamp: str, direction: str, target: int, horizon: int) -> str:
    return hashlib.sha256(f"{timestamp}|{direction}|{target}|{horizon}".encode()).hexdigest()[:24]


def enforce_magnitude_monotonicity(probabilities: list[float]) -> list[float]:
    """Project ordered >=$200...>=$800 probabilities onto a non-increasing sequence."""
    values = np.clip(np.asarray(probabilities, dtype=float), 0, 1)
    return np.minimum.accumulate(values).tolist()


def prefreeze_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "precision": metrics.get("precision", 0) >= 0.70,
        "positive_net_ev": metrics.get("net_ev", 0) > 0,
        "frequency": metrics.get("signals_per_day", 0) >= 3,
        "support": metrics.get("signals", 0) >= 100,
        "temporal_stability": metrics.get("positive_folds", 0) > metrics.get("folds", 0) / 2,
        "parameter_stability": metrics.get("parameter_cliff", True) is False,
    }
    return {"passed": all(checks.values()), "checks": checks}


def pareto_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = []
    for row in rows:
        dominated = any(
            other["precision"] >= row["precision"]
            and other["signals_per_day"] >= row["signals_per_day"]
            and other["net_ev"] >= row["net_ev"]
            and (
                other["precision"] > row["precision"]
                or other["signals_per_day"] > row["signals_per_day"]
                or other["net_ev"] > row["net_ev"]
            )
            for other in rows
        )
        if not dominated:
            frontier.append(row)
    return sorted(frontier, key=lambda row: (-row["precision"], -row["signals_per_day"], -row["net_ev"]))


FINDINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS findings(
 finding_id TEXT PRIMARY KEY, category TEXT NOT NULL, statement TEXT NOT NULL,
 evidence_json TEXT NOT NULL, period TEXT NOT NULL, sample_size INTEGER NOT NULL,
 confidence TEXT NOT NULL, supports TEXT NOT NULL, contradicts TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS findings_no_update BEFORE UPDATE ON findings BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS findings_no_delete BEFORE DELETE ON findings BEGIN SELECT RAISE(ABORT,'append-only'); END;
"""


class FindingsStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as database:
            database.executescript(FINDINGS_SCHEMA)

    def append(self, finding: dict[str, Any]) -> str:
        semantic = {key: value for key, value in finding.items() if key != "created_at"}
        canonical = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
        finding_id = hashlib.sha256(canonical.encode()).hexdigest()[:24]
        row = {"finding_id": finding_id, **finding}
        with sqlite3.connect(self.path) as database:
            database.execute(
                "INSERT OR IGNORE INTO findings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (row["finding_id"], row["category"], row["statement"], json.dumps(row["evidence"], sort_keys=True),
                 row["period"], row["sample_size"], row["confidence"], row["supports"], row["contradicts"],
                 row["status"], row["created_at"]),
            )
        return finding_id

    def rows(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as database:
            database.row_factory = sqlite3.Row
            return [dict(row) for row in database.execute("SELECT * FROM findings ORDER BY finding_id")]


def as_record(record: OpportunityRecord) -> dict[str, Any]:
    return asdict(record)
