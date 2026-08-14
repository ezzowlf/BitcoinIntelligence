"""Persistent state for the Signal-Progress notifier.

One row per direction (BUY/SELL). SQLite transactions are atomic by
construction - a crash mid-write leaves the previous committed row intact,
never a half-written/corrupt one. No price, no secrets, no PII - only the
notifier's own bookkeeping fields.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS signal_progress_state(
direction TEXT PRIMARY KEY,
last_progress_level TEXT NOT NULL,
last_score REAL,
last_confirmed TEXT NOT NULL DEFAULT '[]',
last_fingerprint TEXT,
was_notified INTEGER NOT NULL DEFAULT 0,
invalidated INTEGER NOT NULL DEFAULT 0,
last_sent_at TEXT,
last_message_type TEXT,
updated_at TEXT NOT NULL
);"""


class SignalProgressStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.executescript(SCHEMA)

    def get(self, direction: str) -> dict | None:
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT * FROM signal_progress_state WHERE direction=?", (direction,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["last_confirmed"] = json.loads(data["last_confirmed"] or "[]")
        data["was_notified"] = bool(data["was_notified"])
        data["invalidated"] = bool(data["invalidated"])
        if data["last_sent_at"]:
            data["last_sent_at"] = datetime.fromisoformat(data["last_sent_at"])
        return data

    def save(self, new_row: dict) -> None:
        last_sent_at = new_row.get("last_sent_at")
        if isinstance(last_sent_at, datetime):
            last_sent_at = last_sent_at.isoformat()
        payload = {
            "direction": new_row["direction"],
            "last_progress_level": new_row["last_progress_level"],
            "last_score": new_row.get("last_score"),
            "last_confirmed": json.dumps(sorted(new_row.get("last_confirmed", []) or [])),
            "last_fingerprint": new_row.get("last_fingerprint"),
            "was_notified": int(bool(new_row.get("was_notified"))),
            "invalidated": int(bool(new_row.get("invalidated"))),
            "last_sent_at": last_sent_at,
            "last_message_type": new_row.get("last_message_type"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with sqlite3.connect(self.path) as con:
            con.execute(
                """INSERT INTO signal_progress_state(direction,last_progress_level,last_score,last_confirmed,last_fingerprint,was_notified,invalidated,last_sent_at,last_message_type,updated_at)
                VALUES(:direction,:last_progress_level,:last_score,:last_confirmed,:last_fingerprint,:was_notified,:invalidated,:last_sent_at,:last_message_type,:updated_at)
                ON CONFLICT(direction) DO UPDATE SET
                last_progress_level=excluded.last_progress_level,last_score=excluded.last_score,last_confirmed=excluded.last_confirmed,
                last_fingerprint=excluded.last_fingerprint,was_notified=excluded.was_notified,invalidated=excluded.invalidated,
                last_sent_at=excluded.last_sent_at,last_message_type=excluded.last_message_type,updated_at=excluded.updated_at""",
                payload,
            )

    def last_alert_summary(self) -> dict | None:
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT direction,last_message_type,last_sent_at FROM signal_progress_state WHERE last_sent_at IS NOT NULL ORDER BY last_sent_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None
