import json
import time
from datetime import UTC,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from bitcoin_cycle_analyzer.short_term.archive import archive_segment,verify_archive
from bitcoin_cycle_analyzer.short_term.journal import Journal,atomic_json
from bitcoin_cycle_analyzer.short_term.storage_policy import StorageMaintenance,StoragePolicy

T=datetime(2026,1,1,tzinfo=UTC)

def setup(tmp_path):
    root=tmp_path/'raw';root.mkdir()
    journal=Journal(tmp_path/'journal.db')
    raw=root/'test.jsonl'
    raw.write_text(''.join(json.dumps({'source':'spot','received_at':T.timestamp()+s,'payload':str(s)})+'\n' for s in range(10)))
    # Windows pyarrow mmap handle release is occasionally delayed, making the
    # archive rename fail spuriously (pre-existing flake - the retry pattern
    # already used by the bulk-manifest tests below).
    for attempt in range(5):
        try:
            archive_segment(raw);break
        except PermissionError:
            if attempt==4:raise
            time.sleep(0.05)
    return root,journal,raw,StorageMaintenance(root,journal,SimpleNamespace(pending_floor=lambda:None))

def test_verified_hot_tier_retains_raw_and_archive(tmp_path):
    root,j,raw,m=setup(tmp_path)
    result=m.run(T+timedelta(hours=12))
    assert result['redundant_raw_removed']==0 and raw.exists()
    manifest=verify_archive(raw.with_suffix('.parquet'))
    assert manifest['storage_tier']=='HOT' and manifest['records']==10

def test_unpinned_archive_fully_expires_past_warm_seconds(tmp_path):
    # Storage gate <=100MB/24h: an unpinned WARM-aged archive is market noise
    # nothing ever tied to a real signal - both the raw .jsonl AND the
    # compressed .parquet+manifest must be reclaimed, not kept forever.
    root,j,raw,m=setup(tmp_path)
    result=m.run(T+timedelta(days=2))
    assert result['redundant_raw_removed']==1 and not raw.exists()
    assert result['raw_archives_deleted']==1
    assert not raw.with_suffix('.parquet').exists()
    assert not raw.with_suffix('.manifest.json').exists()

def test_expire_archives_dry_run_reports_without_deleting(tmp_path):
    root,j,raw,_=setup(tmp_path)
    m=StorageMaintenance(root,j,SimpleNamespace(pending_floor=lambda:None),expire_archives_dry_run=True)
    result=m.run(T+timedelta(days=2))
    assert result['raw_archives_expirable_dry_run']==1 and result['raw_archives_deleted']==0
    assert raw.with_suffix('.parquet').exists() and raw.with_suffix('.manifest.json').exists()

@pytest.mark.parametrize('protected',['P0','event','pending'])
def test_priority_and_open_outcome_preserve_required_raw(tmp_path,protected):
    root,j,raw,m=setup(tmp_path)
    if protected=='P0':
        path=raw.with_suffix('.manifest.json');v=json.loads(path.read_text());v['priority']='P0';atomic_json(path,v)
    elif protected=='event':j.append('signal_transition','event',T,{'state_to':'PREWARNING'})
    else:m.outcomes.pending_floor=lambda:T.timestamp()
    m.run(T+timedelta(days=8))
    assert raw.exists() and verify_archive(raw.with_suffix('.parquet'))['records']==10

def test_disk_critical_fails_closed_and_records_incident(tmp_path,monkeypatch):
    root,j,raw,m=setup(tmp_path)
    monkeypatch.setattr('bitcoin_cycle_analyzer.short_term.storage_policy.shutil.disk_usage',lambda p:SimpleNamespace(total=100000000000,used=96000000000,free=4000000000))
    r=m.run(T)
    assert r['tier']=='CRITICAL' and not r['new_signals_allowed'] and r['remaining_days']==0
    assert j.rows('incident')[0]['payload']['reason']=='DISK_CRITICAL'

def test_pending_pin_index_backlog_blocks_retention(tmp_path,monkeypatch):
    root,j,raw,m=setup(tmp_path)
    monkeypatch.setattr(m,'index_pins',lambda:False)
    m.run(T+timedelta(days=8))
    assert raw.exists()

def test_invalid_storage_budget_rejected():
    with pytest.raises(ValueError):StoragePolicy(high=.99,critical=.95)


