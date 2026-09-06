import json
from datetime import UTC,datetime,timedelta
import pytest
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
