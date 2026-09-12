import json
from datetime import UTC,datetime,timedelta
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


def test_storage_maintenance_prunes_old_telemetry_via_retention_window(tmp_path):
    root,j,raw,m=setup(tmp_path)
    old=T
    j.append('candidate','old-1',old,{'x':1})
    j.append('incident','old-1',old,{'reason':'KEEP_ME'})
    m.policy=StoragePolicy(journal_retention_seconds=86400)
    m.run(T+timedelta(days=30))
    assert len(j.rows('candidate'))==0   # pruned: past the retention window
    assert any(r['id']=='old-1' for r in j.rows('incident'))  # audit trail kind, never pruned
