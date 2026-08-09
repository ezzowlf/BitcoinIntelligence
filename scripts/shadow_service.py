from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"scripts"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.forward import ForwardLedger
from bitcoin_cycle_analyzer.precision.storage import PrecisionStore
from bitcoin_cycle_analyzer.runtime import RuntimeSettings
from bitcoin_cycle_analyzer.telegram import TelegramClient,TelegramDecisionBot
from bitcoin_cycle_analyzer.telegram.events import detect_events,event_id,event_message
import bitcoin_intelligence

EXPECTED_CONFIG_HASH="db4b6ed6e40fd9f6ce7efe4b0748c61dee83ddcf0603962eb836eeafa8e3ee5f"
CHAMPION="2.3-FROZEN"


def now():return datetime.now(timezone.utc).isoformat()
def json_write(path,payload):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
def settings():
    value=RuntimeSettings.from_env(ROOT);value.ensure_layout();return value
def ledger(cfg):return ForwardLedger(cfg.forward_dir/"forward_validation.db")
def verify_frozen():
    actual=PrecisionStore.config_hash(load_config(ROOT/"config.yaml"))
    if actual!=EXPECTED_CONFIG_HASH:raise RuntimeError("FROZEN_MODEL_HASH_MISMATCH")
    return actual
def audit(cfg,event,**details):
    log=cfg.log_dir/"audit.jsonl"
    if log.exists() and log.stat().st_size>5_000_000:
        rotated=cfg.log_dir/"audit.1.jsonl"
        if rotated.exists():rotated.unlink()
        log.replace(rotated)
    record={"timestamp":now(),"event":event,"champion":CHAMPION,"execution":"DISABLED",**details}
    with log.open("a",encoding="utf-8") as handle:handle.write(json.dumps(record,default=str)+"\n")
def health(cfg,state=None):
    store=ledger(cfg);latest=store.latest_snapshot()
    payload={"system":"ONLINE","champion":CHAMPION,"forward_validation":"ACTIVE","forward_start":"2026-08-10T00:00:00Z","telegram":"DRY_RUN" if cfg.telegram_dry_run else "ACTIVE","last_daily_snapshot":None if latest is None else latest["timestamp"],"execution":"DISABLED",**store.health()}
    if state:payload.update({"last_analysis":str(state["precision"]["timestamp"]),"data_health":state["precision"]["data_health"],"providers":state["data_status"]})
    json_write(cfg.data_dir/"health.json",payload);return payload
def startup(cfg,send=False):
    verify_frozen();marker=cfg.forward_dir/"startup_notice.sent";client=TelegramClient(cfg.telegram_token,cfg.telegram_chat_id,cfg.telegram_enabled,cfg.telegram_dry_run)
    message="₿ Bitcoin Intelligence Online\n\nChampion:\n2.3-FROZEN\n\nMode:\nSHADOW LIVE\n\nForward Validation:\nACTIVE\n\nExecution:\nDISABLED\n\nTelegram Alerts:\nACTIVE"
    result={"status":"ALREADY_RECORDED"}
    if not marker.exists():
        result=client.send(message) if send else {"status":"DRY_RUN","delivered":False,"message":message}
        if result.get("delivered"):marker.write_text(now(),encoding="utf-8")
    audit(cfg,"PROGRAM_START",telegram=result["status"],config_hash=EXPECTED_CONFIG_HASH);return result
def run_analysis(cfg,kind):
    verify_frozen();state,_=bitcoin_intelligence.state();result={"kind":kind,"timestamp":now(),"analysis_timestamp":state["precision"]["timestamp"],"decision":state["decision"]}
    json_write(cfg.data_dir/f"last_{kind}.json",result);health(cfg,state);audit(cfg,f"{kind.upper()}_ANALYSIS",decision=state["decision"]["long_term_decision"]);return state
def dispatch_alerts(cfg,state):
    state_file=cfg.forward_dir/"last_alert_state.json";previous=json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else None
    store=ledger(cfg);client=TelegramClient(cfg.telegram_token,cfg.telegram_chat_id,cfg.telegram_enabled,cfg.telegram_dry_run);results=[]
    for event in detect_events(state,previous):
        alert_id=event_id(event,state)
        if store.alert_exists(alert_id):continue
        message=event_message(event,state);delivery=client.send(message)
        payload={"message":message,"message_hash":hashlib.sha256(message.encode()).hexdigest(),"market_state":state["precision"]["market_state"],"btc_price":state["decision"]["zones"]["current_price"],"delivery":delivery}
        store.append_alert(alert_id,state["precision"]["timestamp"],event,state["decision"]["long_term_decision"],payload,delivery["status"]);results.append({"type":event,"status":delivery["status"]})
    json_write(state_file,state);return results
