"""Causal executable-side outcomes. Missing paths are explicit, never losses."""
from __future__ import annotations

import json
import math
import sqlite3
from bisect import bisect_left,bisect_right
from datetime import UTC,datetime,timedelta

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
        self.register_many(((id,kind,timestamp,direction,bid,ask,invalidation,horizons,payload),))

    def register_many(self, registrations):
        """Register related observations through one bounded journal commit."""
        registrations=tuple(registrations)
        if not registrations:
            return
        rows=[]
        for id,kind,timestamp,direction,bid,ask,invalidation,horizons,payload in registrations:
            t=utc(timestamp).timestamp()
            if direction not in {'LONG','SHORT','NONE'}:raise ValueError('invalid direction')
            rows.append((id,kind,t,direction,bid,ask,invalidation,tuple(horizons),payload))
        with self.journal.connect() as db:
            pending=[]
            for id,kind,t,direction,bid,ask,invalidation,horizons,payload in rows:
                if bid is None or ask is None:
                    quote=db.execute('SELECT t,bid,ask FROM quotes WHERE t<=? ORDER BY t DESC LIMIT 1',(t,)).fetchone()
                    if quote and t-quote[0]<=self.max_gap:_,bid,ask=quote
                encoded=json.dumps(payload or {},sort_keys=True,default=str)
                pending.extend((id,kind,t,h,direction,bid,ask,invalidation,encoded,t+h) for h in horizons)
            db.executemany('INSERT OR IGNORE INTO observations(id,kind,t,horizon,direction,bid,ask,invalidation,payload,due_at) VALUES(?,?,?,?,?,?,?,?,?,?)',pending)

    def resolve_due(self,now,limit=1000,heartbeat_seconds=2.0):
        """Root cause fixed 2026-09-14: the outcome_scheduler heartbeat mark was
        only written once, after the *entire* batch (up to `limit` rows)
        finished. health_supervisor.py reports outcome_scheduler=OFFLINE purely
        from that mark's age (resilience.CONFIG.decision_offline_after=600s).
        A single legitimately large due-observation backlog (e.g. after a
        restart, or a burst of expiring horizons) processed in one call could
        therefore make a genuinely alive, working scheduler read as OFFLINE for
        the whole batch duration. Marking progress periodically *during* the
        loop (every `heartbeat_seconds` of wall-clock time, not every row -
        cheap regardless of row count) proves real liveness without changing
        resolution logic, outcome status semantics, or the final mark."""
        import time as _time
        wall=utc(now).timestamp();resolved=[];last_heartbeat=_time.monotonic()
        started=last_heartbeat
        # Read the bounded input set first and release the journal lock before
        # evaluating it.  SQLite permits one writer, and holding Journal's
        # in-process writer gate while calculating a large overdue batch made
        # every feed consumer wait behind outcome resolution.  That was the
        # direct cause of the apparently "stale" decision pipeline.
        with self.journal.connect() as db:
            rows=db.execute("SELECT id,kind,t,horizon,direction,bid,ask,invalidation,payload FROM observations WHERE status='PENDING' AND due_at<=? ORDER BY due_at LIMIT ?",(wall-self.grace,limit)).fetchall()
            paths=None;path_times=[]
            if rows:
                first=min(row[2] for row in rows);last=max(row[2]+row[3] for row in rows)
                if last-first<=7200:
                    paths=db.execute('SELECT t,bid,ask FROM quotes WHERE t>=? AND t<=? ORDER BY t',(first,last)).fetchall()
                    path_times=[row[0] for row in paths]
        pending_writes=[]

        def commit_results():
            if not pending_writes:return
            batch=tuple(pending_writes)
            pending_writes.clear()
            # Keep the only write transaction bounded to the three atomic
            # result-state-outbox updates.  The records were calculated from a
            # stable snapshot above; INSERT OR IGNORE keeps restart delivery
            # idempotent if another recovery path completed one meanwhile.
            with self.journal.connect() as db:
                db.executemany('INSERT OR IGNORE INTO observation_outcomes VALUES(?,?,?,?,?)',
                    [(i,h,s,wall,p) for i,h,s,p in batch])
                db.executemany('UPDATE observations SET status=? WHERE id=? AND horizon=?',
                    [(s,i,h) for i,h,s,p in batch])
                db.executemany('INSERT OR IGNORE INTO outcome_outbox VALUES(?,?,?)',
                    [(i,h,p) for i,h,s,p in batch])

        for id,kind,t,h,direction,bid,ask,stop,payload in rows:
            if len(pending_writes)>=25:commit_results()
            if _time.monotonic()-last_heartbeat>=heartbeat_seconds:
                commit_results()
                heartbeat=utc(now)+timedelta(seconds=_time.monotonic()-started)
                self.journal.mark('outcome_scheduler',identity('scheduler',wall,len(resolved)),heartbeat,committed_at=heartbeat)
                last_heartbeat=_time.monotonic()
            entry=ask if direction=='LONG' else bid
            # These terminal states never inspect quotes. Avoid reading a
            # potentially hour-long path whose result would be discarded.
            quotes=[]
            if direction!='NONE' and entry is not None and math.isfinite(entry) and entry>0:
                if paths is not None:
                    quotes=paths[bisect_left(path_times,t):bisect_right(path_times,t+h)]
                else:
                    # A read-only connection is intentionally not routed
                    # through Journal.connect(): this uncommon wide batch must
                    # not block the feed writers while it is evaluated.
                    read_db=sqlite3.connect(self.journal.path.as_uri()+'?mode=ro',uri=True,timeout=.2)
                    try:quotes=read_db.execute('SELECT t,bid,ask FROM quotes WHERE t>=? AND t<=? ORDER BY t',(t,t+h)).fetchall()
                    finally:read_db.close()
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
            pending_writes.append((id,h,status,json.dumps(result,sort_keys=True)))
            resolved.append(result)
        commit_results()
        # Both result and terminal observation state have committed before progress.
        self.flush_outbox()
        heartbeat=utc(now)+timedelta(seconds=_time.monotonic()-started)
        self.journal.mark('outcome_scheduler',identity('scheduler',wall,'complete'),heartbeat,committed_at=heartbeat)
        return resolved

    def flush_outbox(self,limit=1000):
        """At-least-once delivery, idempotent event IDs, acknowledgment after commit."""
        with self.journal.connect() as db:
            pending=db.execute('SELECT id,horizon,payload FROM outcome_outbox ORDER BY rowid LIMIT ?',(limit,)).fetchall()
        # Commit each bounded group atomically: results and acknowledgments
        # either both persist or both roll back. IDs remain idempotent.
        for offset in range(0,len(pending),100):
            with self.journal.connect() as db:
                for id,h,payload in pending[offset:offset+100]:
                    row=json.loads(payload);now=row['resolved_at']
                    self.journal.append('outcome',identity(id,h),now,row,stage='outcomes',connection=db)
                    if row['kind']=='PREWARNING' and row['horizon_seconds']==300 and row['status']=='RESOLVED' and not row['targets']['100']['hit']:
                        self.journal.append('false_warning',row['id'],now,row,connection=db)
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
