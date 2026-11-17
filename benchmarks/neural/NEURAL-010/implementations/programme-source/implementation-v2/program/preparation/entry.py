"""Isolated standard-library entry: authenticate every sibling before compilation."""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import types

HERE=Path(__file__).resolve().parent
NAMES={'entry.py','prepare.py','storage.py','views.py','VENDOR_BINDINGS.json','vendor/edf_adapter.py','vendor/reconcile_annotations.py','vendor/io_contract.py','vendor/event_protocol.py','vendor/scorer.py'}

def need(ok,message):
    if not ok:raise ValueError(message)

def parse(raw):
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d,'duplicate metadata field');d[k]=v
        return d
    def bad(x):raise ValueError('nonfinite metadata token')
    return json.loads(raw.decode(),object_pairs_hook=pairs,parse_constant=bad)

def capture(path,pin,cap):
    need(type(pin)is dict and set(pin)=={'bytes','sha256'} and type(pin['bytes'])is int and 0<pin['bytes']<=cap,'bounded bootstrap pin')
    need(type(pin['sha256'])is str and len(pin['sha256'])==64 and all(c in '0123456789abcdef'for c in pin['sha256']),'bootstrap digest')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==pin['bytes'],'ordinary bootstrap body')
        body=bytearray()
        while len(body)<=pin['bytes']:
            b=os.read(fd,min(65536,pin['bytes']+1-len(body)))
            if not b:break
            body.extend(b)
        z=os.fstat(fd)
        need(all(getattr(a,k)==getattr(z,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable bootstrap body')
        body=bytes(body);need(len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256'],'bootstrap exact identity');return body
    finally:os.close(fd)

def compile_captured(bodies,root):
    """Pure source assembly; no input/header/key/native producer is invoked."""
    modules={};normal=builtins.__import__
    def importer(name,globals=None,locals=None,fromlist=(),level=0):
        if name in modules:return modules[name]
        return normal(name,globals,locals,fromlist,level)
    for name in ('storage','views','prepare'):
        mod=types.ModuleType('neural010_captured_'+name)
        mod.__file__=str(root/(name+'.py'))
        namespace=dict(vars(builtins));namespace['__import__']=importer
        mod.__dict__['__builtins__']=namespace
        exec(compile(bodies[name+'.py'],mod.__file__,'exec'),mod.__dict__)
        modules[name]=mod
    return modules

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('request','authority','authority-sha256'):p.add_argument('--'+name,required=True)
    p.add_argument('--authority-bytes',type=int,required=True);a=p.parse_args()
    # This exact entry and authority are authenticated by the independent launcher.
    ap={'bytes':a.authority_bytes,'sha256':a.authority_sha256};araw=capture(a.authority,ap,1048576);authority=parse(araw)
    need(authority.get('schema')=='neural010-original-preparation-authority-v1','authority schema')
    for k in ('qualified_original_preparation','qualified_source_closure','qualified_namespace','qualified_runtime_resources','operator_selected'):
        need(authority.get(k)is True,'missing independent '+k)
    manifest_raw=capture(HERE/'SOURCE_MANIFEST.json',authority['source_manifest'],1000000);manifest=parse(manifest_raw)
    need(manifest.get('schema')=='neural010-preparation-runtime-sources-v1' and type(manifest.get('files'))is list,'source closure schema')
    rows=manifest['files'];need(len(rows)==len(NAMES) and {r['name']for r in rows}==NAMES,'exact full source closure')
    bodies={};debited=len(araw)+1+len(manifest_raw)+1
    for row in rows:
        bodies[row['name']]=capture(HERE/row['name'],{k:row[k]for k in ('bytes','sha256')},1000000)
        debited+=len(bodies[row['name']])+1
    raw=capture(a.request,authority['request'],1048576);debited+=len(raw)+1;request=parse(raw)
    modules=compile_captured(bodies,HERE)
    result=modules['prepare'].prepare(request,authority,operator_origin=request['original_origin'],bootstrap_read_bytes=debited)
    print(json.dumps({'status':result['status'],'records':686,'people':23},sort_keys=True))

if __name__=='__main__':main()