def daily(cfg):
    state=run_analysis(cfg,"daily");store=ledger(cfg);commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    timestamp=str(state["precision"]["timestamp"])
    if store.latest_snapshot() and store.latest_snapshot()["timestamp"]==timestamp:return {"status":"DEDUPLICATED","timestamp":timestamp}
    payload=store.append_snapshot(state,commit,EXPECTED_CONFIG_HASH);audit(cfg,"SNAPSHOT",timestamp=timestamp);return {"snapshot":payload,"alerts":dispatch_alerts(cfg,state)}
def h4(cfg):
    state=run_analysis(cfg,"h4");return {"decision":state["decision"],"alerts":dispatch_alerts(cfg,state)}
def backup(cfg):
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ");target=cfg.backup_dir/stamp;target.mkdir(parents=True,exist_ok=False)
    copied=[]
    for source in (cfg.forward_dir/"forward_validation.db",ROOT/"config.yaml",ROOT/"frozen"/"bitcoin_intelligence_2_3_frozen.json"):
        if source.exists():shutil.copy2(source,target/source.name);copied.append(source.name)
    dirs=sorted((p for p in cfg.backup_dir.iterdir() if p.is_dir()),reverse=True)
    for old in dirs[7:]:shutil.rmtree(old)
    audit(cfg,"BACKUP",files=copied);return {"backup":str(target),"files":copied,"daily_retention":7}
def connection_test(cfg):
    verify_frozen();client=TelegramClient(cfg.telegram_token,cfg.telegram_chat_id,cfg.telegram_enabled,cfg.telegram_dry_run)
    result=client.send("₿ Bitcoin Intelligence Telegram connection successful.\nExecution remains DISABLED.")
    audit(cfg,"TELEGRAM_CONNECTION_TEST",status=result["status"]);return result
def refresh(cfg,external=False):
    script=ROOT/"scripts"/("update_external_data.py" if external else "update_data.py")
    process=subprocess.run([sys.executable,str(script)],cwd=ROOT,text=True,capture_output=True,timeout=900)
    audit(cfg,"PROVIDER_REFRESH" if external else "PRICE_REFRESH",status="OK" if process.returncode==0 else "ERROR")
    return {"status":"OK" if process.returncode==0 else "ERROR","kind":"providers" if external else "price","returncode":process.returncode}
def command(cfg,name):
    state=run_analysis(cfg,"command");return TelegramDecisionBot(dry_run=cfg.telegram_dry_run,ledger=ledger(cfg)).command(name,state,health(cfg,state))
def poll(cfg):
    client=TelegramClient(cfg.telegram_token,cfg.telegram_chat_id,cfg.telegram_enabled,cfg.telegram_dry_run);offset_file=cfg.forward_dir/"telegram_offset.txt";offset=int(offset_file.read_text()) if offset_file.exists() else None;handled=[]
    for update in client.get_updates(offset):
        offset=max(offset or 0,update["update_id"]+1);name=client.authorized_command(update)
        if name in {"/btc","/decision","/value","/timing","/risk","/cycle","/zones","/why","/health","/candidates","/signals"}:handled.append({"command":name,"delivery":client.send(command(cfg,name))["status"]})
    if offset is not None:offset_file.write_text(str(offset),encoding="ascii")
    return {"handled":handled,"unauthorized_ignored":True}
def main():
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("startup","daily","h4","health","backup","telegram-test","command","poll","refresh-price","refresh-providers"));parser.add_argument("--command",default="/decision");parser.add_argument("--send",action="store_true");args=parser.parse_args();cfg=settings()
    try:
        result={"startup":lambda:startup(cfg,args.send),"daily":lambda:daily(cfg),"h4":lambda:h4(cfg),"health":lambda:health(cfg),"backup":lambda:backup(cfg),"telegram-test":lambda:connection_test(cfg),"command":lambda:command(cfg,args.command),"poll":lambda:poll(cfg),"refresh-price":lambda:refresh(cfg),"refresh-providers":lambda:refresh(cfg,True)}[args.action]()
        print(result if isinstance(result,str) else json.dumps(result,indent=2,default=str))
    except Exception as exc:
        logging.exception("Shadow service action failed");audit(cfg,"ERROR",action=args.action,error=type(exc).__name__);print(json.dumps({"status":"ERROR","code":str(exc),"execution":"DISABLED"}));raise SystemExit(1)
if __name__=="__main__":main()
