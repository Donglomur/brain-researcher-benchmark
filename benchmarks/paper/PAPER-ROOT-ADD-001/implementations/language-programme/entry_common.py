"""Immutable in-container entry checks. No candidate/reference work at import."""
import hashlib, json, os, resource, runpy, sys
from pathlib import Path

def need(v,m):
    if not v:raise ValueError(m)

def read(path,cap):
    p=Path(path);need(p.is_file() and not p.is_symlink() and p.stat().st_size<=cap,'bounded entry file')
    b=p.read_bytes();need(len(b)<=cap,'bounded captured entry');return b

def main_args():
    import argparse
    p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--request',required=True);a=p.parse_args()
    r=json.loads(read(a.request,1048576));v=json.loads(read('/input/VIEW.json',1048576))
    need(r['schema']=='langbuild_owned_phase_request_v1' and v['task_id']=='PAPER-ROOT-ADD-001','task/request identity')
    need(r['mode']==v['mode'] and r['episode']==v['episode'] and r['phase_id']==v['phase_id'],'exact isolated context')
    need(r['source']==v['source_manifest'],'same source closure')
    need(sys.version.split()[0]==v['versions']['python'],'exact Python version')
    from importlib.metadata import version
    for key,value in v['versions'].items():
        if key!='python':need(version(key)==value,'exact dependency version: '+key)
    need(os.getuid()==65534 and Path('/output').is_dir(),'isolated producer output')
    need(not any(Path('/output').iterdir()),'empty owned output')
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):need(os.environ.get(key)=='1','single-thread numerical policy')
    return r,v

def candidate(mode):
    r,v=main_args();need(r['mode']==mode and v['role']==('native' if mode=='native' else 'strict'),'candidate role')
    b=read('/program/program.py',8388608);need({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}==v['program'],'globally committed candidate')
    args=['/program/program.py','--mode','native' if mode=='native' else 'prediction','--input','/input','--output','/output']
    if mode=='strict':args+=['--case','/input/case.json']
    sys.argv=args;runpy.run_path('/program/program.py',run_name='__main__')
