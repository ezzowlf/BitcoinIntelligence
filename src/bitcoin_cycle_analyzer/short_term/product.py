"""Operational read models and paper ledger for the WAVERUN cockpit."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

HYPOTHESIS_SHA256 = "49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea"
EXECUTION = "DISABLED"


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tail_jsonl(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        block, data = 65536, b""
        while size > 0 and data.count(b"\n") <= limit:
            take = min(block, size)
            size -= take
            handle.seek(size)
            data = handle.read(take) + data
    rows = []
    for line in data.splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def runtime_state(root: Path) -> dict[str, Any]:
    runtime = root / "runtime"
    snapshot = read_json(runtime / "waverun/latest.json") or {}
    validation = read_json(runtime / "waverun_v5_3_fast_v2_forward/status.json") or {}
    ticks = tail_jsonl(runtime / "waverun/vantage_ticks.jsonl", 12000)
    candidates = tail_jsonl(runtime / "waverun_v5_3_fast_v2_forward/candidates.jsonl", 1000)
    outcomes = tail_jsonl(runtime / "waverun_v5_3_fast_v2_forward/outcomes.jsonl", 1000)
    decisions = tail_jsonl(runtime / "waverun/pre_gate_candidates.jsonl", 3)
    latest_tick = ticks[-1] if ticks else {}
    latest_decision = decisions[-1] if decisions else {}
    now = pd.Timestamp.now(tz="UTC")
    tick_time = pd.Timestamp(latest_tick["timestamp"]) if latest_tick else None
    age = None if tick_time is None else max(0.0, (now - tick_time).total_seconds())
    live_state = "LIVE" if age is not None and age <= 3 else "STALE" if age is not None and age <= 30 else "OFFLINE"
    return {"snapshot": snapshot, "validation": validation, "ticks": ticks,
            "candidates": candidates, "outcomes": outcomes, "latest_tick": latest_tick,
            "latest_decision": latest_decision, "age_seconds": age, "live_state": live_state,
            "server_time": now.isoformat(), "hypothesis_sha256": HYPOTHESIS_SHA256,
            "execution": EXECUTION}


def price_frame(ticks: list[dict[str, Any]], timeframe: str) -> pd.DataFrame:
    if not ticks:
        return pd.DataFrame()
    frame = pd.DataFrame(ticks)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True, format="mixed")
    frame = frame.drop_duplicates("time_msc").set_index("timestamp").sort_index()
    frame["mid"] = (frame.bid + frame.ask) / 2
    rule = {"1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "1h": "1h"}[timeframe]
    return frame.mid.resample(rule).ohlc().dropna()


@dataclass(frozen=True)
class PaperEntry:
    direction: str
    note: str
    timestamp: str
    bid: float
    ask: float
    entry: float
    waverun_state: str
    features_json: str


class PaperLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS paper_positions(
              id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, direction TEXT NOT NULL,
              bid REAL NOT NULL, ask REAL NOT NULL, entry REAL NOT NULL, note TEXT NOT NULL,
              waverun_state TEXT NOT NULL, features_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'OPEN', exit_timestamp TEXT, exit_price REAL,
              mfe REAL NOT NULL DEFAULT 0, mae REAL NOT NULL DEFAULT 0,
              hypothesis_sha256 TEXT NOT NULL, execution TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_marks(
              position_id INTEGER NOT NULL, horizon_seconds INTEGER NOT NULL,
              resolved_at TEXT NOT NULL, pnl REAL NOT NULL,
              PRIMARY KEY(position_id,horizon_seconds));
            """)

    def open(self, direction: str, note: str, state: dict[str, Any]) -> int:
        tick = state["latest_tick"]
        if not tick or direction not in {"LONG", "SHORT"}:
            raise ValueError("A live Vantage tick and LONG/SHORT are required")
        entry = float(tick["ask"] if direction == "LONG" else tick["bid"])
        decision = state["latest_decision"]
        item = PaperEntry(direction, note.strip(), tick["timestamp"], float(tick["bid"]),
                          float(tick["ask"]), entry, decision.get("final_decision", "NO TRADE"),
                          json.dumps(decision, sort_keys=True, default=str))
        with sqlite3.connect(self.path) as db:
            cursor = db.execute("""INSERT INTO paper_positions
              (timestamp,direction,bid,ask,entry,note,waverun_state,features_json,hypothesis_sha256,execution)
              VALUES(:timestamp,:direction,:bid,:ask,:entry,:note,:waverun_state,:features_json,:hash,:execution)""",
              {**asdict(item), "hash": HYPOTHESIS_SHA256, "execution": EXECUTION})
            return int(cursor.lastrowid)

    def update(self, tick: dict[str, Any]) -> None:
        if not tick:
            return
        now = pd.Timestamp(tick["timestamp"])
        horizons = (30, 60, 120, 180, 300, 600, 1800)
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM paper_positions WHERE status='OPEN'").fetchall():
                pnl = (float(tick["bid"]) - row["entry"]) if row["direction"] == "LONG" else (row["entry"] - float(tick["ask"]))
                db.execute("UPDATE paper_positions SET mfe=max(mfe,?),mae=max(mae,?) WHERE id=?",
                           (max(0.0, pnl), max(0.0, -pnl), row["id"]))
                age = (now - pd.Timestamp(row["timestamp"])).total_seconds()
                for horizon in horizons:
                    if age >= horizon:
                        db.execute("INSERT OR IGNORE INTO paper_marks VALUES(?,?,?,?)",
                                   (row["id"], horizon, now.isoformat(), pnl))

    def close(self, position_id: int, tick: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM paper_positions WHERE id=? AND status='OPEN'", (position_id,)).fetchone()
            if row is None or not tick:
                return
            price = float(tick["bid"] if row["direction"] == "LONG" else tick["ask"])
            db.execute("UPDATE paper_positions SET status='CLOSED',exit_timestamp=?,exit_price=? WHERE id=?",
                       (tick["timestamp"], price, position_id))

    def rows(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM paper_positions ORDER BY id DESC").fetchall()]

    @staticmethod
    def live_pnl(row: dict[str, Any], tick: dict[str, Any]) -> float | None:
        if not tick:
            return None
        current = float(tick["bid"] if row["direction"] == "LONG" else tick["ask"])
        return current - row["entry"] if row["direction"] == "LONG" else row["entry"] - current
