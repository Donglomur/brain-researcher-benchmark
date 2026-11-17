"""Literal CLI entry. Root/native caller must pin this entry before execution."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('native','collect','observe','grade','prepare'),required=True)
    for key in ('source-root','manifest','manifest-pin','bootstrap-pin','request','request-pin','origin','deadline','read-cap','write-cap'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args(argv)
    origin=float(args.origin);deadline=float(args.deadline);read_cap=int(args.read_cap);write_cap=int(args.write_cap)
    if not (math.isfinite(origin) and math.isfinite(deadline) and origin<deadline and read_cap>0 and write_cap>0):
        raise ValueError('explicit original source/runtime limits')
    state={'read_reserved':0,'read_observed':0,'attempted_paths':[]}
    def tick():
        if not origin<=time.monotonic()<deadline: raise ValueError('original entry deadline')
    def captured(path,expected,limit):
        tick();n=expected['bytes']
        if type(n)is not int or not 0<=n<=limit or state['read_reserved']+n+1>read_cap: raise ValueError('entry read cap')
        state['read_reserved']+=n+1;state['attempted_paths'].append(str(path))
        path=Path(path)
        if not path.is_absolute() or '..' in path.parts: raise ValueError('entry canonical path')
        for parent in reversed(path.parents):
            if not stat.S_ISDIR(os.lstat(parent).st_mode): raise ValueError('entry ordinary parents')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=n or before.st_mode&0o222:
                raise ValueError('entry sealed exact source')
            parts=[];left=n
            while left:
                tick();body=os.read(fd,min(left,65536));state['read_observed']+=len(body)
                if not body: raise ValueError('entry short source')
                parts.append(body);left-=len(body)
            extra=os.read(fd,1);state['read_observed']+=len(extra)
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if extra or stamp(before)!=stamp(os.fstat(fd)) or stamp(before)!=stamp(os.lstat(path)): raise ValueError('entry custody changed')
            body=b''.join(parts)
            if hashlib.sha256(body).hexdigest()!=expected['sha256']: raise ValueError('entry source hash')
            tick();return body
        finally:
            primary=sys.exception()
            try:os.close(fd)
            except BaseException as error:
                if primary is not None:raise BaseExceptionGroup('entry read and close',[primary,error]) from None
                raise
    ctx=None
    try:
        bootstrap_pin=json.loads(args.bootstrap_pin);manifest_pin=json.loads(args.manifest_pin)
        bootstrap=captured(Path(args.source_root)/'program/bootstrap.py',bootstrap_pin,1<<20)
        namespace={'__name__':'_neural058_bootstrap'};tick();exec(compile(bootstrap,'captured-bootstrap.py','exec'),namespace);tick()
        ctx={'origin':origin,'deadline':deadline,'read_cap':read_cap-state['read_reserved'],
             'read_reserved':0,'read_observed':0,'attempted_paths':[]}
        frozen=namespace['load'](args.source_root,args.manifest,manifest_pin,ctx)
        if frozen['manifest'].get('task_id')!='NEURAL-058':raise ValueError('actual task manifest')
        state['read_reserved']+=ctx['read_reserved'];state['read_observed']+=ctx['read_observed'];ctx=None
        from core import Budget,capture,parse,pin,encoded
        budget=Budget(origin,deadline,read_cap,write_cap);budget.reserve_read(state['read_reserved'])
        raw,_=capture(args.request,json.loads(args.request_pin),4<<20,budget,readonly=True);request=parse(raw)
        if request['origin']!=origin or request['deadline']!=deadline or request['source']!=manifest_pin:
            raise ValueError('entry exact selected request/source/clocks')
        if args.mode=='native':
            from worker import run
        elif args.mode=='collect':
            from controller import run
        elif args.mode=='observe':
            from outer import run
        elif args.mode=='grade':
            from grading import run
        else:
            from prepare_entry import run
        result=run(request,budget,frozen)
        budget.tick();print(encoded({'schema':'neural058_entry_terminal_v1','status':'complete','mode':args.mode,
                                   'result':result,'source':manifest_pin,'source_reads':state,
                                   'budget_before_terminal':budget.record()}).decode(),flush=True)
        budget.tick();return 0
    except BaseException as error:
        # This terminal is a bounded diagnostic, never a completion/hold-release
        # receipt. Its external bytes/EOF and process outcome remain independently
        # observed; failed terminal publication may itself leave closure unknown.
        print(json.dumps({'schema':'neural058_entry_terminal_v1','status':'failed','mode':args.mode,
                          'error_type':type(error).__name__,'source_reads':state,'source_capture_in_progress':ctx,
                          'failure_record':getattr(error,'failure_record',None),
                          'known_budget':None if 'budget' not in locals() else {'read_reserved':budget.read_bytes,'write_reserved':budget.write_bytes},
                          'complete_accounting':False},sort_keys=True),flush=True)
        return 2


if __name__=='__main__': raise SystemExit(main())
