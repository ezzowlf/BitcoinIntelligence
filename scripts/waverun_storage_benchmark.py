"""Reproducible local benchmark on actual records; no raw source mutation."""
import argparse,gzip,hashlib,json,time,tracemalloc,os,shutil
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq


def benchmark(source,output,limit):
    output.mkdir(parents=True,exist_ok=True);tracemalloc.start()
    lines=[];times=[];sources=[]
    with source.open('rb') as f:
        for i,line in enumerate(f):
            if i>=limit:break
            r=json.loads(line);lines.append(line);times.append(r['received_timestamp']);sources.append(r['exchange'])
    raw=b''.join(lines);digest=hashlib.sha256(raw).hexdigest();results={}
    for fmt in ('jsonl','gzip','parquet_zstd'):
        path=output/('sample.'+fmt);start=time.perf_counter();cpu=time.process_time()
        if fmt=='parquet_zstd':pq.write_table(pa.table({'source':sources,'received_at':times,'raw':lines}),path,compression='zstd',compression_level=9,row_group_size=8192)
        elif fmt=='gzip':
            with gzip.open(path,'wb',compresslevel=6) as f:f.write(raw)
        else:path.write_bytes(raw)
        with path.open('r+b') as f:os.fsync(f.fileno())
        duration=time.perf_counter()-start;cpu_write=time.process_time()-cpu
        start=time.perf_counter();cpu=time.process_time()
        recovered=b''.join(pq.read_table(path).column('raw').to_pylist()) if fmt=='parquet_zstd' else gzip.open(path,'rb').read() if fmt=='gzip' else path.read_bytes()
        read_duration=time.perf_counter()-start;cpu_read=time.process_time()-cpu
        assert recovered==raw and hashlib.sha256(recovered).hexdigest()==digest
        lo,hi=times[len(times)//3],times[2*len(times)//3]
        start=time.perf_counter()
        if fmt=='parquet_zstd':matched=pq.read_table(path,filters=[('received_at','>=',lo),('received_at','<=',hi)],columns=['received_at']).num_rows
        else:matched=sum(lo<=json.loads(line)['received_timestamp']<=hi for line in recovered.splitlines())
        range_seconds=time.perf_counter()-start
        results[fmt]={'bytes':path.stat().st_size,'compression_ratio':len(raw)/path.stat().st_size,'write_seconds':duration,'write_records_second':len(lines)/duration,'read_seconds':read_duration,'read_records_second':len(lines)/read_duration,'cpu_write_seconds':cpu_write,'cpu_read_seconds':cpu_read,'range_seconds':range_seconds,'range_rows':matched,'lossless_roundtrip':True}
    assert len({v['range_rows'] for v in results.values()})==1
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    result={'input':str(source),'sample_records':len(lines),'sample_raw_bytes':len(raw),'sample_sha256':digest,'start':times[0],'end':times[-1],'formats':results,'python_peak_traced_bytes':peak,'arrow_allocated_bytes_at_end':pa.total_allocated_bytes(),'disk':dict(zip(('total','used','free'),shutil.disk_usage(output))),'scope':'local warm-cache sample; not a VPS throughput guarantee','crash_safety_evidence':'tests/test_waverun_rebuild.py archive restart/corruption/retention tests; throughput benchmark alone does not prove crash safety','execution':'DISABLED'}
    (output/'benchmark.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--records',type=int,default=100000);a=p.parse_args();benchmark(a.input,a.output,a.records)
