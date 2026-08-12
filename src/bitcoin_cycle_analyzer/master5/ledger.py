from __future__ import annotations
import hashlib,json,sqlite3
from pathlib import Path
import pandas as pd

class Master5ShadowLedger:
    def __init__(self,path:Path,forward_start):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.forward_start=pd.Timestamp(forward_start)
        with sqlite3.connect(self.path) as db:db.execute("CREATE TABLE IF NOT EXISTS challenger_snapshots(id TEXT PRIMARY KEY,timestamp TEXT UNIQUE,payload TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    def append(self,timestamp,payload):
        ts=pd.Timestamp(timestamp)
        if ts<self.forward_start:raise ValueError("snapshot precedes challenger forward start")
        body=json.dumps(payload,sort_keys=True,default=str);sid=hashlib.sha256(f"{ts}|{body}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            prior=db.execute("SELECT payload FROM challenger_snapshots WHERE timestamp=?",(ts.isoformat(),)).fetchone()
            if prior and prior[0]!=body:raise ValueError("append-only violation: timestamp already frozen")
            db.execute("INSERT OR IGNORE INTO challenger_snapshots(id,timestamp,payload) VALUES(?,?,?)",(sid,ts.isoformat(),body))
        return sid
    def count(self):
        with sqlite3.connect(self.path) as db:return db.execute("SELECT COUNT(*) FROM challenger_snapshots").fetchone()[0]
