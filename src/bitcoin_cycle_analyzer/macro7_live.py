from __future__ import annotations
import hashlib,json,sqlite3
from pathlib import Path
import pandas as pd

class Macro7ShadowLedger:
    def __init__(self,path:Path,forward_start):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.forward_start=pd.Timestamp(forward_start)
        with sqlite3.connect(self.path) as db:db.executescript("CREATE TABLE IF NOT EXISTS macro7_snapshots(id TEXT PRIMARY KEY,timeframe TEXT NOT NULL,timestamp TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(timeframe,timestamp));CREATE TRIGGER IF NOT EXISTS macro7_no_update BEFORE UPDATE ON macro7_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;CREATE TRIGGER IF NOT EXISTS macro7_no_delete BEFORE DELETE ON macro7_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;")
    def append(self,timeframe,timestamp,payload):
        ts=pd.Timestamp(timestamp)
        if ts<=self.forward_start:raise ValueError("snapshot must be after Macro 7 freeze")
        body=json.dumps(payload,sort_keys=True,default=str);sid=hashlib.sha256(f"{timeframe}|{ts}|{body}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            prior=db.execute("SELECT payload_json,id FROM macro7_snapshots WHERE timeframe=? AND timestamp=?",(timeframe,ts.isoformat())).fetchone()
            if prior and prior[0]!=body:raise ValueError("append-only violation")
            db.execute("INSERT OR IGNORE INTO macro7_snapshots(id,timeframe,timestamp,payload_json) VALUES(?,?,?,?)",(sid,timeframe,ts.isoformat(),body))
        return prior[1] if prior else sid
    def health(self):
        with sqlite3.connect(self.path) as db:rows=db.execute("SELECT timeframe,COUNT(*),MAX(timestamp) FROM macro7_snapshots GROUP BY timeframe").fetchall()
        return {"snapshots":{x[0]:{"count":x[1],"last":x[2]} for x in rows},"append_only":True,"execution":"DISABLED"}
