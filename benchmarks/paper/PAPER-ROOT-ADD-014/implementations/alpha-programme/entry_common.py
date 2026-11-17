"""Container-only exact selected environment and immutable public input guard."""
import importlib.metadata
import json
import os
from pathlib import Path
import sys

def need(ok,message):
    if not ok:raise ValueError(message)

def bounded(path):
    with Path(path).open('rb') as f:raw=f.read(1048577)
    need(len(raw)<=1048576,'bounded selected request metadata');return json.loads(raw)

def guard():
    need(os.getuid()==os.geteuid()==65534,'fixed isolated producer UID')
    r=bounded('/request.json');v=bounded('/input/VIEW.json')
    need(r['schema']=='visualalpha_owned_phase_request_v1' and v['schema']=='visual_alpha_program_view_v1' and v['task_id']=='PAPER-ROOT-ADD-014','exact program condition')
    need(all(v[k]==r[k] for k in ('mode','participant','fit_role')),'exact phase context')
    need(v['versions']=={'python':'3.11.6','numpy':'2.4.6','scipy':'1.17.1'} and sys.version.split()[0]=='3.11.6','exact interpreter profile')
    for name in ('numpy','scipy'):need(importlib.metadata.version(name)==v['versions'][name],'exact selected numerical version')
    return r,v
