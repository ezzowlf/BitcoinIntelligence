from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

HORIZONS = {"4H": pd.Timedelta(hours=4), "1D": pd.Timedelta(days=1), "3D": pd.Timedelta(days=3), "7D": pd.Timedelta(days=7), "14D": pd.Timedelta(days=14), "30D": pd.Timedelta(days=30), "90D": pd.Timedelta(days=90)}
WATCHED_TRANSITIONS = {("WAIT", "CONFIRMING"), ("CONFIRMING", "CONFIRMED"), ("BUY_ZONE", "STRONG_BUY"), ("WATCH", "DISTRIBUTION"), ("CAUTION", "HIGH_RISK")}


class Fusion6ForwardLedger:
    """Append-only Fusion 6 observation store. Frozen engines are inputs only."""

    def __init__(self, path: Path, forward_start):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.forward_start = pd.Timestamp(forward_start)
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS fusion_snapshots(id TEXT PRIMARY KEY,timestamp TEXT UNIQUE NOT NULL,price REAL NOT NULL,payload_json TEXT NOT NULL,is_first_true INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS fusion_outcomes(snapshot_id TEXT NOT NULL,horizon TEXT NOT NULL,observed_at TEXT NOT NULL,outcome_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(snapshot_id,horizon));
            CREATE TABLE IF NOT EXISTS fusion_transitions(id TEXT PRIMARY KEY,timestamp TEXT NOT NULL,field TEXT NOT NULL,old_state TEXT NOT NULL,new_state TEXT NOT NULL,snapshot_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS research_next_candidates(id TEXT PRIMARY KEY,discovered_at TEXT NOT NULL,title TEXT NOT NULL,evidence_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'RESEARCH_NEXT',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TRIGGER IF NOT EXISTS fusion_snapshots_no_update BEFORE UPDATE ON fusion_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fusion_snapshots_no_delete BEFORE DELETE ON fusion_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fusion_outcomes_no_update BEFORE UPDATE ON fusion_outcomes BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fusion_outcomes_no_delete BEFORE DELETE ON fusion_outcomes BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fusion_transitions_no_update BEFORE UPDATE ON fusion_transitions BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fusion_transitions_no_delete BEFORE DELETE ON fusion_transitions BEGIN SELECT RAISE(ABORT,'append-only'); END;
            """)

    def append_snapshot(self, timestamp, price: float, payload: dict) -> dict:
        ts = pd.Timestamp(timestamp)
        if ts <= self.forward_start:
            raise ValueError("snapshot must be a confirmed candle strictly after Fusion 6 forward start")
        body = json.dumps(payload, sort_keys=True, default=str)
        sid = hashlib.sha256(f"{ts.isoformat()}|{body}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            prior = db.execute("SELECT id,payload_json,is_first_true FROM fusion_snapshots WHERE timestamp=?", (ts.isoformat(),)).fetchone()
            if prior:
                if prior[1] != body:
                    raise ValueError("append-only violation: confirmed timestamp already frozen")
                return {"id": prior[0], "inserted": False, "first_true": bool(prior[2])}
            first = db.execute("SELECT COUNT(*) FROM fusion_snapshots").fetchone()[0] == 0
            db.execute("INSERT INTO fusion_snapshots(id,timestamp,price,payload_json,is_first_true) VALUES(?,?,?,?,?)", (sid, ts.isoformat(), float(price), body, int(first)))
        return {"id": sid, "inserted": True, "first_true": first, "marker": "FIRST_TRUE_FUSION6_FORWARD_SNAPSHOT" if first else None}

    def append_transitions(self, snapshot_id: str, timestamp, previous: dict | None, current: dict) -> list[dict]:
        if not previous:
            return []
        fields = {"timing": "timing", "rare_buy": "rare_buy", "distribution": "distribution", "risk": "risk", "new_entry": "new_entry"}
        rows = []
        with sqlite3.connect(self.path) as db:
            for field, key in fields.items():
                old, new = previous.get(key), current.get(key)
                if old == new or (old, new) not in WATCHED_TRANSITIONS:
                    continue
                payload = {"field": field, "old": old, "new": new, "execution": "DISABLED"}
                tid = hashlib.sha256(f"{snapshot_id}|{field}|{old}|{new}".encode()).hexdigest()
                db.execute("INSERT OR IGNORE INTO fusion_transitions(id,timestamp,field,old_state,new_state,snapshot_id,payload_json) VALUES(?,?,?,?,?,?,?)", (tid, pd.Timestamp(timestamp).isoformat(), field, old, new, snapshot_id, json.dumps(payload)))
                rows.append({"id": tid, **payload})
        return rows

    def mature_outcomes(self, prices: pd.DataFrame, as_of=None) -> int:
        if prices.empty:
            return 0
        series = prices["close"].sort_index()
        cutoff = pd.Timestamp(as_of) if as_of is not None else series.index.max()
        inserted = 0
        with sqlite3.connect(self.path) as db:
            snapshots = db.execute("SELECT id,timestamp,price FROM fusion_snapshots ORDER BY timestamp").fetchall()
            for sid, raw_ts, entry in snapshots:
                ts = pd.Timestamp(raw_ts)
                for label, delta in HORIZONS.items():
                    target = ts + delta
                    if target > cutoff or db.execute("SELECT 1 FROM fusion_outcomes WHERE snapshot_id=? AND horizon=?", (sid, label)).fetchone():
                        continue
                    future = series.loc[series.index >= target]
                    if future.empty:
                        continue
                    observed_at, price = future.index[0], float(future.iloc[0])
                    payload = {"entry_price": entry, "outcome_price": price, "return": price / entry - 1, "target_at": target.isoformat(), "observed_at": observed_at.isoformat()}
                    db.execute("INSERT INTO fusion_outcomes(snapshot_id,horizon,observed_at,outcome_json) VALUES(?,?,?,?)", (sid, label, observed_at.isoformat(), json.dumps(payload)))
                    inserted += 1
        return inserted

    def add_research_next(self, discovered_at, title: str, evidence: dict) -> str:
        body = json.dumps(evidence, sort_keys=True, default=str)
        rid = hashlib.sha256(f"{title}|{body}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO research_next_candidates(id,discovered_at,title,evidence_json) VALUES(?,?,?,?)", (rid, pd.Timestamp(discovered_at).isoformat(), title, body))
        return rid

    def latest_payload(self) -> dict | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload_json FROM fusion_snapshots ORDER BY timestamp DESC LIMIT 1").fetchone()
        return None if row is None else json.loads(row[0])

    def health(self) -> dict:
        with sqlite3.connect(self.path) as db:
            counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("fusion_snapshots", "fusion_outcomes", "fusion_transitions", "research_next_candidates")}
            first = db.execute("SELECT timestamp FROM fusion_snapshots WHERE is_first_true=1 LIMIT 1").fetchone()
        return {**counts, "first_true_snapshot": None if first is None else first[0], "append_only": True, "execution": "DISABLED"}
