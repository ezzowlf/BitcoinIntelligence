"""External collector owner: restart only its own child, with durable budgets."""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from .journal import Journal,atomic_json,identity,utc


class ProcessWatchdog:
    def __init__(self,runtime,command,*,spawn=None,budget=3,window=3600,grace=90,health_timeout=60):
        self.runtime=Path(runtime);self.runtime.mkdir(parents=True,exist_ok=True)
        self.command=list(command);self.spawn=spawn or self._spawn
        self.budget=budget;self.window=window;self.grace=grace;self.health_timeout=health_timeout
        self.journal=Journal(self.runtime/'watchdog.db')
        self.child=None;self.boot_id=None;self.started=None;self.blocked=False
        self._owner_file=None

    def _claim_owner(self):
        if self._owner_file:return
        handle=(self.runtime/'watchdog.lock').open('a+b')
        handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            handle.close();raise RuntimeError('another watchdog owns this runtime')
        self._owner_file=handle

    def close(self):
        self.stop()
        if self._owner_file:self._owner_file.close();self._owner_file=None

    def _spawn(self,env):
        return subprocess.Popen(self.command,env=env,stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

    def _launch(self,now):
        # Persist an attempted launch before spawning. Crashes cannot reset the budget.
        attempts=[t for t in self.journal.state('launch_attempts',[]) if t>=now-self.window]
        if len(attempts)>=self.budget:
            self.blocked=True
            atomic_json(self.runtime/'watchdog_status.json',{'state':'MANUAL_INTERVENTION_REQUIRED','timestamp':utc().isoformat(),'execution':'DISABLED'})
            return False
        self.journal.save('launch_attempts',attempts+[now])
        self.boot_id=uuid.uuid4().hex;self.started=now
        env=dict(os.environ,WAVERUN_BOOT_ID=self.boot_id,WAVERUN_EXECUTION='DISABLED')
        self.child=self.spawn(env)
        atomic_json(self.runtime/'collector_process.json',{'boot_id':self.boot_id,'pid':self.child.pid,'started_at':now,'execution':'DISABLED'})
        return True

    def stop(self):
        child=self.child
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)
        self.child=None

    def step(self,now=None):
        self._claim_owner()
        now=time.time() if now is None else now
        if self.blocked:return 'MANUAL_INTERVENTION_REQUIRED'
        if self.child is None:return 'STARTED' if self._launch(now) else 'MANUAL_INTERVENTION_REQUIRED'
        reason='CHILD_EXITED' if self.child.poll() is not None else None
        try:request=json.loads((self.runtime/'restart_request.json').read_text())
        except (OSError,ValueError):request={}
        if request.get('boot_id')==self.boot_id:
            request_id=request.get('request_id')
            if request_id and request_id!=self.journal.state('handled_request'):
                reason='CONTROLLED_RESTART_REQUEST'
                self.journal.save('handled_request',request_id)
        if not reason and now-self.started>=self.grace:
            try:
                health=json.loads((self.runtime/'health.json').read_text())
                age=now-utc(health['server_time']).timestamp()
                valid=health.get('boot_id')==self.boot_id and 0<=age<=self.health_timeout
            except (OSError,ValueError,KeyError,TypeError):valid=False
            if not valid:reason='HEALTH_WRITER_STALLED'
        if reason:
            self.journal.append('restart',identity(self.boot_id,reason),utc(),{'reason':reason,'boot_id':self.boot_id})
            self.stop()
            return 'RESTARTED' if self._launch(now) else 'MANUAL_INTERVENTION_REQUIRED'
        return 'RUNNING'
