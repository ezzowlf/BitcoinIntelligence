from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .contracts import Forecast


class ForecastStore:
    """Small append-only forecast/outcome store; raw feed retention stays separate."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS predictions (
                prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, horizon_seconds INTEGER NOT NULL,
                payload TEXT NOT NULL, actual_return REAL, mfe REAL, mae REAL,
                outcome_at TEXT, UNIQUE(timestamp, horizon_seconds)
            )""")

    def append(self, forecast: Forecast) -> str:
        payload = json.dumps(forecast.to_dict(), ensure_ascii=False, sort_keys=True)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO predictions(timestamp,horizon_seconds,payload) VALUES (?,?,?)", (forecast.timestamp.isoformat(), forecast.horizon_seconds, payload))
        return forecast.timestamp.isoformat()

    def record_outcome(self, timestamp: str, horizon_seconds: int, actual_return: float, mfe: float | None = None, mae: float | None = None, outcome_at: str | None = None) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE predictions SET actual_return=?,mfe=?,mae=?,outcome_at=? WHERE timestamp=? AND horizon_seconds=?", (actual_return, mfe, mae, outcome_at, timestamp, horizon_seconds))

    def pending(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM predictions WHERE actual_return IS NULL ORDER BY timestamp")]
