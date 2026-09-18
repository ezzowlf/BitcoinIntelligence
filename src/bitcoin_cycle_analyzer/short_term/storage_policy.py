"""Conservative storage tiers: verified copies, permanent event pins, no P0 deletion."""
from __future__ import annotations

import bisect
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .archive import expire_archive,retain_segment
from .journal import atomic_json,identity,utc


@dataclass(frozen=True)
class StoragePolicy:
    hot_seconds:int=86400
    # Measured 2026-09-17: raw wire-stream compression alone runs ~118MB/day
    # (avg ~82KB compressed per 60s segment) - already the whole storage
    # gate's ~100MB/24h TOTAL budget by itself. A 7-day archive-retention
    # window would hold ~7x that resident before self-offsetting at steady
    # state; the minimum viable value given hot_seconds<=warm_seconds keeps
    # the non-event working set (and the one-time ramp to steady-state net-
    # zero growth) as small as the pin-window mechanics allow.
    warm_seconds:int=86400
    notice:float=.70
    warning:float=.80
    high:float=.90
    critical:float=.95
    reserve_bytes:int=5_000_000_000
    journal_retention_seconds:int=14*86400
    # Quotes only have to outlive the longest outcome horizon (3600s) plus the
    # resolution grace; 2 days is generous and still bounded. Never applied
    # ahead of an open observation - see prune_side_tables().
    quote_retention_seconds:int=2*86400

    def __post_init__(self):
        if not 0<self.notice<self.warning<self.high<self.critical<1:raise ValueError('invalid disk thresholds')
        if not 0<self.hot_seconds<=self.warm_seconds:raise ValueError('invalid retention intervals')


