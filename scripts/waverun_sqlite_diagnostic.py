"""Opt-in observation only: timings, errors and periodic Python thread stacks."""
import faulthandler
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
FLAG=ROOT/'runtime/waverun/diagnostic-once.json'
_lock=threading.Lock()
_metrics={}
_handles=[]

def install():
    if not FLAG.exists():return
    target=ROOT/'ops/watchdog-diagnostic-20260915-1242'
    target.mkdir(parents=True,exist_ok=True)
    stack=(target/f'stacks-{os.getpid()}.log').open('a')
    _handles.append(stack)
    faulthandler.enable(file=stack,all_threads=True)
    faulthandler.dump_traceback_later(20,repeat=True,file=stack)
    original=sqlite3.connect

    class Connection(sqlite3.Connection):
        def measured(self,operation,fn,*args,**kwargs):
            start=time.perf_counter();error=None
            try:return fn(*args,**kwargs)
            except sqlite3.Error as exc:
                error={'type':type(exc).__name__,'message':str(exc),'code':getattr(exc,'sqlite_errorcode',None)}
                raise
            finally:
                elapsed=time.perf_counter()-start
                with _lock:
                    key=operation
                    row=_metrics.setdefault(key,{'count':0,'seconds':0,'max_seconds':0,'errors':0,'busy_locked':0,'busy_wait_errors':0})
                    row['count']+=1;row['seconds']+=elapsed;row['max_seconds']=max(row['max_seconds'],elapsed)
                    if error:
                        row['errors']+=1;row['last_error']=error
                        if error['code'] is not None and error['code']&255 in (5,6):
                            row['busy_locked']+=1
                            if elapsed>=.19:row['busy_wait_errors']+=1
                    if error:
                        with (target/'failure.json').open('w') as output:
                            json.dump({'time':time.time(),'operation':operation,'error':error},output)
        def execute(self,sql,*args,**kwargs):
            return self.measured(sql.split()[0].upper()+' '+str(sql.split()[2:3]),super().execute,sql,*args,**kwargs)
        def executemany(self,sql,*args,**kwargs):
            return self.measured('BATCH '+sql.split()[0].upper(),super().executemany,sql,*args,**kwargs)
        def executescript(self,sql,*args,**kwargs):
            return self.measured('SCHEMA',super().executescript,sql,*args,**kwargs)
        def commit(self):return self.measured('COMMIT',super().commit)
        def __exit__(self,*args):return self.measured('CONTEXT_COMMIT_ROLLBACK',super().__exit__,*args)

    def connect(*args,**kwargs):
        kwargs.setdefault('factory',Connection)
        return original(*args,**kwargs)
    sqlite3.connect=connect

    def report():
        with (target/f'sqlite-{os.getpid()}.jsonl').open('a',buffering=1) as output:
            while True:
                with _lock: snapshot=json.loads(json.dumps(_metrics))
                output.write(json.dumps({'time':time.time(),'pid':os.getpid(),'metrics':snapshot})+'\n')
                time.sleep(1)
    threading.Thread(target=report,name='sqlite-diagnostic',daemon=True).start()
