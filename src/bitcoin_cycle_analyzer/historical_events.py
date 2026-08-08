from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

SCHEMA = """CREATE TABLE IF NOT EXISTS historical_events (
    event_start TEXT NOT NULL, event_end TEXT NOT NULL, category TEXT NOT NULL,
    description TEXT NOT NULL, source_url TEXT NOT NULL,
    btc_return_1d REAL, btc_return_7d REAL, btc_return_30d REAL,
    max_drawdown REAL, volatility_change REAL,
    PRIMARY KEY(event_start, category, description))"""


class HistoricalEventLibrary:
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con: con.execute(SCHEMA)

    def add(self, event: dict) -> None:
        required = {"event_start", "event_end", "category", "description", "source_url"}
        if not required <= event.keys() or not event["source_url"]:
            raise ValueError("verified event dates, description and source_url required")
        columns = ["event_start", "event_end", "category", "description", "source_url", "btc_return_1d", "btc_return_7d", "btc_return_30d", "max_drawdown", "volatility_change"]
        with sqlite3.connect(self.path) as con:
            con.execute(f"INSERT OR REPLACE INTO historical_events ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [event.get(column) for column in columns])

    def load(self) -> pd.DataFrame:
        with sqlite3.connect(self.path) as con: return pd.read_sql_query("SELECT * FROM historical_events ORDER BY event_start", con)

