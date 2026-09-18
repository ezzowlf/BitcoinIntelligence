"""Read-only evidence capture and guarded, once-only approved watchdog reset."""
import argparse
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'ops' / 'watchdog-diagnostic-20260915-1242'
RUNTIME = ROOT / 'runtime/waverun'

def capture(label):
    target = DEST / label
    target.mkdir(parents=True, exist_ok=False)
    for name in ('health.json','backpressure.json','writer_health.json','collector_process.json',
                 'watchdog_status.json','restart_request.json','signal.json','latest.json'):
        source = RUNTIME / name
        if source.exists(): shutil.copy2(source,target / name)
    for source in (ROOT / 'logs').glob('TAKEOFF-Collector.*.log'):
        shutil.copy2(source,target/source.name)
    ps = "Get-Date; Get-CimInstance Win32_Service | Where-Object Name -Like 'TAKEOFF*' | Select-Object Name,State,ProcessId,StartName; Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|terminal64|nssm'} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List; Get-PSDrive C"
    (target/'processes.txt').write_text(subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True).stdout)
    facts={}
    for name in ('watchdog.db','journal.db'):
        source=RUNTIME/name
        db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=1)
        facts[name]={'journal_mode':db.execute('PRAGMA journal_mode').fetchone(),
                     'files':{str(p.name):p.stat().st_size for p in RUNTIME.glob(name+'*') if p.is_file()}}
        if name=='watchdog.db':
            backup=sqlite3.connect(target/name);db.backup(backup);backup.close()
            facts[name]['states']=db.execute('SELECT * FROM state').fetchall()
            facts[name]['recent']=db.execute('SELECT * FROM events ORDER BY seq DESC LIMIT 10').fetchall()
        else:
            facts[name]['progress']=db.execute('SELECT * FROM progress').fetchall()
            facts[name]['incidents']=db.execute("SELECT timestamp,payload FROM events WHERE kind='incident' ORDER BY seq DESC LIMIT 20").fetchall()
            facts[name]['outbox']=db.execute('SELECT count(*) FROM outcome_outbox').fetchone()
        db.close()
    # A short write-lock probe rolls back immediately; it changes no data.
    db=sqlite3.connect(RUNTIME/'journal.db',timeout=.2)
    start=time.monotonic()
    try: db.execute('BEGIN IMMEDIATE');db.rollback();facts['lock_probe']='AVAILABLE'
    except sqlite3.Error as exc: facts['lock_probe']=str(exc)
    finally: db.close()
    facts['lock_probe_seconds']=time.monotonic()-start
    (target/'database.json').write_text(json.dumps(facts,indent=2))
    print(str(target),flush=True)

def reset():
    if not (DEST/'before'/'watchdog.db').exists():raise RuntimeError('Missing before snapshot')
    marker=DEST/'reset-once.json'
    with marker.open('x') as output:
        db=sqlite3.connect(RUNTIME/'watchdog.db')
        try:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute("SELECT payload FROM state WHERE key='launch_attempts'").fetchone()
            db.execute("UPDATE state SET payload='[]' WHERE key='launch_attempts'")
            db.commit()
            json.dump({'reset_at':time.time(),'old':old,'reset_count':1},output)
        finally:db.close()
    print('ONE RESET COMMITTED',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['before','after','reset']);args=parser.parse_args()
    reset() if args.mode=='reset' else capture(args.mode)
