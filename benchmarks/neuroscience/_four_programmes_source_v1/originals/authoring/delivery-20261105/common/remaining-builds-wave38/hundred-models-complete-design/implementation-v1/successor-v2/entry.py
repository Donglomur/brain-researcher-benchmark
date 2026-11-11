#!/usr/bin/env python3
"""Bounded source bootstrap. Native work requires separately selected scientific authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('worker','reference','inspect'))
    ap.add_argument('--root',required=True);ap.add_argument('--source-bytes',type=int,required=True);ap.add_argument('--source-sha256',required=True)
    ap.add_argument('--request');ap.add_argument('--request-bytes',type=int);ap.add_argument('--request-sha256')
    ap.add_argument('--deadline-ns',type=int,required=True);ap.add_argument('--bootstrap-read-bytes',type=int,required=True)
    args=ap.parse_args();package=Path(__file__).absolute().parent;root=Path(args.root).absolute();used=0
    def read(base,name,n,sha,cap):
        nonlocal used
        if type(n)is not int or n<0 or n>cap:raise ValueError('bounded bootstrap extent')
        parts=name.split('/')
        if not name or Path(name).is_absolute() or any(x in ('','.','..') for x in parts):raise ValueError('contained bootstrap path')
        p=base/name
        if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap symlink forbidden')
        used+=n+1
        if used>args.bootstrap_read_bytes or time.monotonic_ns()>=args.deadline_ns:raise TimeoutError('bootstrap reservation/deadline')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=n:raise ValueError('ordinary exact bootstrap source')
            with os.fdopen(fd,'rb',closefd=False) as f:body=f.read(n+1)
            after=os.fstat(fd);named=p.lstat()
            fields=('st_dev','st_ino','st_size','st_nlink','st_mode','st_mtime_ns','st_ctime_ns')
            if any(getattr(before,k)!=getattr(after,k) or getattr(after,k)!=getattr(named,k) for k in fields):raise ValueError('unstable bootstrap source')
            if len(body)!=n or hashlib.sha256(body).hexdigest()!=sha:raise ValueError('bootstrap identity mismatch')
            if time.monotonic_ns()>=args.deadline_ns:raise TimeoutError('bootstrap late completion')
            return body
        finally:os.close(fd)
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate bootstrap key')
            out[k]=v
        return out
    raw=read(package,'RUNTIME_SOURCE.json',args.source_bytes,args.source_sha256,256*1024)
    manifest=json.loads(raw,object_pairs_hook=pairs)
    if manifest['schema']!='hundred_models_runtime_source_v1':raise ValueError('source manifest ABI')
    names=[x['path'] for x in manifest['files']]
    if len(names)!=len(set(names)) or 'entry.py' not in names:raise ValueError('complete unique bootstrap source')
    for x in manifest['files']:read(package,x['path'],x['bytes'],x['sha256'],4*1024*1024)
    request=None
    if args.mode!='inspect':request=json.loads(read(root,args.request,args.request_bytes,args.request_sha256,24*1024*1024),object_pairs_hook=pairs)
    sys.path.insert(0,str(package))
    from hundred_models_complete.guard import Budget,encoded,bare,need,ordinary
    from hundred_models_complete.source import install_manifest,source_bytes
    from hundred_models_complete.scope import validate_scope,compile_jobs
    install_manifest(package,manifest)
    limits={'read_bytes':args.bootstrap_read_bytes,'write_bytes':1024*1024,'work':1000000,'deadline_ns':args.deadline_ns} if request is None else request['limits']
    need(limits['deadline_ns']==args.deadline_ns,'one original deadline across bootstrap and programme')
    budget=Budget(**limits);budget.charge('read_bytes',used)
    scope=json.loads(source_bytes(package,'design/SCOPE.json',budget))
    if args.mode=='inspect':
        validate_scope(scope);print(json.dumps({'mode':'source_inspection_only','task_id':scope['task_id'],'models':99,'extra_SSL':1,'figures':22,'tables':2,'native_execution':False,'scientific_qualification':False,'budget':budget.snapshot()}));return
    from hundred_models_complete.runner import dispatch,execute_reference
    need(request['scope']==scope,'exact accepted full scope')
    plan=compile_jobs(scope,request['inputs']);authority=request['authority'];source_pin={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    need(authority['source']==source_pin and authority['plan']==bare(encoded(plan)),'external scientific selection of this exact full programme')
    need(request['inputs']['job_limits']['deadline_ns']==args.deadline_ns,'same child deadline')
    output=ordinary(root,request['output'])
    if args.mode=='worker':
        need(request['schema']=='hundred_models_job_request_v1' and request['plan']==plan,'unchanged full job request')
        result=dispatch(package,root,scope,request['inputs'],authority,plan,request['job'],request['completed'],budget,output)
    else:
        need(request['schema']=='hundred_models_reference_request_v1','reference request ABI')
        result=execute_reference(package,root,scope,request['inputs'],authority,budget,output,source_pin)
    print(json.dumps({'result':result,'budget':budget.snapshot(),'scientific_qualification':False},sort_keys=True))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        fields=('known_output_prefix','native_output_prefix','original_child_observation','campaign_prefix')
        print(json.dumps({'status':'failed','error':type(error).__name__,'message':str(error),'notes':getattr(error,'__notes__',[]),'custody':{k:getattr(error,k) for k in fields if hasattr(error,k)}},sort_keys=True),file=sys.stderr)
        raise
