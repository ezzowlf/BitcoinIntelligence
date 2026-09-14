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
    archive_segment(raw)
    return root,journal,raw,StorageMaintenance(root,journal,SimpleNamespace(pending_floor=lambda:None))

def test_verified_hot_warm_cold_and_archive_retention(tmp_path):
    root,j,raw,m=setup(tmp_path)
    result=m.run(T+timedelta(days=8))
    assert result['redundant_raw_removed']==1 and not raw.exists()
    manifest=verify_archive(raw.with_suffix('.parquet'))
    assert manifest['storage_tier']=='COLD' and manifest['records']==10

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
