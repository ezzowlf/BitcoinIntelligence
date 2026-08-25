"""Append-only tracking for de-clustered LIVE SIGNAL UNVERIFIED observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

HORIZONS = (30, 60, 120, 180, 300)
TARGETS = (25, 50, 75, 100, 150, 200, 300)
DECLUSTER_SECONDS = 180


@dataclass
class _Path:
    signal: dict[str, Any]
    favorable: list[tuple[float, float]] = field(default_factory=list)
    written_horizons: set[int] = field(default_factory=set)


class UnverifiedSignalTracker:
    """Persist signals, alerts and completed Vantage Bid/Ask outcomes."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.signals_path = root / "live_signals_unverified.jsonl"
        self.alerts_path = root / "signal_alerts.jsonl"
        self.outcomes_path = root / "live_signal_outcomes.jsonl"
        self._last_signal: pd.Timestamp | None = None
        self._paths: dict[str, _Path] = {}

    @staticmethod
    def _append(path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    def observe(
        self,
        *,
        timestamp: datetime,
        direction: str,
        quote: dict[str, Any],
        mechanism: list[dict[str, Any]],
        quality: float,
        reasons: list[str],
        risks: list[str],
    ) -> dict[str, Any] | None:
        stamp = pd.Timestamp(timestamp).tz_convert("UTC")
        if self._last_signal is not None and (stamp - self._last_signal).total_seconds() < DECLUSTER_SECONDS:
            return None
        bid, ask = quote.get("bid"), quote.get("ask")
        if direction not in {"LONG", "SHORT"} or bid is None or ask is None:
            return None
        self._last_signal = stamp
        signal_id = hashlib.sha256(f"{stamp.isoformat()}|{direction}|LIVE_SIGNAL_UNVERIFIED".encode()).hexdigest()
        row = {
            "signal_id": signal_id,
            "timestamp": stamp.isoformat(),
            "direction": direction,
            "status": "LIVE_SIGNAL_UNVERIFIED",
            "mechanism": mechanism,
            "quality": quality,
            "entry": float(ask if direction == "LONG" else bid),
            "entry_side": "ASK" if direction == "LONG" else "BID",
            "spread": quote.get("spread"),
            "reasons": reasons,
            "risks": risks,
            "holdout": "CLOSED",
            "execution": "DISABLED",
        }
        self._append(self.signals_path, row)
        self._append(self.alerts_path, {**row, "alert": True, "sound": True})
        self._paths[signal_id] = _Path(row)
        return row

    def record_vantage_tick(self, tick: dict[str, Any]) -> None:
        now = pd.Timestamp(tick["timestamp"])
        for signal_id, path in list(self._paths.items()):
            start = pd.Timestamp(path.signal["timestamp"])
            elapsed = (now - start).total_seconds()
            if elapsed <= 0:
                continue
            entry = float(path.signal["entry"])
            favorable = (
                float(tick["bid"]) - entry
                if path.signal["direction"] == "LONG"
                else entry - float(tick["ask"])
            )
            path.favorable.append((elapsed, favorable))
            for horizon in HORIZONS:
                if elapsed < horizon or horizon in path.written_horizons:
                    continue
                values = [(seconds, value) for seconds, value in path.favorable if seconds <= horizon]
                if not values:
                    continue
                pnl = [value for _, value in values]
                first_green = next((seconds for seconds, value in values if value > 0), None)
                target_times = {
                    str(target): next((seconds for seconds, value in values if value >= target), None)
                    for target in TARGETS
                }
                outcome = {
                    "signal_id": signal_id,
                    "timestamp": path.signal["timestamp"],
                    "direction": path.signal["direction"],
                    "horizon_seconds": horizon,
                    "entry": entry,
                    "entry_side": path.signal["entry_side"],
                    "mfe": max(pnl),
                    "mae": min(pnl),
                    "time_to_green_s": first_green,
                    "target_hits": {key: value is not None for key, value in target_times.items()},
                    "target_times_s": target_times,
                    "resolved_at": now.isoformat(),
                    "execution": "DISABLED",
                }
                self._append(self.outcomes_path, outcome)
                path.written_horizons.add(horizon)
            if 300 in path.written_horizons:
                del self._paths[signal_id]
