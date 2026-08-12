from __future__ import annotations
import hashlib,sqlite3
from pathlib import Path
import pandas as pd

CATEGORIES={"WAR_ESCALATION","WAR_DEESCALATION","FED","CPI","LABOR","BANKING_CRISIS","EXCHANGE_FAILURE","REGULATION","ETF","STABLECOIN","LIQUIDITY","SANCTIONS","ENERGY"}
class HistoricalEventStore:
    def __init__(self,path:Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:db.execute("CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,headline TEXT,category TEXT,event_time TEXT,available_at TEXT,source TEXT,severity_at_time TEXT)")
    def append(self,headline,category,event_time,available_at,source,severity):
        if category not in CATEGORIES:raise ValueError("unsupported category")
        event_time=pd.Timestamp(event_time);available_at=pd.Timestamp(available_at)
        if available_at<event_time:raise ValueError("available_at precedes event_time")
        if not str(source).startswith(("https://","http://")):raise ValueError("verifiable source URL required")
        eid=hashlib.sha256(f"{headline}|{event_time}|{source}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?)",(eid,headline,category,event_time.isoformat(),available_at.isoformat(),source,severity))
        return eid
    def as_of(self,timestamp):
        with sqlite3.connect(self.path) as db:return pd.read_sql_query("SELECT * FROM events WHERE available_at<=? ORDER BY event_time",db,params=(pd.Timestamp(timestamp).isoformat(),))
