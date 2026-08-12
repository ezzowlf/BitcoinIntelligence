from __future__ import annotations
import hashlib,json,sqlite3
from pathlib import Path

def relevant_changes(previous,current):
    if not previous:return []
    events=[]
    pairs=(("timing","WAIT","CONFIRMING","BUY_TIMING_CONFIRMING"),("timing","CONFIRMING","CONFIRMED","BUY_TIMING_CONFIRMED"),("rare_buy","BUY_ZONE","STRONG_BUY","RARE_BUY_UPGRADE"),("distribution","WATCH","DISTRIBUTION","DISTRIBUTION_UPGRADE"),("risk","CAUTION","HIGH_RISK","RISK_UPGRADE"))
    for field,old,new,event in pairs:
        if previous.get(field)==old and current.get(field)==new:events.append(event)
    old_patterns={x.get("pattern_id") for x in previous.get("active_historical_patterns",[])};new_patterns={x.get("pattern_id") for x in current.get("active_historical_patterns",[])}
    if new_patterns-old_patterns:events.append("NEW_HISTORICAL_PATTERN")
    return events

class FusionAlertLedger:
    def __init__(self,path:Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:db.executescript("CREATE TABLE IF NOT EXISTS fusion_alerts(id TEXT PRIMARY KEY,timestamp TEXT,event TEXT,payload_json TEXT,delivery TEXT DEFAULT 'PENDING',created_at TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TRIGGER IF NOT EXISTS fusion_alerts_no_update BEFORE UPDATE ON fusion_alerts BEGIN SELECT RAISE(ABORT,'append-only'); END;CREATE TRIGGER IF NOT EXISTS fusion_alerts_no_delete BEFORE DELETE ON fusion_alerts BEGIN SELECT RAISE(ABORT,'append-only'); END;")
    def append(self,timestamp,event,payload):
        body=json.dumps(payload,sort_keys=True,default=str);aid=hashlib.sha256(f"{timestamp}|{event}|{body}".encode()).hexdigest()
        with sqlite3.connect(self.path) as db:cur=db.execute("INSERT OR IGNORE INTO fusion_alerts(id,timestamp,event,payload_json) VALUES(?,?,?,?)",(aid,str(timestamp),event,body))
        return {"id":aid,"inserted":bool(cur.rowcount)}
