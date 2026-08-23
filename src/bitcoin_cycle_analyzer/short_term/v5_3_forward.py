"""Frozen WAVERUN V5.3 Fast V2 forward-only shadow evaluator."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HYPOTHESIS_SHA256 = "49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea"
ACCEL_THRESHOLD = 3.6430941529033496
HISTOGRAM_THRESHOLD = 16.737360838814414
VETO_THRESHOLD = 0.1502250887673838
DECLUSTER_SECONDS = 180
TARGETS = (25, 50, 75, 100, 150, 200, 300, 500)
RESERVED_HOLDOUT = {date(2026, 8, 16), date(2026, 8, 17)}


def is_original_signal(features: dict[str, float]) -> bool:
    return (
        features["macd_30s_cross_direction"] < 0
        and features["macd_30s_histogram"] < 0
        and features["macd_30s_histogram_slope"] < 0
        and features["macd_30s_histogram_acceleration"] < 0
        and abs(features["macd_30s_histogram_acceleration"]) >= ACCEL_THRESHOLD
        and abs(features["macd_30s_histogram"]) >= HISTOGRAM_THRESHOLD
    )


def resolve_short_path(candidate: dict[str, Any], ticks: list[dict[str, Any]]) -> dict[str, Any] | None:
    start = pd.Timestamp(candidate["timestamp"])
    end = start + pd.Timedelta(seconds=300)
    path = [row for row in ticks if start < pd.Timestamp(row["timestamp"]) <= end]
    if not path or pd.Timestamp(path[-1]["timestamp"]) < end:
        return None
    entry = float(candidate["vantage_bid"])
    times = np.array([(pd.Timestamp(row["timestamp"]) - start).total_seconds() for row in path])
    favorable = np.array([entry - float(row["ask"]) for row in path])
    hit_times = {
        str(target): (float(times[np.flatnonzero(favorable >= target)[0]]) if np.any(favorable >= target) else None)
        for target in TARGETS
    }
    first_positive = float(times[np.flatnonzero(favorable > 0)[0]]) if np.any(favorable > 0) else None
    hit100 = hit_times["100"]
    pre100 = favorable[times <= hit100] if hit100 is not None else favorable
    underwater = 0.0
    previous = 0.0
    for seconds, value in zip(times, favorable, strict=True):
        if value < 0:
            underwater += max(0.0, float(seconds) - previous)
        previous = float(seconds)
    return {
        "candidate_id": candidate["candidate_id"],
        "timestamp": candidate["timestamp"],
        "accepted": candidate["accepted"],
        "resolved_at": end.isoformat(),
        "target_hits": {key: value is not None for key, value in hit_times.items()},
        "target_times_s": hit_times,
        "mfe": float(np.max(favorable)),
        "mae": float(max(0.0, -np.min(favorable))),
        "mae_before_100": float(max(0.0, -np.min(pre100))),
        "time_to_first_positive_s": first_positive,
        "time_underwater_s": min(300.0, underwater),
        "hypothesis_sha256": HYPOTHESIS_SHA256,
        "execution": "DISABLED",
    }


class ForwardV2Collector:
    """Append-only collector; all output belongs below ignored runtime/."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.candidates_path = root / "candidates.jsonl"
        self.outcomes_path = root / "outcomes.jsonl"
        self.status_path = root / "status.json"
        self._lock = threading.Lock()
        self._ticks: deque[dict[str, Any]] = deque()
        self._candidates = self._read(self.candidates_path)
        self._outcomes = self._read(self.outcomes_path)
        self._resolved = {row["candidate_id"] for row in self._outcomes}
        self._last_signal = max((pd.Timestamp(row["timestamp"]) for row in self._candidates), default=None)
        self._source_health: dict[str, Any] = {"vantage": "WAITING_FOR_TICKS"}
        self._write_status()

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    @staticmethod
    def _append(path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    def observe(self, timestamp: datetime, features: dict[str, float], spot_pressure_10s: float,
                quote: dict[str, Any], state: dict[str, Any]) -> bool:
        stamp = pd.Timestamp(timestamp).tz_convert("UTC")
        if stamp.date() in RESERVED_HOLDOUT or not is_original_signal(features):
            return False
        with self._lock:
            if self._last_signal is not None and (stamp - self._last_signal).total_seconds() < DECLUSTER_SECONDS:
                return False
            self._last_signal = stamp
            accepted = spot_pressure_10s <= VETO_THRESHOLD
            candidate_id = hashlib.sha256(f"{stamp.isoformat()}|{HYPOTHESIS_SHA256}".encode()).hexdigest()
            row = {
                "candidate_id": candidate_id, "timestamp": stamp.isoformat(), "direction": "SHORT",
                "signal_inputs": features, "spot_pressure_10s": spot_pressure_10s,
                "veto_passed": accepted, "accepted": accepted,
                "vantage_bid": quote.get("bid"), "vantage_ask": quote.get("ask"),
                "spread": quote.get("spread"), **state,
                "hypothesis_sha256": HYPOTHESIS_SHA256, "holdout": "CLOSED", "execution": "DISABLED",
            }
            self._candidates.append(row)
            self._append(self.candidates_path, row)
            self._write_status()
            return True

    def record_vantage_tick(self, tick: dict[str, Any]) -> None:
        with self._lock:
            self._source_health["vantage"] = "AVAILABLE"
            self._ticks.append(tick)
            now = pd.Timestamp(tick["timestamp"])
            while self._ticks and now - pd.Timestamp(self._ticks[0]["timestamp"]) > pd.Timedelta(seconds=330):
                self._ticks.popleft()
            for candidate in self._candidates:
                if candidate["candidate_id"] in self._resolved or candidate.get("vantage_bid") is None:
                    continue
                outcome = resolve_short_path(candidate, list(self._ticks))
                if outcome is not None:
                    self._outcomes.append(outcome)
                    self._resolved.add(candidate["candidate_id"])
                    self._append(self.outcomes_path, outcome)
            self._write_status(now)

    def heartbeat(self, quote: dict[str, Any], feeds: dict[str, Any]) -> None:
        with self._lock:
            self._source_health = {"vantage": quote.get("status", "UNKNOWN"), "feeds": feeds}
            self._write_status(pd.Timestamp.now(tz="UTC"))

    def _write_status(self, now: pd.Timestamp | None = None) -> None:
        accepted = [row for row in self._candidates if row["accepted"]]
        resolved = [row for row in self._outcomes if row["accepted"]]
        wins = sum(row["target_hits"]["100"] for row in resolved)
        status = {
            "title": "FORWARD V2 VALIDATION", "status": "PROVISIONAL",
            "accepted_signals": len(accepted), "veto_blocked_signals": len(self._candidates) - len(accepted),
            "resolved_signals": len(resolved), "progress_to_100": f"{len(resolved)}/100",
            "successes_100_5m": wins,
            "provisional_rate": wins / len(resolved) if resolved else None,
            "last_candidate_timestamp": self._candidates[-1]["timestamp"] if self._candidates else None,
            "recorder_health": "RUNNING" if now is not None else "INITIALIZED",
            "source_health": self._source_health,
            "hypothesis_sha256": HYPOTHESIS_SHA256, "holdout": "CLOSED", "execution": "DISABLED",
            "updated_at": (now.to_pydatetime() if now is not None else datetime.now(UTC)).isoformat(),
        }
        self.status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
