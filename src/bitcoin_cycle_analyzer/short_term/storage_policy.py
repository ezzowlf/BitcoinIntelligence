"""Conservative storage tiers: verified copies, permanent event pins, no P0 deletion."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .archive import retain_segment
from .journal import atomic_json,identity,utc


@dataclass(frozen=True)
class StoragePolicy:
    hot_seconds:int=86400
    warm_seconds:int=7*86400
    notice:float=.70
    warning:float=.80
    high:float=.90
    critical:float=.95
    reserve_bytes:int=5_000_000_000
    journal_retention_seconds:int=14*86400

    def __post_init__(self):
        if not 0<self.notice<self.warning<self.high<self.critical<1:raise ValueError('invalid disk thresholds')
        if not 0<self.hot_seconds<=self.warm_seconds:raise ValueError('invalid retention intervals')


class StorageMaintenance:
    EVENT_KINDS=('signal_transition','candidate','decision','move','missed_move','false_warning','incident','feed_lifecycle')
    # High-volume, low-long-term-value telemetry: per-evaluation feature/decision
    # snapshots and per-second liveness markers. This is what made journal.db
    # grow unbounded in production (7-day audit, 2026-09-12). 'incident',
    # 'signal_transition', 'false_warning', 'move'/'missed_move' and
    # 'feed_lifecycle' are deliberately excluded - they are the actual audit
    # trail and stay for the journal_retention_seconds window at minimum via
    # normal SQLite storage (no separate pin needed, they're low-volume).
    PRUNABLE_KINDS=('outcome','candidate','decision','features',
        'stage_feed_spot','stage_feed_futures','stage_feed_l2','stage_storage',
        'stage_predictions','stage_vantage','stage_outcome_scheduler')

    def __init__(self,root,journal,outcomes,policy=None):
        self.root=Path(root);self.journal=journal;self.outcomes=outcomes;self.policy=policy or StoragePolicy()
        with journal.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS raw_event_pins(id TEXT PRIMARY KEY,start REAL NOT NULL,end REAL NOT NULL,kind TEXT NOT NULL)')

    def index_pins(self,limit=256):
        caught_up=True
        # Bounded indexed ingestion; never rescan or retain an unbounded Python list.
        for kind in self.EVENT_KINDS:
            cursor=self.journal.state('pin_cursor_'+kind,0)
            rows=self.journal.rows(kind,after=cursor,limit=limit)
            if len(rows)==limit:caught_up=False
            with self.journal.connect() as db:
                for row in rows:
                    t=row['timestamp']
                    db.execute('INSERT OR IGNORE INTO raw_event_pins VALUES(?,?,?,?)',(identity(kind,row['id']),t-600,t+1800,kind))
            if rows:self.journal.save('pin_cursor_'+kind,rows[-1]['seq'])
        return caught_up

    def pinned(self,start,end):
        with self.journal.connect() as db:
            return db.execute('SELECT 1 FROM raw_event_pins WHERE start<=? AND end>=? LIMIT 1',(end,start)).fetchone() is not None

    def run(self,now=None,limit=32):
        now=utc(now);p=self.policy
        self.journal.prune(self.PRUNABLE_KINDS,now.timestamp()-p.journal_retention_seconds)
        pins_ready=self.index_pins()
        disk=shutil.disk_usage(self.root);used=disk.used/disk.total
        tier='CRITICAL' if used>=p.critical else 'HIGH' if used>=p.high else 'WARNING' if used>=p.warning else 'NOTICE' if used>=p.notice else 'OK'
        floor=self.outcomes.pending_floor()
        raw_total=0;compressed_total=0;start=None;end=None
        # Manifests are tiny. Verification/deletion is bounded per pass.
        deleted=0
        for path in self.root.glob('*.manifest.json'):
            m=json.loads(path.read_text());raw_total+=m['raw_bytes'];compressed_total+=m['compressed_bytes']
            start=m['start'] if start is None else min(start,m['start']);end=m['end'] if end is None else max(end,m['end'])
            pin=self.pinned(m['start'],m['end'])
            age=now.timestamp()-m['end'];storage_tier='HOT' if age<p.hot_seconds else 'WARM' if age<p.warm_seconds else 'COLD'
            priority='P1' if pin else m.get('priority','P2')
            if priority=='P0':storage_tier='P0_PERMANENT'
            if m.get('storage_tier')!=storage_tier or m.get('event_window_pinned')!=pin:
                m.update(storage_tier=storage_tier,event_window_pinned=pin,effective_priority=priority)
                atomic_json(path,m)
            if pins_ready and deleted<limit and priority not in {'P0','P1'} and age>=p.hot_seconds and (self.root/m['raw_filename']).exists():
                if retain_segment(path.with_name(m['filename']),now=now,hot_seconds=p.hot_seconds,pending_floor=floor):deleted+=1
        period=end-start if start is not None and end is not None else 0
        raw_day=raw_total/period*86400 if period>0 else None
        compressed_day=compressed_total/period*86400 if period>0 else None
        reserve=max(p.reserve_bytes,(1-p.critical)*disk.total)
        result={'timestamp':now.isoformat(),'total':disk.total,'used':disk.used,'free':disk.free,'tier':tier,'raw_growth_day':raw_day,'compressed_growth_day':compressed_day,'compression_ratio':raw_total/compressed_total if compressed_total else None,'remaining_days':max(0,disk.free-reserve)/compressed_day if compressed_day else None,'redundant_raw_removed':deleted,'new_signals_allowed':tier not in {'HIGH','CRITICAL'},'raw_archives_deleted':0,'execution':'DISABLED'}
        atomic_json(self.root.parent/'storage_health.json',result)
        if tier!=self.journal.state('disk_tier'):
            self.journal.append('incident',identity('disk',tier,now),now,{'reason':'DISK_'+tier,'free':disk.free},state_updates={'disk_tier':tier})
        return result