def test_pin_overlaps_matches_brute_force_reference():
    """_pin_overlaps (O(log n) bisect over a pre-loaded index) must produce
    exactly the same result as the original SQL overlap predicate
    (start<=query_end AND end>=query_start) for every case: no pins, one pin,
    many overlapping/non-overlapping pins."""
    import random
    random.seed(1)
    pins=[(min(a,b),max(a,b)) for a,b in ((random.uniform(0,1000),random.uniform(0,1000)) for _ in range(80))]
    idx_sorted=sorted(pins)
    starts=[s for s,_ in idx_sorted]
    prefix_max=[];running=float('-inf')
    for _,e in idx_sorted:
        running=max(running,e);prefix_max.append(running)
    index=(starts,prefix_max)

    def brute(qs,qe):
        return any(s<=qe and e>=qs for s,e in pins)

    assert StorageMaintenance._pin_overlaps(([],[]),0,10) is False  # no pins at all
    for _ in range(3000):
        qs=random.uniform(-100,1100);qe=qs+random.uniform(0,200)
        assert StorageMaintenance._pin_overlaps(index,qs,qe)==brute(qs,qe)


def test_storage_maintenance_uses_bounded_db_connections_regardless_of_manifest_count(tmp_path,monkeypatch):
    """Root cause fixed 2026-09-14: run() used to open one Journal connection
    per manifest via pinned() (O(n) - 2,082 connections / 89s for 2,055
    manifests in production, longer than the 60s maintenance interval itself).
    With N manifests and zero pins, the number of Journal.connect() calls must
    stay constant (not grow with N) - proving the O(n) SQLite round-trip path
    is gone. 200 manifests is enough to demonstrate the scaling difference
    without a slow test."""
    root=tmp_path/'raw';root.mkdir();journal=Journal(tmp_path/'journal.db')
    for i in range(200):
        raw=root/f'seg{i:04d}.jsonl'
        raw.write_text(json.dumps({'source':'spot','received_at':T.timestamp()+i,'payload':str(i)})+'\n')
        # Windows pyarrow mmap handle release is occasionally delayed under a
        # tight loop (pre-existing, documented flake unrelated to this fix -
        # see test_archive_roundtrip_retention_and_pins history); retry the
        # rename rather than fail the whole performance test on it.
        for attempt in range(5):
            try:
                archive_segment(raw);break
            except PermissionError:
                if attempt==4:raise
                time.sleep(0.05)
    maintenance=StorageMaintenance(root,journal,SimpleNamespace(pending_floor=lambda:None))

    calls={'n':0};real_connect=Journal.connect
    def counting_connect(self):
        calls['n']+=1;return real_connect(self)
    monkeypatch.setattr(Journal,'connect',counting_connect)

    maintenance.run(T+timedelta(days=8))
    # A handful of fixed calls (prune, index_pins x8 kinds, the pin index load,
    # plus per-deleted-segment retain_segment bookkeeping) - NOT one per manifest.
    assert calls['n']<30,f"expected a small, N-independent number of DB connections, got {calls['n']} for 200 manifests"


def test_storage_maintenance_never_deletes_a_pinned_manifest_among_many(tmp_path):
    """Correctness under the new bulk pin-index path: with many manifests and
    exactly one pinned event overlapping one specific segment, only that
    segment must survive retention - the optimization must not accidentally
    pin everything or nothing."""
    root=tmp_path/'raw';root.mkdir();journal=Journal(tmp_path/'journal.db')
    paths=[]
    for i in range(30):
        raw=root/f'seg{i:03d}.jsonl'
        ts=T+timedelta(seconds=i*3700)  # spread out so each is its own hot/warm window
        raw.write_text(json.dumps({'source':'spot','received_at':ts.timestamp(),'payload':str(i)})+'\n')
        # Windows pyarrow mmap handle release is occasionally delayed under a
        # tight archive_segment() loop (pre-existing, documented flake - see
        # test_storage_maintenance_uses_bounded_db_connections... above);
        # retry the rename rather than fail this correctness test on it.
        for attempt in range(5):
            try:
                archive_segment(raw);break
            except PermissionError:
                if attempt==4:raise
                time.sleep(0.05)
        paths.append(raw)
    # Pin exactly one event that overlaps segment #15's [start,end] window.
    pinned_ts=T+timedelta(seconds=15*3700)
    journal.append('signal_transition','pin-me',pinned_ts,{'state_to':'PREWARNING'})
    maintenance=StorageMaintenance(root,journal,SimpleNamespace(pending_floor=lambda:None))
    maintenance.run(T+timedelta(days=30))
    assert paths[15].exists(),"the pinned segment's raw file must survive"
    assert not paths[0].exists() and not paths[29].exists(),"unpinned old segments must still be retained per existing policy"
    manifest15=json.loads(paths[15].with_suffix('.manifest.json').read_text())
    assert manifest15['event_window_pinned'] is True and manifest15['effective_priority']=='P1'


