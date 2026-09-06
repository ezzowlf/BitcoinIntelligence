"""Durable P0 events and causal progress, independent of raw-file retention."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
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
    os.replace(temp,path)


class Journal:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    id TEXT NOT NULL, timestamp REAL NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(kind,id));
                CREATE INDEX IF NOT EXISTS events_time ON events(kind,timestamp);
                CREATE TABLE IF NOT EXISTS progress(
                    stage TEXT PRIMARY KEY, seq INTEGER NOT NULL, event_at REAL NOT NULL,
                    committed_at REAL NOT NULL, cause_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=1)
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:yield db
        finally:db.close()

    def append(self,kind,id,timestamp,payload,*,stage=None,cause_id=None,committed_at=None,state_updates=None):
        t=utc(timestamp).timestamp();wall=utc(committed_at).timestamp()
        value={**payload,'execution':'DISABLED'}
        with self.connect() as db:
            cur=db.execute('INSERT OR IGNORE INTO events(kind,id,timestamp,payload) VALUES(?,?,?,?)',(kind,id,t,json.dumps(value,sort_keys=True,default=str)))
            if cur.rowcount and stage:
                db.execute('''INSERT INTO progress VALUES(?,?,?,?,?) ON CONFLICT(stage) DO UPDATE SET
                    seq=excluded.seq,event_at=excluded.event_at,committed_at=excluded.committed_at,cause_id=excluded.cause_id''',
                    (stage,cur.lastrowid,t,wall,cause_id or id))
            for key,value in (state_updates or {}).items():
                db.execute('INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload',(key,json.dumps(value,sort_keys=True,default=str)))
            return cur.rowcount==1

    def mark(self,stage,cause_id,event_at,*,committed_at=None):
        return self.append('stage_'+stage,identity(stage,cause_id),event_at,{'cause_id':cause_id},stage=stage,cause_id=cause_id,committed_at=committed_at)

    def state(self,key,default=None):
        with self.connect() as db:r=db.execute('SELECT payload FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(r[0]) if r else default

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
    def progress_at(path):
        path=Path(path)
        if not path.exists():return {}
        try:
            db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2)
            try:rows=db.execute('SELECT stage,seq,event_at,committed_at,cause_id FROM progress').fetchall()
            finally:db.close()
            return {s:dict(seq=n,event_at=t,committed_at=w,cause_id=c) for s,n,t,w,c in rows}
        except sqlite3.Error:return {}
