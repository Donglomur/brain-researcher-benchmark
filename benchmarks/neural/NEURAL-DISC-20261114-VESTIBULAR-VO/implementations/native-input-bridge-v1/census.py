"""Once-only complete original schema census under a separately admitted protocol.

No participant/model execution, SSL inspection, Docker operation or data export.
This executable does not grant itself admission to read the authentic original.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import time

import native_mat as n

HERE=Path(__file__).resolve().parent
WALL_SECONDS=300
CPU_SECONDS=240
RAM_BYTES=3*1024**3
OUTPUT_BYTES=18*1024**2
FLOOR_BYTES=60*1024**3


def verify_source(expected):
    raw=n.read_source(HERE/'CENSUS_SOURCE.json',expected)
    manifest=json.loads(raw)
    n.need(manifest['schema']=='vestibular_complete_census_source_v1','source_manifest_schema')
    n.need({row['path'] for row in manifest['files']}=={'native_mat.py','census.py','reused/census_worker.py'},'complete_census_source_roster')
    for row in manifest['files']:
        n.need(n.pin(n.read_source(HERE/row['path'],row['sha256']))=={k:row[k] for k in ('bytes','sha256')},'complete_source_identity')
    return n.pin(raw)


def save(path,value):
    body=n.encoded(value);n.need(len(body)<=65536,'bounded_census_receipt')
    with Path(path).open('xb') as stream:
        Path(path).chmod(0o600);stream.write(body);stream.flush();os.fsync(stream.fileno())
    return n.pin(body)


class CensusWriter:
    def __init__(self,stream):
        self.stream=stream;self.bytes=0;self.sha=hashlib.sha256()
    def write(self,body):
        n.need(self.bytes+len(body)<=n.Limits().census_bytes,'complete_census_write_cap')
        count=self.stream.write(body)
        n.need(count==len(body),'complete_census_write')
        self.bytes+=count;self.sha.update(body)
        return count
    def identity(self):
        return {'bytes':self.bytes,'sha256':self.sha.hexdigest()}


def census_worker(source_path,output,source_pin,*,descriptor=n.SOURCE):
    """Internal descriptor seam exists only for generated loader controls."""
    started=time.monotonic();state={};document=None;error=None;writer=None
    partial=output/'PRIVATE_SCHEMA.partial.jsonl'
    try:
        with partial.open('xb') as stream:
            partial.chmod(0o600)
            writer=CensusWriter(stream)
            document=n.load_complete(source_path,descriptor,writer,diagnostics=state)
            stream.flush();os.fsync(stream.fileno())
        partial.rename(output/'PRIVATE_SCHEMA.jsonl')
    except BaseException as caught:
        # Numeric values and arbitrary third-party exception prose stay private.
        error=n.failure_record(caught)
    receipt={'schema':'vestibular_complete_host_census_worker_v1','task_id':n.TASK,
             'source_manifest':source_pin,'original':descriptor,
             'complete_census':error is None,'failure':error,'diagnostics':state,
             'census_artifact':writer.identity() if writer else None,
             'summary':document.census_summary if document else None,
             'elapsed_seconds':time.monotonic()-started,'biological_binding_verified':False,
             'historical_Docker_SSL_inventory_verified':False,
             'authentic_export_models_or_scoring':False}
    save(output/'WORKER_RECEIPT.json',receipt)
    return receipt


def observe(command,env,*,wall_seconds=WALL_SECONDS,ram_bytes=RAM_BYTES):
    """Own child session only; sampled RSS is explicitly not a hard memory quota."""
    started=time.monotonic();proc=None;selector=None;body=bytearray();maximum=0;reason=None
    code=None;reaped=False;natural=False
    try:
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,env=env,start_new_session=True,bufsize=0)
        selector=selectors.DefaultSelector();os.set_blocking(proc.stdout.fileno(),False)
        selector.register(proc.stdout,selectors.EVENT_READ);next_memory=0
        while selector.get_map() or proc.poll() is None:
            now=time.monotonic();n.need(now-started<wall_seconds,'census_wall_deadline')
            if proc.poll() is None and now>=next_memory:
                sample=subprocess.run(['/bin/ps','-o','rss=','-p',str(proc.pid)],capture_output=True,timeout=2,check=False)
                n.need(len(sample.stdout)+len(sample.stderr)<=4096,'bounded_memory_observation')
                if sample.returncode==0:
                    rss=int(sample.stdout.strip())*1024;maximum=max(maximum,rss)
                    n.need(rss<=ram_bytes,'census_sampled_RSS_limit')
                else:
                    n.need(proc.poll() is not None,'census_memory_observation_failed')
                next_memory=now+.25
            for key,_ in selector.select(.1):
                data=os.read(key.fileobj.fileno(),min(8192,65537-len(body)))
                if not data:
                    selector.unregister(key.fileobj);continue
                body.extend(data);n.need(len(body)<=65536,'bounded_worker_diagnostics')
        code=proc.wait(timeout=2);reaped=True;natural=True
    except BaseException as caught:
        reason=n.failure_record(caught)
    finally:
        if proc is not None and not reaped:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            code=proc.wait(timeout=5);reaped=True
        if selector is not None:
            selector.close()
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
    return {'natural_exit':natural,'exit_code':code,'process_reaped':reaped,
            'failure':reason,'sampled_peak_worker_rss_bytes':maximum,
            'rss_scope':'direct trusted worker, sampled every0.25s; no OS hard RSS quota',
            'elapsed_seconds':time.monotonic()-started,'stdout_bytes':len(body)},bytes(body)


def original_read_accounting(output,source_pin):
    """A killed worker has unknown reads; charge the full allowed original read."""
    actual=None
    try:
        worker=json.loads(n.read_source(Path(output)/'WORKER_RECEIPT.json',limit=65536))
        value=worker['diagnostics']['original_bytes_delivered']
        if (worker['schema']=='vestibular_complete_host_census_worker_v1'
                and worker['source_manifest']==source_pin and worker['original']==n.SOURCE
                and type(value) is int and 0<=value<=n.Limits().read_bytes):
            actual=value
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return {'actual_original_read_bytes':actual,
            'conservative_charged_original_read_bytes':n.Limits().read_bytes if actual is None else actual,
            'scope':'bytes delivered by trusted original stream; not filesystem prefetch or cache I/O',
            'unknown_reason':'worker receipt absent, incomplete or unbound' if actual is None else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--other-reserve-bytes',type=int,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args();source=verify_source(args.source_sha256)
    n.need(args.other_reserve_bytes>=0,'nonnegative_other_reservations')
    if args.worker:
        resource.setrlimit(resource.RLIMIT_CPU,(CPU_SECONDS,CPU_SECONDS+10))
        resource.setrlimit(resource.RLIMIT_FSIZE,(OUTPUT_BYTES,OUTPUT_BYTES))
        def expired(*_):raise n.NativeError('census_worker_alarm')
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,WALL_SECONDS-10)
        receipt=census_worker(args.input,args.output,source)
        signal.setitimer(signal.ITIMER_REAL,0)
        print(json.dumps({'complete_census':receipt['complete_census'],'source_manifest':source}))
        return 0 if receipt['complete_census'] else 1
    output=args.output.absolute()
    n.need(not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),'fresh_operator_output')
    n.need(shutil.disk_usage(output.parent).free>=FLOOR_BYTES+args.other_reserve_bytes+OUTPUT_BYTES,'preserve_global_disk_floor')
    output.mkdir(mode=0o700)
    env=os.environ.copy()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
        env[key]='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    command=[sys.executable,'-B',str(HERE/'census.py'),*sys.argv[1:],'--worker']
    previous={}
    def interrupted(*_):raise KeyboardInterrupt('owned census supervisor interrupted')
    try:
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
            previous[sig]=signal.signal(sig,interrupted)
        observation,body=observe(command,env)
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)
    observation['original_read_accounting']=original_read_accounting(output,source)
    save(output/'PROCESS_RECEIPT.json',observation)
    n.need(observation['natural_exit'] and observation['process_reaped']
           and observation['exit_code']==0 and observation['failure'] is None,'observed_census_zero_exit')
    n.need(json.loads(body)=={'complete_census':True,'source_manifest':source},'worker_completion_join')
    verify_source(args.source_sha256)
    worker_raw=n.read_source(output/'WORKER_RECEIPT.json',limit=65536);worker=json.loads(worker_raw)
    n.need(worker['complete_census'] and worker['original']==n.SOURCE
           and worker['source_manifest']==source and worker['diagnostics']['complete_nested_traversal'],'complete_source_worker_join')
    schema=output/'PRIVATE_SCHEMA.jsonl'
    n.need(schema.is_file() and schema.stat().st_size==worker['diagnostics']['census_bytes'],'complete_schema_extent')
    n.need(n.pin(n.read_source(schema,limit=n.Limits().census_bytes))==worker['census_artifact'],'complete_schema_output_identity')
    save(output/'CLOSED_CENSUS.json',{'schema':'vestibular_complete_host_census_closed_v1',
        'source_manifest':source,'original':n.SOURCE,'worker_receipt':n.pin(worker_raw),
        'process_receipt':n.pin(n.encoded(observation)),'census_artifact':worker['census_artifact'],
        'biological_roles_still_require_review':True,
        'external_supervisor_exit_zero_still_required':True})
    print(json.dumps({'complete_structural_census':True,'biological_binding_verified':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