def test_journal_prune_deletes_only_listed_kinds_before_cutoff(tmp_path):
    """7-day production audit (2026-09-12) root cause of journal.db growing to
    8.3GB unbounded: no retention existed for the highest-volume telemetry
    kinds. prune() must delete only what it's told, only before the cutoff, and
    never touch kinds not listed (the audit trail)."""
    j=Journal(tmp_path/'journal.db')
    old=T;new=T+timedelta(days=30)
    j.append('candidate','old-1',old,{'x':1})
    j.append('candidate','new-1',new,{'x':1})
    j.append('outcome','old-1',old,{'x':1})
    j.append('incident','old-1',old,{'reason':'KEEP_ME'})  # not in prune list
    deleted=j.prune(('candidate','outcome'),before_timestamp=old.timestamp()+1)
    assert deleted==2
    assert len(j.rows('candidate'))==1 and j.rows('candidate')[0]['id']=='new-1'
    assert len(j.rows('outcome'))==0
    assert len(j.rows('incident'))==1  # untouched regardless of age


def test_storage_maintenance_manifest_cache_skips_unchanged_files_on_second_pass(tmp_path,monkeypatch):
    """Root cause fixed 2026-09-14: run() re-parsed every manifest.json from
    disk on every pass (61.5s steady-state at ~2,000 manifests, growing with
    archive volume - longer than the archiver's own 60s interval). A second
    pass with nothing changed must not re-read any manifest content; new or
    externally-changed files must still be read."""
    root=tmp_path/'raw';root.mkdir();journal=Journal(tmp_path/'journal.db')
    for i in range(50):
        raw=root/f'seg{i:03d}.jsonl'
        raw.write_text(json.dumps({'source':'spot','received_at':T.timestamp()+i,'payload':str(i)})+'\n')
        for attempt in range(5):
            try:archive_segment(raw);break
            except PermissionError:
                if attempt==4:raise
                time.sleep(0.05)
    maintenance=StorageMaintenance(root,journal,SimpleNamespace(pending_floor=lambda:None))
    maintenance.run(T)  # first pass: cold cache, must read everything and settle tiers

    reads={'n':0};real_read_text=Path.read_text
    def counting_read_text(self,*a,**k):
        if self.suffix=='.json':reads['n']+=1
        return real_read_text(self,*a,**k)
    monkeypatch.setattr(Path,'read_text',counting_read_text)

    maintenance.run(T)  # second pass, same "now": nothing changed on disk
    assert reads['n']==0,f"expected zero manifest re-reads on an unchanged second pass, got {reads['n']}"

    # A genuinely new manifest must still be picked up.
    raw=root/'seg999.jsonl'
    raw.write_text(json.dumps({'source':'spot','received_at':T.timestamp()+999,'payload':'999'})+'\n')
    for attempt in range(5):
        try:archive_segment(raw);break
        except PermissionError:
            if attempt==4:raise
            time.sleep(0.05)
    maintenance.run(T)
    assert reads['n']>=1,"a newly-created manifest must be read at least once"


def test_storage_maintenance_prunes_old_telemetry_via_retention_window(tmp_path):
    root,j,raw,m=setup(tmp_path)
    old=T
    j.append('candidate','old-1',old,{'x':1})
    j.append('incident','old-1',old,{'reason':'KEEP_ME'})
    m.policy=StoragePolicy(journal_retention_seconds=86400)
    m.run(T+timedelta(days=30))
    assert len(j.rows('candidate'))==0   # pruned: past the retention window
    assert any(r['id']=='old-1' for r in j.rows('incident'))  # audit trail kind, never pruned


