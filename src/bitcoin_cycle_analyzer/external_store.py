from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd
from .data_contracts import MarketDataRecord

SCHEMA = """CREATE TABLE IF NOT EXISTS external_metrics (
    metric TEXT NOT NULL, value REAL NOT NULL, event_timestamp TEXT NOT NULL,
    observed_at TEXT NOT NULL, available_at TEXT NOT NULL, provider TEXT NOT NULL,
    source_id TEXT NOT NULL, quality TEXT NOT NULL, revision TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(metric, event_timestamp, provider, revision))"""


class ExternalMetricStore:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con: con.execute(SCHEMA)

    def upsert(self, records: list[MarketDataRecord]) -> int:
        rows = [(r.metric, r.value, str(r.event_timestamp), str(r.observed_at), str(r.available_at), r.provider, r.source_id, r.quality, r.revision) for r in records]
        with sqlite3.connect(self.path) as con:
            con.executemany("""INSERT OR REPLACE INTO external_metrics
                (metric,value,event_timestamp,observed_at,available_at,provider,source_id,quality,revision)
                VALUES (?,?,?,?,?,?,?,?,?)""", rows)
        return len(rows)

    def load(self, metric: str, as_of=None) -> pd.DataFrame:
        query = "SELECT * FROM external_metrics WHERE metric=?"
        params = [metric]
        if as_of is not None:
            query += " AND available_at<=?"; params.append(str(pd.Timestamp(as_of)))
        query += " ORDER BY event_timestamp"
        with sqlite3.connect(self.path) as con: frame = pd.read_sql_query(query, con, params=params)
        for column in ("event_timestamp", "observed_at", "available_at", "imported_at"):
            if column in frame: frame[column] = pd.to_datetime(frame[column], utc=True, format="mixed")
        return frame

    def coverage(self) -> pd.DataFrame:
        with sqlite3.connect(self.path) as con:
            return pd.read_sql_query("SELECT metric,provider,MIN(event_timestamp) AS min_time,MAX(event_timestamp) AS max_time,COUNT(*) AS rows FROM external_metrics GROUP BY metric,provider", con)
