"""Durable P0 events and causal progress, independent of raw-file retention."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
import time
import logging
import traceback
import threading
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path


def utc(value=None):
    if value is None:return datetime.now(UTC)
    if isinstance(value,datetime):return value.astimezone(UTC)
    return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(UTC)


def identity(*parts):
    return hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()


def atomic_json(path, payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    with temp.open('w',encoding='utf8') as f:
        json.dump(payload,f,sort_keys=True,default=str);f.flush();os.fsync(f.fileno())
    for attempt in range(6):
        try:
            os.replace(temp,path)
            break
        except PermissionError as exc:
            if getattr(exc,'winerror',None) not in (5,32,33) or attempt==5:
                raise
            time.sleep(.01*(attempt+1))


class Journal:
    # SQLite permits one writer.  The collector deliberately has several
    # independent workers (raw storage, outcome resolution, Vantage and event
    # consumers), so relying on SQLite's busy retries turned a brief write into
    # many five-second stalls.  Coordinate writers in-process before opening a
    # transaction.  Locks are per resolved database path so independently
    # constructed Journal objects still cooperate.
    _locks_guard = threading.Lock()
    _locks: dict[str, threading.RLock] = {}

    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        key=str(self.path.resolve()).casefold()
        with self._locks_guard:
            self._lock=self._locks.setdefault(key,threading.RLock())
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            # Only takes effect on a brand-new/empty database file; a no-op on an
            # existing one. Lets bounded retention (Journal.prune) actually
            # shrink the file over time via incremental_vacuum instead of a full
            # VACUUM (which needs ~the whole file's size again in free disk).
            db.execute('PRAGMA auto_vacuum=INCREMENTAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    id TEXT NOT NULL, timestamp REAL NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(kind,id));
                CREATE INDEX IF NOT EXISTS events_time ON events(kind,timestamp);
                CREATE INDEX IF NOT EXISTS events_kind_seq ON events(kind,seq);
                CREATE TABLE IF NOT EXISTS progress(
                    stage TEXT PRIMARY KEY, seq INTEGER NOT NULL, event_at REAL NOT NULL,
                    committed_at REAL NOT NULL, cause_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        # WAL mode + NORMAL sync is SQLite's own recommended pairing: a commit is
        # still durable against a process crash (the WAL is replayed), only the
        # very last transaction can be lost on an OS-level crash/power-loss - an
        # acceptable trade for a rebuildable progress journal on an
        # observation-only system. FULL added an fsync per commit that, under the
        # dozens of concurrent short-lived writers this journal actually has
        # (per-worker consumers, outcome scheduler, raw writer/archiver, vantage
        # recorder, health supervisor), was the dominant source of the
        # "database is locked" OperationalError storms seen in production. A
        # longer busy-timeout (5s vs 1s) gives SQLite's own retry loop more room
        # before surfacing that as an error at all.
        # Diagnostic-only split of wait-for-lock vs. actual DB work, to prove
        # (not guess) whether contention or commit latency dominates. Cheap
        # (2 extra monotonic() reads); logged only above WAVERUN_JOURNAL_DIAG_MIN_S
        # so normal operation is unaffected once the flag/threshold is removed.
        wait_start=time.monotonic()
        with self._lock:
            acquired_at=time.monotonic()
            db=sqlite3.connect(self.path,timeout=5)
            db.execute('PRAGMA busy_timeout=5000')
            db.execute('PRAGMA synchronous=NORMAL')
            try:
                with db:yield db
            finally:
                db.close()
            released_at=time.monotonic()
        wait_s=acquired_at-wait_start;hold_s=released_at-acquired_at;elapsed=released_at-wait_start
        diag_min=float(os.environ.get('WAVERUN_JOURNAL_DIAG_MIN_S',0) or 0)
        if diag_min and elapsed>=diag_min:
            logging.getLogger(__name__).warning('journal_diag wait=%.3fs hold=%.3fs total=%.3fs',wait_s,hold_s,elapsed)
        if elapsed>=1:
            logging.getLogger(__name__).warning('Slow journal context %.3fs (wait=%.3fs hold=%.3fs): %s',elapsed,wait_s,hold_s,''.join(traceback.format_stack(limit=5)))

    def append(self,kind,id,timestamp,payload,*,stage=None,cause_id=None,committed_at=None,state_updates=None,connection=None):
        t=utc(timestamp).timestamp();wall=utc(committed_at).timestamp()
        value={**payload,'execution':'DISABLED'}
        with (self.connect() if connection is None else nullcontext(connection)) as db:
            cur=db.execute('INSERT OR IGNORE INTO events(kind,id,timestamp,payload) VALUES(?,?,?,?)',(kind,id,t,json.dumps(value,sort_keys=True,default=str)))
            if cur.rowcount and stage:
                db.execute('''INSERT INTO progress VALUES(?,?,?,?,?) ON CONFLICT(stage) DO UPDATE SET
                    seq=excluded.seq,event_at=excluded.event_at,committed_at=excluded.committed_at,cause_id=excluded.cause_id''',
                    (stage,cur.lastrowid,t,wall,cause_id or id))
            for key,value in (state_updates or {}).items():
                db.execute('INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',(key,json.dumps(value,sort_keys=True,default=str)))
            return cur.rowcount==1

    def append_many(self, entries):
        """Append a causally related group in one SQLite transaction.

        The live evaluator used to open and commit a connection for every
        features/candidate/decision/progress record.  That is needlessly
        expensive on a busy single-writer SQLite journal and can make a live
        trade consumer fall behind although no individual write is faulty.
        Entries use the same fields as :meth:`append`; order is retained and
        all successful entries become durable together.
        """
        inserted=[]
        with self.connect() as db:
            for entry in entries:
                inserted.append(self.append(connection=db, **entry))
        return inserted

    def mark(self,stage,cause_id,event_at,*,committed_at=None):
        return self.append('stage_'+stage,identity(stage,cause_id),event_at,{'cause_id':cause_id},stage=stage,cause_id=cause_id,committed_at=committed_at)

    def mark_on(self,db,stage,cause_id,event_at,*,committed_at=None):
        """Same effect as mark(), but writes through a connection the caller
        already holds open instead of opening a new one. For a caller running a
        long transaction on its own connection (e.g. OutcomeEngine.resolve_due
        processing a large due-observation batch), calling mark() there would
        open a second writer connection while the first's transaction is still
        open, contending for the same write lock. Caller is responsible for
        committing db afterward."""
        t=utc(event_at).timestamp();wall=utc(committed_at).timestamp()
        kind='stage_'+stage;id=identity(stage,cause_id)
        payload=json.dumps({'cause_id':cause_id,'execution':'DISABLED'},sort_keys=True,default=str)
        cur=db.execute('INSERT OR IGNORE INTO events(kind,id,timestamp,payload) VALUES(?,?,?,?)',(kind,id,t,payload))
        if cur.rowcount:
            db.execute('''INSERT INTO progress VALUES(?,?,?,?,?) ON CONFLICT(stage) DO UPDATE SET
                seq=excluded.seq,event_at=excluded.event_at,committed_at=excluded.committed_at,cause_id=excluded.cause_id''',
                (stage,cur.lastrowid,t,wall,cause_id))
        return cur.rowcount==1

    def state(self,key,default=None):
        with self.connect() as db:r=db.execute('SELECT payload FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default

    def prune(self,kinds,before_timestamp,*,limit=5000,vacuum_pages=64):
        """Bounded retention delete for the highest-volume telemetry kinds
        (outcome/candidate/decision/features/stage_*). Never touches 'incident',
        'signal_transition' or anything not explicitly listed - those stay for
        audit history. Deletes at most `limit` rows per kind per call so this is
        safe to run from a periodic maintenance loop without a long transaction.
        Returns the number of rows deleted. auto_vacuum=INCREMENTAL (set at
        table creation on a fresh DB) lets a small incremental_vacuum actually
        shrink the file instead of just freeing internal pages for reuse."""
        deleted=0
        with self.connect() as db:
            for kind in kinds:
                cur=db.execute('DELETE FROM events WHERE seq IN (SELECT seq FROM events WHERE kind=? AND timestamp<? LIMIT ?)',(kind,before_timestamp,limit))
                deleted+=cur.rowcount
            if deleted:db.execute(f'PRAGMA incremental_vacuum({vacuum_pages})')
        return deleted

    def save(self,key,value):
        with self.connect() as db:db.execute('INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',(key,json.dumps(value,sort_keys=True,default=str)))

    def rows(self,kind,*,start=None,end=None,after=0,limit=10000):
        query='SELECT seq,id,timestamp,payload FROM events WHERE kind=? AND seq>?';args=[kind,after]
        if start is not None:query+=' AND timestamp>=?';args.append(utc(start).timestamp())
        if end is not None:query+=' AND timestamp<=?';args.append(utc(end).timestamp())
        query+=' ORDER BY seq LIMIT ?';args.append(limit)
        with self.connect() as db:rows=db.execute(query,args).fetchall()
        return [dict(seq=s,id=i,timestamp=t,payload=json.loads(p)) for s,i,t,p in rows]

    @staticmethod
    def state_at(path,key,default=None):
        """Read-only, connection-pooling-free lookup of a single `state` row,
        for a reader process (e.g. the web API) that must never contend with
        the collector's own writer connection - mirrors progress_at()'s
        read-only/short-timeout pattern rather than opening a normal
        read-write connect() like the instance method state() does."""
        path=Path(path)
        if not path.exists():return default
        try:
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2)
            try:row=db.execute('SELECT payload FROM state WHERE key=?',(key,)).fetchone()
            finally:db.close()
            return json.loads(row[0]) if row else default
        except sqlite3.Error:return default

    @staticmethod
    def progress_at(path):
        path=Path(path)
        if not path.exists():return {}
        try:
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2)
            try:rows=db.execute('SELECT stage,seq,event_at,committed_at,cause_id FROM progress').fetchall()
            finally:db.close()
            return {s:dict(seq=n,event_at=t,committed_at=w,cause_id=c) for s,n,t,w,c in rows}
        except sqlite3.Error:return {}
