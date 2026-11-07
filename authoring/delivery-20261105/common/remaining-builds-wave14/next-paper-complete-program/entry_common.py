"""Container-only role/version guard. No data or estimator work on import."""
import importlib.metadata,json,os,sys
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)

def guard(role):
    need(os.getuid()==os.geteuid()==65534,'fixed producer UID')
    with Path('/input/VIEW.json').open('rb') as f:raw=f.read(65537)
    need(len(raw)<=65536,'bounded view metadata');view=json.loads(raw)
    need(view['role']==role,'exact phase role');v=view['versions']
    need(v['python']==sys.version.split()[0],'selected Python version')
    for package,version in v.items():
        if package!='python':need(importlib.metadata.version(package)==version,'selected distribution version')
    return view

def candidate(role):
    guard(role)
    os.execv(sys.executable,[sys.executable,'-I','-B','/program/program.py','--input','/input','--output','/output'])