def test_stage_marks_do_not_create_permanent_event_rows(tmp_path):
    # Regression: stage_* rows were ~520k/day of pure waste - nothing ever read
    # them back (health/recovery/API all read the progress table).
    j=Journal(tmp_path/'journal.db')
    for i in range(50):
        assert j.mark('feed_spot','cause-%d'%i,T+timedelta(seconds=i)) is True
    with j.connect() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind LIKE 'stage_%'").fetchone()[0]==0
    marker=Journal.progress_at(tmp_path/'journal.db')['feed_spot']
    assert marker['seq']==50 and marker['cause_id']=='cause-49'

def test_stage_mark_is_idempotent_for_the_same_cause(tmp_path):
    j=Journal(tmp_path/'journal.db')
    assert j.mark('vantage','same',T) is True
    assert j.mark('vantage','same',T) is False  # duplicate suppressed, seq unchanged
    assert Journal.progress_at(tmp_path/'journal.db')['vantage']['seq']==1

def test_progress_seq_is_monotonic_across_both_write_paths(tmp_path):
    # append(stage=...) and mark_on() both advance the same stage; mixing
    # rowid-based with incremented sequences could move seq backwards, which
    # HealthSupervisor reads as "recovery never progressed".
    j=Journal(tmp_path/'journal.db')
    seqs=[]
    for i in range(20):
        if i%2:j.mark('features','c%d'%i,T+timedelta(seconds=i))
        else:j.append('features','e%d'%i,T+timedelta(seconds=i),{'x':i},stage='features',cause_id='c%d'%i)
        seqs.append(Journal.progress_at(tmp_path/'journal.db')['features']['seq'])
    assert seqs==sorted(seqs) and len(set(seqs))==len(seqs)

def _with_outcomes(tmp_path):
    from bitcoin_cycle_analyzer.short_term.outcome_engine import OutcomeEngine
    root,j,raw,_=setup(tmp_path)
    return root,j,raw,StorageMaintenance(root,j,OutcomeEngine(j))

def test_quotes_and_pins_are_pruned_but_open_outcomes_protected(tmp_path):
    root,j,raw,m=_with_outcomes(tmp_path)
    old=T.timestamp()-30*86400
    with j.connect() as db:
        db.execute('INSERT INTO quotes VALUES(?,?,?)',(old,100.0,101.0))
        db.execute('INSERT INTO quotes VALUES(?,?,?)',(T.timestamp(),100.0,101.0))
        db.execute('INSERT INTO raw_event_pins VALUES(?,?,?,?)',('stale',old-600,old+1800,'signal_transition'))
    m.prune_side_tables(T+timedelta(days=10))
    with j.connect() as db:
        assert db.execute('SELECT count(*) FROM quotes WHERE t=?',(old,)).fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM raw_event_pins WHERE id='stale'").fetchone()[0]==0

def test_quote_prune_never_crosses_an_open_observation(tmp_path):
    root,j,raw,m=_with_outcomes(tmp_path)
    old=T.timestamp()-30*86400
    with j.connect() as db:db.execute('INSERT INTO quotes VALUES(?,?,?)',(old,100.0,101.0))
    m.outcomes.pending_floor=lambda:old-1  # an outcome still needs that quote
    m.prune_side_tables(T+timedelta(days=10))
    with j.connect() as db:
        assert db.execute('SELECT count(*) FROM quotes WHERE t=?',(old,)).fetchone()[0]==1

def test_atomic_json_leaves_no_temp_file_when_replace_fails(tmp_path,monkeypatch):
    # Regression: 2,473 orphaned *.tmp files had accumulated in runtime/waverun
    # because a permanently failing os.replace() returned without cleanup.
    import os as _os
    from types import SimpleNamespace
    from bitcoin_cycle_analyzer.short_term import journal as journal_mod
    def always_busy(src,dst):
        err=PermissionError('busy');err.winerror=32;raise err
    # Patch only the journal module's own `os` reference - replacing the real
    # os.replace breaks pytest's tmp_path machinery itself.
    monkeypatch.setattr(journal_mod,'os',SimpleNamespace(replace=always_busy,fsync=_os.fsync,getpid=_os.getpid))
    monkeypatch.setattr(journal_mod.time,'sleep',lambda s:None)
    target=tmp_path/'state.json'
    with pytest.raises(PermissionError):
        atomic_json(target,{'a':1})
    assert list(tmp_path.glob('*.tmp'))==[]
