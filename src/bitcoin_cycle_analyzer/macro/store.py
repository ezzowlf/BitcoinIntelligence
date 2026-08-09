from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd
from .contracts import MacroObservation

SCHEMA="""CREATE TABLE IF NOT EXISTS macro_releases(
series_id TEXT NOT NULL, period TEXT NOT NULL, value REAL NOT NULL, release_timestamp TEXT NOT NULL,
available_at TEXT NOT NULL, vintage_date TEXT NOT NULL, revision_number INTEGER NOT NULL, provider TEXT NOT NULL,
imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, quality TEXT NOT NULL,
PRIMARY KEY(series_id,period,vintage_date,revision_number));
CREATE INDEX IF NOT EXISTS idx_macro_series ON macro_releases(series_id);
CREATE INDEX IF NOT EXISTS idx_macro_period ON macro_releases(period);
CREATE INDEX IF NOT EXISTS idx_macro_available ON macro_releases(available_at);"""


class MacroReleaseStore:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as con: con.executescript(SCHEMA)

    def upsert(self,records:list[MacroObservation]):
        rows=[(r.metric,str(r.period_start),r.observation_value,str(r.release_time),str(r.available_at),
               str(r.release_time.date()),0,r.provider,"HIGH") for r in records]
        with sqlite3.connect(self.path) as con:
            con.executemany("INSERT OR IGNORE INTO macro_releases(series_id,period,value,release_timestamp,available_at,vintage_date,revision_number,provider,quality) VALUES(?,?,?,?,?,?,?,?,?)",rows)
        return len(rows)

    def as_of(self,series_id,cutoff):
        with sqlite3.connect(self.path) as con:
            return pd.read_sql_query("SELECT * FROM macro_releases WHERE series_id=? AND available_at<=? ORDER BY period,available_at",con,params=(series_id,str(pd.Timestamp(cutoff))))

    def health(self):
        with sqlite3.connect(self.path) as con:
            duplicates=con.execute("SELECT COUNT(*) FROM (SELECT series_id,period,vintage_date,revision_number,COUNT(*) n FROM macro_releases GROUP BY 1,2,3,4 HAVING n>1)").fetchone()[0]
            rows=con.execute("SELECT COUNT(*) FROM macro_releases").fetchone()[0]
        return {"rows":rows,"duplicates":duplicates,"status":"AVAILABLE" if rows else "UNAVAILABLE"}