class StorageMaintenance:
    # Raw-segment pin windows (-600s/+1800s, see index_pins/_pin_index below) are
    # meant to preserve market context around genuinely rare, meaningful events.
    # 'candidate' and 'decision' are journaled on every evaluated second (near-
    # continuous during market hours), not on a rare event - including them here
    # made their 40-minute windows overlap end-to-end, so every raw segment was
    # permanently "pinned" and redundant_raw_removed stayed 0 forever (measured
    # 2026-09-17: 6176 manifests / 19GB raw/, zero deletions). They remain in
    # PRUNABLE_KINDS below for the existing journal.prune() retention window;
    # only their raw-segment-pinning role is removed. signal_transition (actual
    # state changes), move/missed_move/false_warning/incident/feed_lifecycle
    # stay - those are the rare events raw context is meant for.
    EVENT_KINDS=('signal_transition','move','missed_move','false_warning','incident','feed_lifecycle')
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

    def __init__(self,root,journal,outcomes,policy=None,*,expire_archives_dry_run=False):
        self.root=Path(root);self.journal=journal;self.outcomes=outcomes;self.policy=policy or StoragePolicy()
        # dry_run=True (see run()) reports what full-archive expiry WOULD delete
        # without touching disk - used to preview impact on an existing backlog
        # before enabling live deletion.
        self.expire_archives_dry_run=expire_archives_dry_run
        with journal.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS raw_event_pins(id TEXT PRIMARY KEY,start REAL NOT NULL,end REAL NOT NULL,kind TEXT NOT NULL)')
        # In-memory cache of parsed manifests keyed by path, invalidated by
        # mtime. Root cause fixed 2026-09-14: run() used to do
        # json.loads(path.read_text()) for every manifest on every pass
        # (61.5s steady-state at ~2,000 manifests - longer than the archiver's
        # own 60s scheduling interval, and growing with archive volume). Once a
        # manifest's content is known and its mtime hasn't changed since, disk
        # is never re-read for it - only a cheap stat() confirms nothing moved.
        # Purely a process-local performance cache: an empty cache (cold start,
        # restart) falls back to reading everything, identical to the
        # unoptimized behavior, so crash-safety and restart-safety are
        # unaffected. Manifests no longer on disk are dropped from the cache.
        self._manifest_cache={}

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

    def prune_side_tables(self,now=None,limit=20000):
        """Bound the two tables nothing else ever deleted from.

        `quotes` grows one row per Vantage tick forever and `raw_event_pins` one
        row per pinned event forever; on the 7-day production audit they held
        235k and 423k rows with no retention path at all. Quotes are only needed
        until every observation that could read them has resolved, so the cutoff
        never crosses an open outcome's floor. A pin only protects raw segments,
        so once no raw can still exist for its window it protects nothing.
        """
        now=utc(now);p=self.policy
        quote_cutoff=now.timestamp()-p.quote_retention_seconds
        floor=self.outcomes.pending_floor()
        if floor is not None:quote_cutoff=min(quote_cutoff,floor)
        pin_cutoff=now.timestamp()-p.warm_seconds
        observation_cutoff=now.timestamp()-p.journal_retention_seconds
        with self.journal.connect() as db:
            # The quote/observation tables belong to OutcomeEngine, which may not
            # have initialised them yet on a brand-new database.
            present={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'quotes' in present:
                db.execute('DELETE FROM quotes WHERE t IN (SELECT t FROM quotes WHERE t<? LIMIT ?)',(quote_cutoff,limit))
            db.execute('DELETE FROM raw_event_pins WHERE id IN (SELECT id FROM raw_event_pins WHERE end<? LIMIT ?)',(pin_cutoff,limit))
            # Settled observations and their results follow the same retention
            # window as the journal telemetry they belong to. PENDING is never
            # touched - an unresolved outcome must survive any retention pass.
            if 'observations' in present:
                db.execute('''DELETE FROM observations WHERE (id,horizon) IN (
                    SELECT id,horizon FROM observations WHERE status<>'PENDING' AND t<? LIMIT ?)''',(observation_cutoff,limit))
            if 'observation_outcomes' in present:
                db.execute('''DELETE FROM observation_outcomes WHERE (id,horizon) IN (
                    SELECT id,horizon FROM observation_outcomes WHERE resolved_at<? LIMIT ?)''',(observation_cutoff,limit))

    def pinned(self,start,end):
        with self.journal.connect() as db:
            return db.execute('SELECT 1 FROM raw_event_pins WHERE start<=? AND end>=? LIMIT 1',(end,start)).fetchone() is not None

    def _pin_index(self):
        """One query loading every pin window, instead of one connect+query per
        manifest (was O(n) SQLite round-trips per maintenance pass - 2,082
        connections / 89s for 2,055 manifests in production, longer than the
        60s maintenance interval itself). Returns pins sorted by start plus a
        running prefix-max of `end`, so each manifest's overlap check is an
        O(log n) bisect instead of a DB round-trip. Same overlap semantics as
        pinned(): a pin matches if pin.start<=query_end AND pin.end>=query_start.
        """
        with self.journal.connect() as db:
            rows=db.execute('SELECT start,end FROM raw_event_pins ORDER BY start').fetchall()
        starts=[r[0] for r in rows];ends=[r[1] for r in rows]
        prefix_max=[]
        running=float('-inf')
        for e in ends:
            running=max(running,e);prefix_max.append(running)
        return starts,prefix_max

    @staticmethod
    def _pin_overlaps(index,start,end):
        starts,prefix_max=index
        if not starts:return False
        idx=bisect.bisect_right(starts,end)  # candidates: starts[0:idx], all have start<=end
        if idx==0:return False
        return prefix_max[idx-1]>=start  # max end among candidates still needs end>=start

    def run(self,now=None,limit=32):
        now=utc(now);p=self.policy
        self.journal.prune(self.PRUNABLE_KINDS,now.timestamp()-p.journal_retention_seconds)
        self.prune_side_tables(now)
        pins_ready=self.index_pins()
        pin_index=self._pin_index()
        disk=shutil.disk_usage(self.root);used=disk.used/disk.total
        tier='CRITICAL' if used>=p.critical else 'HIGH' if used>=p.high else 'WARNING' if used>=p.warning else 'NOTICE' if used>=p.notice else 'OK'
        floor=self.outcomes.pending_floor()
        raw_total=0;compressed_total=0;start=None;end=None
        # Manifests are tiny. Verification/deletion is bounded per pass.
        deleted=0;archives_deleted=0;archives_expirable_dry_run=0
        cache=self._manifest_cache;seen=set()
        for path in self.root.glob('*.manifest.json'):
            key=str(path);seen.add(key)
            try:mtime_ns=path.stat().st_mtime_ns
            except FileNotFoundError:continue  # deleted between glob() and stat()
            cached=cache.get(key)
            if cached is not None and cached[0]==mtime_ns:
                m=cached[1]
            else:
                m=json.loads(path.read_text());cache[key]=(mtime_ns,m)
            raw_total+=m['raw_bytes'];compressed_total+=m['compressed_bytes']
            start=m['start'] if start is None else min(start,m['start']);end=m['end'] if end is None else max(end,m['end'])
            pin=self._pin_overlaps(pin_index,m['start'],m['end'])
            age=now.timestamp()-m['end'];storage_tier='HOT' if age<p.hot_seconds else 'WARM' if age<p.warm_seconds else 'COLD'
            priority='P1' if pin else m.get('priority','P2')
            if priority=='P0':storage_tier='P0_PERMANENT'
            if m.get('storage_tier')!=storage_tier or m.get('event_window_pinned')!=pin:
                m.update(storage_tier=storage_tier,event_window_pinned=pin,effective_priority=priority)
                atomic_json(path,m);cache[key]=(path.stat().st_mtime_ns,m)
            if pins_ready and deleted<limit and priority not in {'P0','P1'} and age>=p.hot_seconds and (self.root/m['raw_filename']).exists():
                if retain_segment(path.with_name(m['filename']),now=now,hot_seconds=p.hot_seconds,pending_floor=floor):deleted+=1
            # Full archive expiry: an unpinned, WARM-aged compressed segment is
            # market noise that nothing ever tied to a real signal - the raw
            # .jsonl above is already gone by this point, so the .parquet+
            # manifest pair is the only thing left to reclaim. dry_run mode
            # (see __init__) reports what this WOULD remove without deleting,
            # so an existing backlog's impact can be previewed before enabling
            # live deletion.
            if pins_ready and archives_deleted<limit and priority not in {'P0','P1'} and age>=p.warm_seconds and path.exists():
                if self.expire_archives_dry_run:
                    if expire_archive(path.with_name(m['filename']),now=now,warm_seconds=p.warm_seconds,pending_floor=floor,dry_run=True):
                        archives_expirable_dry_run+=1
                elif expire_archive(path.with_name(m['filename']),now=now,warm_seconds=p.warm_seconds,pending_floor=floor):
                    archives_deleted+=1
        for key in list(cache):
            if key not in seen:del cache[key]  # manifest no longer on disk
        period=end-start if start is not None and end is not None else 0
        raw_day=raw_total/period*86400 if period>0 else None
        compressed_day=compressed_total/period*86400 if period>0 else None
        reserve=max(p.reserve_bytes,(1-p.critical)*disk.total)
        result={'timestamp':now.isoformat(),'total':disk.total,'used':disk.used,'free':disk.free,'tier':tier,'raw_growth_day':raw_day,'compressed_growth_day':compressed_day,'compression_ratio':raw_total/compressed_total if compressed_total else None,'remaining_days':max(0,disk.free-reserve)/compressed_day if compressed_day else None,'redundant_raw_removed':deleted,'new_signals_allowed':tier not in {'HIGH','CRITICAL'},'raw_archives_deleted':archives_deleted,'raw_archives_expirable_dry_run':archives_expirable_dry_run,'execution':'DISABLED'}
        atomic_json(self.root.parent/'storage_health.json',result)
        if tier!=self.journal.state('disk_tier'):
            self.journal.append('incident',identity('disk',tier,now),now,{'reason':'DISK_'+tier,'free':disk.free},state_updates={'disk_tier':tier})
        return result
