from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from .event_evidence import PointInTimeEventDatabase
from .fusion_live import Fusion6ForwardLedger

def _manifest(root,filename,folder):
    payload=json.loads((root/"frozen"/filename).read_text(encoding="utf-8"));return all(hashlib.sha256((root/"src"/"bitcoin_cycle_analyzer"/folder/name).read_bytes()).hexdigest().upper()==expected for name,expected in payload["code_manifest_sha256"].items())
def runtime_health(root:Path,live_market:dict):
    root=Path(root);frozen=json.loads((root/"frozen"/"fusion_6_research_frozen.json").read_text(encoding="utf-8"));log=root/"runtime"/"fusion6"/"shadow.log";age=None if not log.exists() else (datetime.now(timezone.utc)-datetime.fromtimestamp(log.stat().st_mtime,timezone.utc)).total_seconds()
    return {"mt5":live_market.get("status"),"price_freshness":live_market.get("tick",{}).get("freshness"),"last_confirmed_h4":live_market.get("last_confirmed_h4"),"fusion_watcher":{"status":"ONLINE" if age is not None and age<180 else "OFFLINE_OR_STALE","log_age_seconds":age},"fusion_forward":Fusion6ForwardLedger(root/"database"/"fusion6_live.db",frozen["forward_start"]).health(),"event_db":PointInTimeEventDatabase(root/"database"/"historical_event_evidence.db").health(),"pattern_registry":{"status":"AVAILABLE" if (root/"data"/"reports"/"fusion6_pattern_registry.csv").exists() else "MISSING"},"frozen_manifests":{"MASTER_5":_manifest(root,"master_5_0_challenger_frozen.json","master5"),"FUSION_6":_manifest(root,"fusion_6_research_frozen.json","fusion6")},"telegram":{"allowlist":"CONFIGURED" if (root/"config"/"telegram_allowlist.json").exists() else "NOT_CONFIGURED"},"execution":"DISABLED"}
