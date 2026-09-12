import json
from datetime import UTC,datetime,timedelta
import pytest
import threading
import time
from bitcoin_cycle_analyzer.short_term.journal import Journal
from bitcoin_cycle_analyzer.short_term.archive import archive_segment,verify_archive,retain_segment,RawWriter
T=datetime(2026,1,1,tzinfo=UTC)

def make_raw(path,n=100):
    path.write_bytes(b''.join((json.dumps({'source':'spot','received_at':T.timestamp()+i,'payload':{'price':77000+i,'exact':'Unicode € preserve'}})+'\n').encode() for i in range(n)))


def test_archive_roundtrip_retention_and_pins(tmp_path):
    path=tmp_path/'raw.jsonl';make_raw(path);archive_segment(path);p=path.with_suffix('.parquet')
    assert verify_archive(p)['records']==100
    assert not retain_segment(p,now=T+timedelta(days=4),hot_seconds=86400,pending_floor=T.timestamp())
    assert not retain_segment(p,now=T+timedelta(days=4),hot_seconds=86400,pinned=True)
    assert retain_segment(p,now=T+timedelta(days=4),hot_seconds=86400)
    assert p.exists() and not path.exists()


@pytest.mark.parametrize('corrupt',['archive','manifest'])
def test_archive_corruption_prevents_delete(tmp_path,corrupt):
    raw=tmp_path/'raw.jsonl';make_raw(raw);archive_segment(raw);p=raw.with_suffix('.parquet')
    if corrupt=='archive':p.write_bytes(p.read_bytes()[:-5]+b'wrong')
    else:
        manifest=p.with_suffix('.manifest.json');m=json.loads(manifest.read_text());m['records']+=1;manifest.write_text(json.dumps(m))
    with pytest.raises(ValueError):retain_segment(p,now=T+timedelta(days=4),hot_seconds=1)
    assert raw.exists()


def test_archive_restart_salvage_and_queue_bounds(tmp_path):
    j=Journal(tmp_path/'journal.db');root=tmp_path/'raw';root.mkdir();raw=root/'interrupted.open';make_raw(raw,3)
    with raw.open('ab') as f:f.write(b'{broken')
    writer=RawWriter(root,j,capacity=1);writer.catch_up()
    assert (root/'interrupted.interrupted').exists()
    assert verify_archive(root/'interrupted.parquet')['records']==3
    assert writer.submit('spot',T,'x') and not writer.submit('spot',T,'y')
    assert writer.error=='RAW_QUEUE_FULL' and writer.dropped==1

def test_slow_compressor_does_not_block_raw_writer(tmp_path,monkeypatch):
    entered=threading.Event();release=threading.Event()
    def blocked(path):
        entered.set()
        assert release.wait(5)
    monkeypatch.setattr('bitcoin_cycle_analyzer.short_term.archive.archive_segment',blocked)
    writer=RawWriter(tmp_path/'raw',Journal(tmp_path/'journal.db'),segment_records=1)
    try:
        writer.start();assert writer.submit('spot',T,'first')
        assert entered.wait(3)
        for i in range(10):assert writer.submit('spot',T,str(i))
        deadline=time.monotonic()+3
        while writer.written<11 and time.monotonic()<deadline:time.sleep(.01)
        assert writer.written==11 and writer.queue.qsize()==0
        assert writer.archive_queue.qsize()>=1
    finally:release.set();writer.close()

def test_catch_up_never_touches_the_actively_written_segment(tmp_path):
    """7-day production audit (2026-09-12) root cause of 239 ARCHIVE_CATCHUP_ERROR
    PermissionError incidents: catch_up() can be re-run by the self-heal
    supervisor while the writer thread is still alive on its own .open segment.
    Racing os.replace() against a file the writer still holds open raises
    PermissionError on Windows. catch_up() must skip whatever RawWriter.current_path
    points at."""
    writer=RawWriter(tmp_path/'raw',Journal(tmp_path/'journal.db'))
    active=writer.root/'20260101T000000_active.open'
    active.write_bytes(b'{"source":"spot","received_at":1,"payload":"x"}\n')
    writer.current_path=active  # simulate: the writer thread owns this segment right now
    stale=writer.root/'20260101T000000_stale.open'
    stale.write_bytes(b'{"source":"spot","received_at":1,"payload":"x"}\n')
    writer.catch_up()
    assert active.exists()  # untouched - still owned by the (simulated) live writer
    assert not stale.exists()  # genuinely orphaned segment was salvaged as before
    assert (writer.root/'20260101T000000_stale.interrupted').exists()
    writer.close()


def test_compressor_failure_keeps_complete_raw_and_fails_health(tmp_path,monkeypatch):
    def broken(path):raise OSError('simulated archive failure')
    monkeypatch.setattr('bitcoin_cycle_analyzer.short_term.archive.archive_segment',broken)
    writer=RawWriter(tmp_path/'raw',Journal(tmp_path/'journal.db'),segment_records=1)
    try:
        writer.start();writer.submit('spot',T,'source-payload')
        deadline=time.monotonic()+3
        while not writer.error and time.monotonic()<deadline:time.sleep(.01)
        assert writer.error=='ARCHIVE_OSError' and not writer.ready
        raw=list(writer.root.glob('*.jsonl'))
        assert len(raw)==1 and 'source-payload' in raw[0].read_text()
    finally:writer.close()
