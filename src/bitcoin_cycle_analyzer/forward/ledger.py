from __future__ import annotations
import json,sqlite3
from pathlib import Path
import pandas as pd

FORWARD_START=pd.Timestamp("2026-08-10T00:00:00Z")
SCHEMA="""CREATE TABLE IF NOT EXISTS frozen_snapshots(timestamp TEXT PRIMARY KEY,btc_price REAL NOT NULL,payload_json TEXT NOT NULL,model_id TEXT NOT NULL,commit_hash TEXT NOT NULL,config_hash TEXT NOT NULL,available_at TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS decision_alerts(alert_id TEXT PRIMARY KEY,timestamp TEXT NOT NULL,alert_type TEXT NOT NULL,decision TEXT NOT NULL,payload_json TEXT NOT NULL,model_id TEXT NOT NULL,message_hash TEXT,market_state TEXT,btc_price REAL,telegram_delivery_status TEXT DEFAULT 'PENDING',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS forward_outcomes(alert_id TEXT,horizon_days INTEGER,outcome_json TEXT,matured_at TEXT,PRIMARY KEY(alert_id,horizon_days));
CREATE TRIGGER IF NOT EXISTS frozen_no_update BEFORE UPDATE ON frozen_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS frozen_no_delete BEFORE DELETE ON frozen_snapshots BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS alerts_no_update BEFORE UPDATE ON decision_alerts BEGIN SELECT RAISE(ABORT,'append-only'); END;
CREATE TRIGGER IF NOT EXISTS alerts_no_delete BEFORE DELETE ON decision_alerts BEGIN SELECT RAISE(ABORT,'append-only'); END;"""


class ForwardLedger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);con=sqlite3.connect(self.path);con.executescript(SCHEMA)
        columns={row[1] for row in con.execute("PRAGMA table_info(decision_alerts)")}
        for name,kind in (("message_hash","TEXT"),("market_state","TEXT"),("btc_price","REAL"),("telegram_delivery_status","TEXT DEFAULT 'PENDING'")):
            if name not in columns:con.execute(f"ALTER TABLE decision_alerts ADD COLUMN {name} {kind}")
        con.close()
    def append_snapshot(self,state,commit_hash,config_hash):
        p=state["precision"]; timestamp=pd.Timestamp(p["timestamp"])
        if timestamp<FORWARD_START: raise ValueError("snapshot precedes frozen forward start")
        payload={"timestamp":timestamp,"btc_price":state["decision"]["zones"]["current_price"],"value":p["value"],"cycle":p["cycle"],"regime":p["regime"],"timing":p["timing"],"risk":p["risk"],"capitulation":p["risk"]["capitulation"],"onchain":state["modules"]["onchain"],"derivatives":state["modules"]["derivatives"],"evidence":p["evidence"],"confluence":p["confluence"],"uncertainty":p["uncertainty"],"data_quality":p["data_health"],"market_state":p["market_state"],"system_conclusion":p["system_conclusion"],"decision":state["decision"],"engine_version":"2.3-FROZEN","commit":commit_hash,"config_hash":config_hash}
        with sqlite3.connect(self.path) as con: con.execute("INSERT INTO frozen_snapshots(timestamp,btc_price,payload_json,model_id,commit_hash,config_hash,available_at) VALUES(?,?,?,?,?,?,?)",(str(timestamp),payload["btc_price"],json.dumps(payload,default=str),"2.3-FROZEN",commit_hash,config_hash,str(timestamp)))
        return payload
    def append_alert(self,alert_id,timestamp,alert_type,decision,payload,delivery_status="PENDING"):
        message_hash=payload.get("message_hash") or __import__("hashlib").sha256(payload.get("message","").encode()).hexdigest()
        with sqlite3.connect(self.path) as con: con.execute("INSERT INTO decision_alerts(alert_id,timestamp,alert_type,decision,payload_json,model_id,message_hash,market_state,btc_price,telegram_delivery_status) VALUES(?,?,?,?,?,?,?,?,?,?)",(alert_id,str(timestamp),alert_type,decision,json.dumps(payload,default=str),"2.3-FROZEN",message_hash,payload.get("market_state"),payload.get("btc_price"),delivery_status))
    def alert_exists(self,alert_id):
        with sqlite3.connect(self.path) as con:return con.execute("SELECT 1 FROM decision_alerts WHERE alert_id=?",(alert_id,)).fetchone() is not None
    def delivery_status(self,alert_id):
        with sqlite3.connect(self.path) as con:
            row=con.execute("SELECT telegram_delivery_status FROM decision_alerts WHERE alert_id=?",(alert_id,)).fetchone();return None if row is None else row[0]
    def latest_snapshot(self):
        with sqlite3.connect(self.path) as con: row=con.execute("SELECT payload_json FROM frozen_snapshots ORDER BY timestamp DESC LIMIT 1").fetchone()
        return None if row is None else json.loads(row[0])
    def health(self):
        with sqlite3.connect(self.path) as con: snapshots=con.execute("SELECT COUNT(*) FROM frozen_snapshots").fetchone()[0];alerts=con.execute("SELECT COUNT(*) FROM decision_alerts").fetchone()[0]
        return {"model":"2.3-FROZEN","forward_start":str(FORWARD_START),"snapshots":snapshots,"alerts":alerts,"append_only":True,"execution":"DISABLED"}
