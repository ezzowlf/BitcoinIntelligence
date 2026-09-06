"""Bounded raw writer and verified lossless Parquet/ZSTD segment archives."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path

from .journal import atomic_json,identity,utc


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def archive_segment(raw,*,compression='zstd'):
    import pyarrow as pa
    import pyarrow.parquet as pq
    raw=Path(raw)
    rows=[];sources=[];times=[]
    with raw.open('rb') as f:
        for line in f:
            obj=json.loads(line)
            rows.append(line);sources.append(obj['source']);times.append(float(obj['received_at']))
    if not rows:raise ValueError('empty archive')
    target=raw.with_suffix('.parquet');temp=target.with_name(target.name+'.tmp')
    table=pa.table({'source':sources,'received_at':times,'raw':rows})
    pq.write_table(table,temp,compression=compression,compression_level=9 if compression=='zstd' else None,row_group_size=8192)
    with temp.open('r+b') as f:os.fsync(f.fileno())
    recovered=pq.read_table(temp).column('raw').to_pylist()
    digest=hashlib.sha256(b''.join(rows)).hexdigest()
    if len(recovered)!=len(rows) or hashlib.sha256(b''.join(recovered)).hexdigest()!=digest:raise ValueError('archive round-trip mismatch')
    os.replace(temp,target)
    manifest={'filename':target.name,'raw_filename':raw.name,'source':sorted(set(sources)),'schema_version':1,'schema':str(table.schema),'start':min(times),'end':max(times),'records':len(rows),'compressed_bytes':target.stat().st_size,'raw_bytes':raw.stat().st_size,'checksum':sha(target),'raw_checksum':digest,'compression':compression,'verification':'VERIFIED_ARCHIVE','creation_time':utc().isoformat(),'priority':'P2','execution':'DISABLED'}
    atomic_json(target.with_suffix('.manifest.json'),manifest)
    return manifest


def verify_archive(path):
    import pyarrow.parquet as pq
    path=Path(path);manifest=json.loads(path.with_suffix('.manifest.json').read_text())
    if manifest['verification']!='VERIFIED_ARCHIVE' or sha(path)!=manifest['checksum']:raise ValueError('archive checksum mismatch')
    table=pq.read_table(path)
    rows=table.column('raw').to_pylist();times=table.column('received_at').to_pylist()
    if len(rows)!=manifest['records'] or hashlib.sha256(b''.join(rows)).hexdigest()!=manifest['raw_checksum']:raise ValueError('archive record mismatch')
    if min(times)!=manifest['start'] or max(times)!=manifest['end'] or str(table.schema)!=manifest['schema']:raise ValueError('archive manifest mismatch')
    return manifest


def retain_segment(path,*,now,hot_seconds,pending_floor=None,pinned=False):
    """Delete only redundant HOT raw; never P0, never the lossless archive."""
    path=Path(path);manifest=verify_archive(path)
    if manifest.get('priority')=='P0' or pinned:return False
    if utc(now).timestamp()-manifest['end']<hot_seconds:return False
    if pending_floor is not None and manifest['end']>=pending_floor:return False
    raw=path.parent/manifest['raw_filename']
    if raw.resolve().parent!=path.resolve().parent:raise ValueError('unsafe raw path in manifest')
    if not raw.exists():return False
    if sha(raw)!=manifest['raw_checksum']:raise ValueError('raw changed after archival')
    raw.unlink()
    return True


class RawWriter:
    def __init__(self,root,journal,*,capacity=8192,segment_records=50000,segment_seconds=60):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.journal=journal;self.queue=queue.Queue(maxsize=capacity)
        self.segment_records=segment_records;self.segment_seconds=segment_seconds
        self.error=None;self.dropped=0;self.written=0;self.archived=0
        self.stop_event=threading.Event();self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self._run,name='waverun-raw-writer',daemon=True);self.thread.start()

    def submit(self,source,received_at,payload):
        item={'source':source,'received_at':utc(received_at).timestamp(),'payload':payload,'schema_version':1}
        try:self.queue.put_nowait(item)
        except queue.Full:
            self.dropped+=1;self.error='RAW_QUEUE_FULL';return False
        return True

    def close(self,timeout=10):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout)
        if self.thread and self.thread.is_alive():self.error='STORAGE_CLOSE_TIMEOUT'

    def catch_up(self):
        for path in self.root.glob('*.jsonl'):
            archive=path.with_suffix('.parquet')
            if archive.exists() and archive.with_suffix('.manifest.json').exists():verify_archive(archive)
            else:archive_segment(path)
        # Interrupted .open files are preserved. Salvage complete rows only;
        # retain original as forensic evidence and record discarded byte count.
        for path in self.root.glob('*.open'):
            good=[];bad=0
            for line in path.open('rb'):
                try:json.loads(line);good.append(line if line.endswith(b'\n') else line+b'\n')
                except ValueError:bad+=len(line)
            if good:
                recovered=path.with_suffix('.jsonl')
                if not recovered.exists():
                    with recovered.open('wb') as f:f.writelines(good);f.flush();os.fsync(f.fileno())
                    archive_segment(recovered)
            os.replace(path,path.with_suffix('.interrupted'))
            self.journal.append('incident',identity('archive-restart',path.name),utc(),{'reason':'INTERRUPTED_SEGMENT','discarded_bytes':bad,'original_retained':True})

    def _run(self):
        handle=None;path=None;n=0;started=time.monotonic();last_flush=0
        try:
            self.catch_up()
            while not self.stop_event.is_set() or not self.queue.empty():
                try:item=self.queue.get(timeout=.1)
                except queue.Empty:item=None
                if item:
                    if handle is None:
                        path=self.root/(utc().strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex+'.open');handle=path.open('wb');started=time.monotonic();n=0
                    handle.write((json.dumps(item,sort_keys=True,separators=(',',':'))+'\n').encode());n+=1;self.written+=1;self.queue.task_done()
                clock=time.monotonic()
                if clock-last_flush>=1:
                    if handle:handle.flush();os.fsync(handle.fileno())
                    self.journal.mark('storage',identity('raw-flush',clock),utc())
                    last_flush=clock
                if handle and (n>=self.segment_records or clock-started>=self.segment_seconds or self.stop_event.is_set() and self.queue.empty()):
                    handle.flush();os.fsync(handle.fileno());handle.close();handle=None
                    raw=path.with_suffix('.jsonl');os.replace(path,raw)
                    archive_segment(raw);self.archived+=1
        except Exception as exc:
            self.error='STORAGE_'+type(exc).__name__
        finally:
            if handle:handle.close()

    def disk_metrics(self,raw_per_day=None,compressed_per_day=None):
        disk=shutil.disk_usage(self.root);used=disk.used/disk.total
        tier='CRITICAL' if used>=.95 else 'HIGH' if used>=.90 else 'WARNING' if used>=.80 else 'NOTICE' if used>=.70 else 'OK'
        available=max(0,disk.free-max(5e9,.05*disk.total))
        retention=available/compressed_per_day if compressed_per_day and compressed_per_day>0 else None
        return {'total':disk.total,'used':disk.used,'free':disk.free,'tier':tier,'raw_growth_day':raw_per_day,'compressed_growth_day':compressed_per_day,'remaining_days':retention,'queue_size':self.queue.qsize(),'dropped_records':self.dropped,'error':self.error,'execution':'DISABLED'}
