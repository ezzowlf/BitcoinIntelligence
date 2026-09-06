"""Causal executable-side outcomes. Missing paths are explicit, never losses."""
from __future__ import annotations

import json
import math
from datetime import UTC,datetime

from .journal import Journal,identity,utc

HORIZONS=(30,60,120,180,300,600,900,1800,3600)
TARGETS=(100,150,200,300,500)
TERMINAL={'RESOLVED','INSUFFICIENT_FUTURE_DATA','INVALID_DATA','CANCELLED'}


class OutcomeEngine:
    def __init__(self,journal:Journal,max_gap=5.0,grace=5.0):
        self.journal=journal;self.max_gap=max_gap;self.grace=grace
        with journal.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS quotes(t REAL PRIMARY KEY,bid REAL NOT NULL,ask REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS observations(
                    id TEXT NOT NULL,kind TEXT NOT NULL,t REAL NOT NULL,horizon INTEGER NOT NULL,
                    direction TEXT NOT NULL,bid REAL,ask REAL,invalidation REAL,
                    status TEXT NOT NULL DEFAULT 'PENDING',payload TEXT NOT NULL,due_at REAL NOT NULL,
                    PRIMARY KEY(id,horizon));
                CREATE INDEX IF NOT EXISTS due_observations ON observations(status,due_at);
                CREATE TABLE IF NOT EXISTS observation_outcomes(
                    id TEXT NOT NULL,horizon INTEGER NOT NULL,status TEXT NOT NULL,
                    resolved_at REAL NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(id,horizon));
                CREATE TABLE IF NOT EXISTS outcome_outbox(
                    id TEXT NOT NULL,horizon INTEGER NOT NULL,payload TEXT NOT NULL,
                    PRIMARY KEY(id,horizon));
            ''')

    def quote(self,timestamp,bid,ask):
        t=utc(timestamp).timestamp()
        if not all(math.isfinite(float(v)) and float(v)>0 for v in (bid,ask)) or bid>ask:raise ValueError('invalid Vantage bid/ask')
        with self.journal.connect() as db:db.execute('INSERT OR IGNORE INTO quotes VALUES(?,?,?)',(t,bid,ask))

    def register(self,id,kind,timestamp,direction,*,bid=None,ask=None,invalidation=None,horizons=HORIZONS,payload=None):
        t=utc(timestamp).timestamp()
        if direction not in {'LONG','SHORT','NONE'}:raise ValueError('invalid direction')
        with self.journal.connect() as db:
            if bid is None or ask is None:
                row=db.execute('SELECT t,bid,ask FROM quotes WHERE t<=? ORDER BY t DESC LIMIT 1',(t,)).fetchone()
                if row and t-row[0]<=self.max_gap:_,bid,ask=row
            db.executemany('INSERT OR IGNORE INTO observations(id,kind,t,horizon,direction,bid,ask,invalidation,payload,due_at) VALUES(?,?,?,?,?,?,?,?,?,?)',[(id,kind,t,h,direction,bid,ask,invalidation,json.dumps(payload or {},sort_keys=True,default=str),t+h) for h in horizons])

    def resolve_due(self,now,limit=1000):
        wall=utc(now).timestamp();resolved=[]
        with self.journal.connect() as db:
            rows=db.execute("SELECT id,kind,t,horizon,direction,bid,ask,invalidation,payload FROM observations WHERE status='PENDING' AND due_at<=? ORDER BY due_at LIMIT ?",(wall-self.grace,limit)).fetchall()
            for id,kind,t,h,direction,bid,ask,stop,payload in rows:
                entry=ask if direction=='LONG' else bid
                quotes=db.execute('SELECT t,bid,ask FROM quotes WHERE t>=? AND t<=? ORDER BY t',(t,t+h)).fetchall()
                result={'id':id,'kind':kind,'observation':json.loads(payload),'horizon_seconds':h,'actual_return':None,'mfe':None,'mae':None,'executable_outcome':None,'resolved_at':datetime.fromtimestamp(wall,UTC).isoformat(),'data_completeness':False,'execution':'DISABLED'}
                if direction=='NONE':status='CANCELLED'
                elif entry is None or not math.isfinite(entry) or entry<=0:status='INVALID_DATA'
                elif not quotes:status='INSUFFICIENT_FUTURE_DATA'
                else:
                    gaps=[quotes[0][0]-t,t+h-quotes[-1][0]]+[b[0]-a[0] for a,b in zip(quotes,quotes[1:])]
                    complete=max(gaps)<=self.max_gap
                    status='RESOLVED' if complete else 'INSUFFICIENT_FUTURE_DATA'
                    result['max_gap_seconds']=max(gaps)
                    if complete:
                        sign=1 if direction=='LONG' else -1
                        exits=[q[1] if direction=='LONG' else q[2] for q in quotes]
                        pnl=[sign*(p-entry) for p in exits]
                        stop_i=next((i for i,p in enumerate(exits) if stop is not None and (p<=stop if direction=='LONG' else p>=stop)),None)
                        targets={}
                        for target in TARGETS:
                            hit=next((i for i,p in enumerate(pnl) if p>=target),None)
                            targets[str(target)]={'hit':hit is not None,'time_seconds':quotes[hit][0]-t if hit is not None else None,'before_invalidation':hit is not None and (stop_i is None or hit<stop_i)}
                        result.update(actual_return=pnl[-1]/entry,mfe=max(pnl)/entry,mae=min(pnl)/entry,mfe_usd=max(pnl),mae_usd=min(pnl),executable_outcome=pnl[-1],entry=entry,entry_side='ASK' if direction=='LONG' else 'BID',exit_side='BID' if direction=='LONG' else 'ASK',endpoint_time=quotes[-1][0],direction_correct=pnl[-1]>0,targets=targets,invalidation_hit=stop_i is not None,data_completeness=True)
                result['status']=status
                db.execute('INSERT OR IGNORE INTO observation_outcomes VALUES(?,?,?,?,?)',(id,h,status,wall,json.dumps(result,sort_keys=True)))
                db.execute('UPDATE observations SET status=? WHERE id=? AND horizon=?',(status,id,h))
                db.execute('INSERT OR IGNORE INTO outcome_outbox VALUES(?,?,?)',(id,h,json.dumps(result,sort_keys=True)))
                resolved.append(result)
        # Both result and terminal observation state have committed before progress.
        self.flush_outbox()
        self.journal.mark('outcome_scheduler',identity('scheduler',wall),now,committed_at=now)
        return resolved

    def flush_outbox(self,limit=1000):
        """At-least-once delivery, idempotent event IDs, acknowledgment after commit."""
        with self.journal.connect() as db:
            pending=db.execute('SELECT id,horizon,payload FROM outcome_outbox ORDER BY rowid LIMIT ?',(limit,)).fetchall()
        for id,h,payload in pending:
            row=json.loads(payload);now=row['resolved_at']
            self.journal.append('outcome',identity(id,h),now,row,stage='outcomes')
            if row['kind']=='PREWARNING' and row['horizon_seconds']==300 and row['status']=='RESOLVED' and not row['targets']['100']['hit']:
                self.journal.append('false_warning',row['id'],now,row)
            with self.journal.connect() as db:
                db.execute('DELETE FROM outcome_outbox WHERE id=? AND horizon=?',(id,h))

    def pending_floor(self):
        with self.journal.connect() as db:return db.execute("SELECT MIN(t) FROM observations WHERE status='PENDING'").fetchone()[0]

    def catch_up_registrations(self,limit=256):
        cursor=self.journal.state('outcome_transition_cursor',0)
        for event in self.journal.rows('signal_transition',after=cursor,limit=limit):
            row=event['payload'];state=row['state_to']
            if state in {'CANDIDATE','PREWARNING','ARMED','LIVE'}:
                zone=row.get('entry_zone') or [None,None]
                self.register(event['id'],state,row['timestamp'],row['direction'],bid=zone[0],ask=zone[1],invalidation=row.get('invalidation'),payload={'setup_id':row['setup_id'],'version':row['signal_version']})
            self.journal.save('outcome_transition_cursor',event['seq'])
