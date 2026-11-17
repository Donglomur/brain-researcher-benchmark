"""Authenticate one frozen participant stream, then use the unchanged scorer."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import sys
import time

def need(ok,message):
    if not ok:raise RuntimeError(message)

def read_pin(path,n,digest,maximum):
    p=Path(path);before=p.stat()
    need(p.is_file() and not p.is_symlink() and before.st_nlink==1 and before.st_size==n and 0<n<=maximum,'bounded admitted input')
    with p.open('rb') as f:raw=f.read(n+1)
    after=p.stat()
    need(len(raw)==n and hashlib.sha256(raw).hexdigest()==digest and all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable exact admitted input')
    return raw

def main():
    start=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('score deadline')))
    signal.setitimer(signal.ITIMER_REAL,650)
    raw=Path('/binding/score-input.json').read_bytes()
    need(len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==os.environ['PFC_SCORE_BINDING_SHA256'],'exact score binding')
    binding=json.loads(raw)
    for name,pin in binding['scorer_sources'].items():read_pin('/scoring/'+name,pin['bytes'],pin['sha256'],1048576)
    packet=binding['packet'];candidate=binding['submission']
    read_pin('/input/participant-packet.json',packet['bytes'],packet['sha256'],16*1024**2)
    read_pin('/submission/submission.jsonl',candidate['bytes'],candidate['sha256'],128*1024**2)
    import numpy,scipy
    need((sys.version.split()[0],numpy.__version__,scipy.__version__)==('3.12.8','2.2.6','1.15.3'),'qualified scientific runtime')
    sys.path.insert(0,'/scoring')
    sys.argv=['/scoring/endpoint_cli.py','score','--packet','/input/participant-packet.json','--candidate','/submission/submission.jsonl','--output','/output/score.json']
    try:runpy.run_path(sys.argv[0],run_name='__main__')
    except SystemExit as error:need(error.code in (None,0),'unchanged scorer natural success')
    need(time.monotonic()-start<650,'original score horizon')
    print(json.dumps({'arm':binding['arm'],'submission_sha256':candidate['sha256'],'score_path':'/output/score.json','complete':True,'reference_unchanged':True}),flush=True)

if __name__=='__main__':main()
