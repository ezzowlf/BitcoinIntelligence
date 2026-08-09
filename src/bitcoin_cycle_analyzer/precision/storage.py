from __future__ import annotations
import hashlib,json,sqlite3
from pathlib import Path

SCHEMA="""CREATE TABLE IF NOT EXISTS precision_snapshots(timestamp TEXT PRIMARY KEY,price REAL,value REAL,regime TEXT,timing TEXT,risk REAL,evidence REAL,confluence REAL,drivers_json TEXT,data_health_json TEXT,engine_version TEXT,config_hash TEXT,code_commit TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS state_transitions(timestamp TEXT,old_state TEXT,new_state TEXT,drivers_json TEXT,confidence REAL,available_at TEXT,PRIMARY KEY(timestamp,old_state,new_state));
CREATE TABLE IF NOT EXISTS research_registry(factor TEXT PRIMARY KEY,hypothesis TEXT,first_test_date TEXT,training_window TEXT,validation_window TEXT,oos_window TEXT,result TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS experiment_ledger(experiment_id TEXT PRIMARY KEY,hypothesis TEXT,change TEXT,dataset TEXT,metrics_json TEXT,result TEXT,decision TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);"""


class PrecisionStore:
    def __init__(self,path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); sqlite3.connect(self.path).executescript(SCHEMA)
    @staticmethod
    def config_hash(config): return hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    def save_snapshot(self,snapshot):
        row=(str(snapshot["timestamp"]),snapshot["price"],snapshot["value"]["score"],snapshot["regime"]["current"],snapshot["timing"]["state"],snapshot["risk"]["horizons"]["30d"],snapshot["evidence"]["score"],snapshot["confluence"]["score"],json.dumps(snapshot.get("explanation",{}),default=str),json.dumps(snapshot.get("data_health",{}),default=str),snapshot["engine_version"],snapshot["config_hash"],snapshot.get("code_commit","unknown"))
        with sqlite3.connect(self.path) as con: con.execute("INSERT OR REPLACE INTO precision_snapshots(timestamp,price,value,regime,timing,risk,evidence,confluence,drivers_json,data_health_json,engine_version,config_hash,code_commit) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",row)
    def as_of(self,cutoff):
        with sqlite3.connect(self.path) as con: row=con.execute("SELECT * FROM precision_snapshots WHERE timestamp<=? ORDER BY timestamp DESC LIMIT 1",(str(cutoff),)).fetchone()
        return row
    def record_transition(self,timestamp,old_state,new_state,drivers,confidence,available_at):
        with sqlite3.connect(self.path) as con: con.execute("INSERT OR IGNORE INTO state_transitions VALUES(?,?,?,?,?,?)",(str(timestamp),old_state,new_state,json.dumps(drivers),confidence,str(available_at)))
    def register_factor(self,record):
        with sqlite3.connect(self.path) as con: con.execute("INSERT OR REPLACE INTO research_registry VALUES(?,?,?,?,?,?,?,?)",tuple(record[key] for key in ("factor","hypothesis","first_test_date","training_window","validation_window","oos_window","result","status")))
    def record_experiment(self,record):
        with sqlite3.connect(self.path) as con: con.execute("INSERT OR REPLACE INTO experiment_ledger(experiment_id,hypothesis,change,dataset,metrics_json,result,decision) VALUES(?,?,?,?,?,?,?)",(record["experiment_id"],record["hypothesis"],record["change"],record["dataset"],json.dumps(record["metrics"]),record["result"],record["decision"]))
