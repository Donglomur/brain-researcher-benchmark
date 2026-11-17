#!/usr/bin/env python3
"""Trusted bootstrap: python -I -S -B launch.py --selection ... --data-root ... --output ..."""
import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

def require(value,reason):
    if not value:raise ValueError(reason)

def read(path,limit,pin=None):
    path=Path(path);require(all(not p.is_symlink() for p in (path,*path.parents)),'bootstrap_symlink')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd);require(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size<=limit,'bootstrap_extent')
        chunks=[];remaining=a.st_size
        while remaining:
            block=os.read(fd,min(remaining,65536));require(block,'bootstrap_short_read');chunks.append(block);remaining-=len(block)
        require(not os.read(fd,1),'bootstrap_growth');b=os.fstat(fd)
        require((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'bootstrap_changed')
        body=b''.join(chunks)
        if pin is not None:require(len(body)==pin['bytes'] and hashlib.sha256(body).hexdigest()==pin['sha256'],'bootstrap_pin')
        return body
    finally:os.close(fd)

def load_json(body):
    def pairs(items):
        result={}
        for k,v in items:require(k not in result,'bootstrap_duplicate_key');result[k]=v
        return result
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_json')))

def main():
    started=time.monotonic()
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated_no_site_no_bytecode_required')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',required=True);parser.add_argument('--data-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();selection_body=read(args.selection,65536);selection=load_json(selection_body)
    require(selection.get('execution_authorized') is True,'future_selection_required')
    pin=selection['source_manifest'];manifest_body=read(pin['path'],65536,pin);manifest=load_json(manifest_body)
    names={'protocol.py','projection.py','analysis.py','custody.py','actors.py','investigation.py',
        'model_state.py','reference_stream.py','run_investigation.py','reference_worker.R','TASK.md','launch.py',
        'model_broker.py','candidate_relay.py','provider_worker.py'}
    require(manifest['schema']=='neural006-operative-source-v1' and len(manifest['files'])==len(names),'bootstrap_manifest')
    require({Path(row['path']).name for row in manifest['files']}==names,'bootstrap_complete_closure')
    root=Path(__file__).resolve().parent;captured={};total=len(selection_body)+len(manifest_body)
    for row in manifest['files']:
        path=Path(row['path']);require(path.is_absolute() and path.parent==root,'bootstrap_source_location')
        body=read(path,1048576,row);total+=len(body);require(total<=4194304,'bootstrap_source_budget')
        captured[path.name]=body
    captured=types.MappingProxyType(captured)
    modules={Path(name).stem:name for name in names if name.endswith('.py') and name!='launch.py'}
    require(not(set(modules)&set(sys.modules)),'no_preloaded_operative_module')
    class Loader(importlib.abc.Loader):
        def __init__(self,name):self.name=name
        def create_module(self,spec):return None
        def exec_module(self,module):
            filename=modules[self.name];module.__file__=str(root/filename)
            module.__verified_source_capture__=captured
            module.__verified_start_monotonic__=started
            module.__verified_bootstrap_read_bytes__=total
            module.__verified_manifest_sha256__=hashlib.sha256(manifest_body).hexdigest()
            exec(compile(captured[filename],module.__file__,'exec',dont_inherit=True),module.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname in modules:return importlib.util.spec_from_loader(fullname,Loader(fullname),origin=str(root/modules[fullname]))
            return None
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        runner=__import__('run_investigation');return runner.main()
    finally:sys.meta_path.remove(finder)

if __name__=='__main__':
    try:code=main()
    except BaseException as error:
        code=1
        packet={'status':'bootstrap_or_unmanaged_failure','class':type(error).__name__,'message':str(error)[:2048],
            'evidence_scope':'bounded bootstrap diagnostic; no successful campaign claim'}
        try:sys.stderr.write(json.dumps(packet,allow_nan=False)+'\n');sys.stderr.flush()
        except BaseException:pass
    raise SystemExit(code)
