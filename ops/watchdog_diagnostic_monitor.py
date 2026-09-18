"""Single controlled live run; stop service on the first observed failure."""
import json
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from watchdog_diagnostic import ROOT,DEST,RUNTIME

def read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}

started=time.time()
print('START',started,flush=True)
subprocess.run(['powershell','-NoProfile','-Command','Start-Service TAKEOFF-Collector'],check=True)
boot=None;reason=None;last_health=None;intervals=[];samples=0
with (DEST/'live-samples.jsonl').open('x',buffering=1) as output:
    while time.time()-started<900:
        now=time.time();process=read(RUNTIME/'collector_process.json')
        if process.get('started_at',0)>=started:boot=boot or process.get('boot_id')
        health=read(RUNTIME/'health.json');bp=read(RUNTIME/'backpressure.json')
        watchdog=read(RUNTIME/'watchdog_status.json');failure=read(DEST/'failure.json')
        row={'time':now,'process':process,'health':health,'backpressure':bp,'watchdog':watchdog}
        current=boot and health.get('boot_id')==boot
        try:bp_current=datetime.fromisoformat(bp.get('updated_at','')).timestamp()>=process.get('started_at',now)
        except ValueError:bp_current=False
        if current:
            stamp=health.get('server_time')
            if last_health and stamp!=last_health[0]:intervals.append(now-last_health[1])
            if not last_health or stamp!=last_health[0]:last_health=(stamp,now)
            if bp_current and sum(bp.get('dropped',{}).values()):reason='TRADE_DROPS'
            if bp_current and any(v.get('failed',0) for v in bp.get('metrics',{}).values()):reason='CONSUMER_ERROR_OR_TIMEOUT'
            if last_health and now-last_health[1]>60:reason='HEALTH_WRITER_STALLED'
        if failure.get('time',0)>=started:reason='SQLITE_ERROR'
        if boot and process.get('boot_id')!=boot:reason='UNEXPECTED_RESTART'
        if watchdog.get('reason')=='HEALTH_WRITER_STALLED' and current is False:reason='HEALTH_WRITER_STALLED'
        if now-started>100 and not current:reason='NO_CURRENT_BOOT_HEALTH'
        if samples%10==0:
            for port,path in ((8877,'/api/state'),(8878,'/')):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=2) as response:
                        body=response.read();row[str(port)]={'status':response.status,'bytes':len(body)}
                        if port==8877:row['api']=json.loads(body)
                except Exception as exc:row[str(port)]={'error':str(exc)}
            print(json.dumps({'elapsed':round(now-started,1),'boot':boot,'current_health':bool(current),'reason':reason}),flush=True)
        output.write(json.dumps(row)+'\n');samples+=1
        if reason:break
        time.sleep(.5)
if reason:
    print('STOP '+reason,flush=True)
    subprocess.run(['powershell','-NoProfile','-Command','Stop-Service TAKEOFF-Collector'],check=True)
result={'started':started,'ended':time.time(),'elapsed_seconds':time.time()-started,'reason':reason,
        'boot_id':boot,'health_intervals':intervals,'samples':samples,'execution':'DISABLED'}
(DEST/'run-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
