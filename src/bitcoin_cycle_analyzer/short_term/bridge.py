"""Authenticated, buffered, idempotent Vantage market-data bridge contracts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def event_id(tick: dict[str, Any]) -> str:
    material = f"{tick['symbol']}|{tick['time_msc']}|{tick['bid']}|{tick['ask']}"
    return hashlib.sha256(material.encode()).hexdigest()


class BridgeSpool:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS spool(id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL,sent_at TEXT)")

    def append(self, tick: dict[str, Any]) -> str:
        identifier = event_id(tick)
        payload = {**tick, "event_id": identifier, "receive_time": datetime.now(UTC).isoformat(), "execution": "DISABLED"}
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO spool VALUES(?,?,?,NULL)", (identifier, json.dumps(payload, sort_keys=True, default=str), payload["receive_time"]))
        return identifier

    def pending(self, limit: int = 500) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM spool WHERE sent_at IS NULL ORDER BY created_at LIMIT ?", (limit,))]

    def acknowledge(self, identifiers: list[str]) -> None:
        if not identifiers:
            return
        with sqlite3.connect(self.path) as db:
            db.executemany("UPDATE spool SET sent_at=? WHERE id=?", [(datetime.now(UTC).isoformat(), value) for value in identifiers])


class IngestStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS vantage_ticks(event_id TEXT PRIMARY KEY,event_time TEXT NOT NULL,receive_time TEXT NOT NULL,server_time TEXT NOT NULL,symbol TEXT NOT NULL,bid REAL NOT NULL,ask REAL NOT NULL,spread REAL NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bridge_health(bridge_id TEXT PRIMARY KEY,last_heartbeat TEXT NOT NULL,payload TEXT NOT NULL);
            """)

    def ingest(self, rows: list[dict[str, Any]]) -> list[str]:
        accepted = []
        with sqlite3.connect(self.path) as db:
            for row in rows:
                now = datetime.now(UTC).isoformat()
                cursor = db.execute("INSERT OR IGNORE INTO vantage_ticks VALUES(?,?,?,?,?,?,?,?,?)",
                    (row["event_id"], str(row["timestamp"]), row["receive_time"], now, row["symbol"], row["bid"], row["ask"], row["spread"], json.dumps(row, sort_keys=True)))
                if cursor.rowcount: accepted.append(row["event_id"])
        return accepted

    def heartbeat(self, bridge_id: str, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO bridge_health VALUES(?,?,?)", (bridge_id, now, json.dumps(payload, sort_keys=True)))
