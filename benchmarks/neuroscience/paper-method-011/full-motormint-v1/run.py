#!/usr/bin/env python3
"""Portable captured-source MotorMINT complete-paper entry; no project-path import fallback."""
import argparse
import builtins
import hashlib
import json
import os
import stat
import sys
import time
import types

sys.dont_write_bytecode=True


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bytes',type=int,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('command',choices=('inspect','prepare','run','reference','candidate','collect','grade','report'))
    parser.add_argument('--program');parser.add_argument('--output');parser.add_argument('--review')
    parser.add_argument('--deployment');parser.add_argument('--other-reserve-bytes',type=int)
    a=parser.parse_args(argv)
    if a.command in ('reference','candidate','collect','grade','report'):
        raise ValueError('This method selects a product from the same live complete MotorMINT invocation; it is not an independently executable scientific stage. Use run.')
    root=os.path.dirname(os.path.abspath(__file__))
    clock=None;limits={'read_bytes':16777216,'write_bytes':2097152,'metadata_bytes':268435456,'open_attempts':10000,'objects':4096}
    counters={k:0 for k in limits};records=[]
    def need(ok,reason):
        if not ok:raise ValueError(reason)
    def tick():
        if clock is not None:
            need(clock['origin_ns']<=time.monotonic_ns()<clock['scientific_ns'],'original bootstrap cutoff')
    def charge(**values):
        for k,v in values.items():counters[k]+=v
        need(all(counters[k]<=limits[k] for k in counters),'bootstrap selected source capacity')
    def parse(raw):
        def pairs(items):
            out={}
            for k,v in items:
                need(k not in out,'duplicate bootstrap JSON key');out[k]=v
            return out
        return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite bootstrap JSON')))
    def capture(path,expected=None,maximum=1048576,private=False):
        need(type(path) is str and path.startswith('/') and '\\' not in path
             and all(x not in ('','.','..') for x in path.split('/')[1:]),'canonical bootstrap path')
        charge(open_attempts=len(path.split('/'))+1,objects=1)
        owned=[];primary=None;raw=None
        def ident(s):return [s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        try:
            tick();fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);owned.append(fd)
            for part in path.split('/')[1:-1]:
                fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);owned.append(fd)
            parent=fd;fd=os.open(path.rsplit('/',1)[1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent);owned.append(fd)
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=maximum,'ordinary bounded bootstrap file')
            if private:need(before.st_uid==os.getuid() and stat.S_IMODE(before.st_mode)&0o077==0,'protected original review')
            if expected is not None:need(before.st_size==expected['bytes'],'expected bootstrap extent')
            charge(read_bytes=before.st_size+1,metadata_bytes=2*before.st_size+4096)
            chunks=[];remaining=before.st_size
            while remaining:
                tick();b=os.read(fd,min(65536,remaining));need(b,'early bootstrap EOF');chunks.append(b);remaining-=len(b)
            need(os.read(fd,1)==b'','exact bootstrap EOF');raw=b''.join(chunks)
            p={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            need(expected is None or p==expected,'changed bootstrap content')
            need(ident(before)==ident(os.fstat(fd))==ident(os.stat(path.rsplit('/',1)[1],dir_fd=parent,follow_symlinks=False)), 'stable bootstrap object')
            records.append({'path':path,'pin':p,'identity':ident(before),'EOF':True})
        except BaseException as error:primary=error
        while owned:
            fd=owned.pop()
            try:os.close(fd)
            except BaseException as error:
                if primary is None:primary=error
                else:primary.bootstrap_secondary=getattr(primary,'bootstrap_secondary',[])+[type(error).__name__]
        if primary is not None:
            primary.central_bootstrap_prefix={'counters':dict(counters),'records':records};raise primary
        tick();return raw
    review=None;review_pin=None
    if a.command!='inspect':
        need(all(v is not None for v in (a.program,a.output,a.review,a.deployment,a.other_reserve_bytes)), 'explicit complete run operands')
        # This one <=32KiB protected issuer record is the declared installed
        # bootstrap audit boundary. Its original clock was chosen by the issuer
        # before invocation; the immediate post-read check cannot prove kernel
        # blocking latency or external issuer competence.
        r=capture(os.path.abspath(a.review),maximum=32768,private=True);review=parse(r)
        review_pin={'bytes':len(r),'sha256':hashlib.sha256(r).hexdigest()}
        clock=review['clock'];need(set(clock)=={'origin_ns','scientific_ns','closure_ns','outer_ns'}
            and all(type(x) is int for x in clock.values())
            and 0<=clock['origin_ns']<clock['scientific_ns']<=clock['closure_ns']<=clock['outer_ns'],'selected original clock')
        limits=review['central_limits'];need(set(limits)==set(counters) and all(type(x) is int and x>0 for x in limits.values()),'finite original source ledger')
        need(all(counters[k]<=limits[k] for k in counters),'initial review capture in same prepaid ledger');tick()
    need(0<a.source_bytes<=1048576 and len(a.source_sha256)==64,'bounded selected package manifest')
    body=capture(root+'/SOURCE_MANIFEST.json',{'bytes':a.source_bytes,'sha256':a.source_sha256})
    charge(metadata_bytes=65*len(body));manifest=parse(body)
    need(type(manifest['files']) is dict and 1<=len(manifest['files'])<=512,'complete bounded portable closure')
    deferred={r['path'] for r in manifest['deferred_dependencies']}
    files={}
    for name,p in manifest['files'].items():
        need(type(name) is str and not name.startswith('/') and '\\' not in name
             and all(x not in ('','.','..') for x in name.split('/')),'canonical portable source name')
        need(name not in deferred and not any(name=='shared/'+d for d in deferred),'deferred dependency body is never source-captured')
        need(set(p)=={'bytes','sha256'} and p['bytes']<=1048576,'bounded exact source pin')
        files[name]=capture(root+'/'+name,p)
    need('run.py' in files,'original entry belongs to frozen closure')
    central=manifest['central_modules'];loaded={}
    basic={'__future__','argparse','builtins','copy','importlib','hashlib','json','os','stat','sys','time','types','math','pathlib','re'}
    def load(name):
        need(name in central,'closed central module')
        if name in loaded:return loaded[name]
        file=central[name];raw=files[file];charge(metadata_bytes=65*len(raw))
        module=types.ModuleType('_motormint_portable_'+name);module.__file__=root+'/'+file
        def imp(n,g=None,l=None,fromlist=(),level=0):
            need(level==0,'closed central absolute imports')
            if n in central:return load(n)
            need(n in basic or n.split('.')[0] in basic,'selected central basic import')
            return builtins.__import__(n,g,l,fromlist,level)
        b=dict(vars(builtins));b['__import__']=imp;module.__dict__['__builtins__']=b
        loaded[name]=module
        exec(compile(raw,module.__file__,'exec',dont_inherit=True),module.__dict__)
        return module
    # Load all central definitions before adopting the exact counter prefix, so
    # subsequent lazy source execution cannot escape the actual Meter.
    for name in central:load(name)
    common=loaded['central_common'];meter=common.Meter(limits,clock);meter.charge(**counters)
    sources=loaded['central_sources'].Sources(root,manifest,body,files,meter)
    failure=None
    if a.command=='inspect':
        result=sources.inspect();result['canonical_source_routes']=loaded['central_routes'].source_preflight(sources)
        result['source_meter_after_preflights']=meter.snapshot()
    else:
        failure=common.Meter(review['failure_limits'],review['clock'])
        return invoke_and_deliver(sources,{
            'command':a.command,'program':os.path.abspath(a.program),'output':os.path.abspath(a.output),
            'deployment':os.path.abspath(a.deployment),'other_reserve_bytes':a.other_reserve_bytes},
            review,review_pin,loaded['central_engine'],loaded['central_failure'],common,failure)
    return deliver_result(result,common,meter)


def deliver_result(result,common,meter):
    meter.charge(metadata_bytes=3*1048576,write_bytes=1048577)
    out=common.encode(result,1048576);meter.tick('outer')
    print(out.decode('ascii'),flush=True);meter.tick('outer');return 0


def retain_error(error,sources,arguments,review_pin,result,failure_tools,failure):
    prefix=getattr(error,'central_failure',None)
    if prefix is None:
        prefix={'failure_stage':'final_delivery' if result is not None else 'before_engine_prefix',
            'source':sources.manifest_pin,'review':review_pin,'meter':sources.meter.snapshot(),
            'inclusive_cost':None if result is None else result.get('inclusive_central_cost'),
            'measurement_failure':'measurement status unavailable before engine failure prefix' if result is None else None,
            'cleanup_failures':getattr(error,'secondary',[]),
            'owned_output':{'path':arguments['output'],'creation_support':'see published/prepared records'},
            'published':[] if result is None else result.get('products',{}),
            'prepared':None if result is None else result.get('prepared_request',result.get('request')),
            'outer':None if result is None else result.get('outer'),'runtime_output_created':None}
    error.central_failure=prefix
    failure_tools.emit(error,prefix,failure)


def deliver_or_retain(result,sources,arguments,review_pin,failure_tools,common,failure):
    """Actual terminal-delivery boundary; failed delivery preserves the original result."""
    try:return deliver_result(result,common,sources.meter)
    except BaseException as error:
        retain_error(error,sources,arguments,review_pin,result,failure_tools,failure)
        raise


def invoke_and_deliver(sources,arguments,review,review_pin,engine,failure_tools,common,failure):
    """The actual CLI caller boundary, shared by retained failure-path controls."""
    try:result=engine.execute(sources,arguments,review,review_pin,failure_meter=failure)
    except BaseException as error:
        retain_error(error,sources,arguments,review_pin,None,failure_tools,failure)
        raise
    return deliver_or_retain(result,sources,arguments,review_pin,failure_tools,common,failure)



if __name__=='__main__':
    raise SystemExit(main())
