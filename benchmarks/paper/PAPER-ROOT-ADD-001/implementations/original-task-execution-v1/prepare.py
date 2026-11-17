"""Finite original-store preparation CLI; external root admission is required."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE=Path(__file__).resolve().parent


def need(ok,message):
    if not ok:raise ValueError(message)


def read_admission(path,expected):
    need(type(expected) is str and len(expected)==64 and all(c in '0123456789abcdef' for c in expected),
         'Externally frozen admission SHA256')
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No admission symlink')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=16384,'Bounded ordinary admission')
        raw=f.read(before.st_size+1)
        identity=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(len(raw)==before.st_size and identity(before)==identity(os.fstat(f.fileno()))==identity(path.lstat())
             and hashlib.sha256(raw).hexdigest()==expected,'Exact stable admission bytes')
    def pairs(items):
        out={}
        for key,value in items:
            need(key not in out,'Duplicate admission key');out[key]=value
        return out
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite admission'))
    need(type(value) is dict and value.get('schema')=='language-original-store-preparation-admission/v1'
         and value.get('model_execution') is False and value.get('native_execution') is False,
         'Only source-store preparation, never a model/provider run')
    return raw,value


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--admission',required=True)
    p.add_argument('--admission-sha256',required=True)
    p.add_argument('--census',required=True)
    p.add_argument('--preparation',required=True)
    args=p.parse_args(argv)
    raw,a=read_admission(args.admission,args.admission_sha256)
    source=HERE.parent/'original-store-producer-v1/producer.py'
    body=source.read_bytes()
    need(len(body)<=131072 and hashlib.sha256(body).hexdigest()==a.get('producer_source_sha256'),
         'Exact admitted producer before loading or archive access')
    spec=importlib.util.spec_from_file_location('_language_admitted_original_producer',source)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    # prepare_original checks every canonical field, path, cap, runtime and
    # source pin again before opening the original archives.
    result=module.prepare_original(a['output'],a['archives'],census_path=args.census,preparation_path=args.preparation,
        admission_bytes=raw,expected_admission_sha256=args.admission_sha256,read_limit=a['read_limit'],
        working_limit=a['working_limit'],output_limit=a['output_limit'],metadata_limit=a['metadata_limit'])
    print(json.dumps({'output':a['output'],'store':result['store'],
                      'complete_original_store':result['metadata']['complete_original_store'],
                      'written_bytes':result['written_bytes'],'models_run':0,'scientific_qualification':False}))


if __name__=='__main__':main()
