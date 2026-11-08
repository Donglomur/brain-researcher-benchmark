"""Actual central entry: captured source and fixed qualification before operands."""
import time
ENTRY_START=time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types

HERE=Path(__file__).absolute().parent
ACTUAL_ARGV=list(sys.orig_argv)
ACTUAL_CWD=os.getcwd()
BOOTSTRAP_PINS={'common_io.py': {'bytes': 9896, 'sha256': 'fc29aecda865c5f63c8865282cf1a9043ce610ce3ef01dc38a315df2907e8a43'}, 'bootstrap.py': {'bytes': 5079, 'sha256': '7b9efa0a82983d189f86b4156d3b361c69b0551d334f076714fc2d6cd3a2f61f'}}
BOOTSTRAP_RESERVED=0

def need(ok,message):
    if not ok:raise ValueError(message)

def bootstrap_read(name):
    global BOOTSTRAP_RESERVED
    expected=BOOTSTRAP_PINS[name];path=HERE/name
    need(time.monotonic()<ENTRY_START+120,'bounded source bootstrap guard')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    leaf=None
    try:
        for part in path.parent.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        leaf=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        a=os.fstat(leaf);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==expected['bytes'],'exact bootstrap source')
        BOOTSTRAP_RESERVED+=a.st_size+1;need(BOOTSTRAP_RESERVED<=262144,'complete bootstrap source cap')
        body=b'';left=a.st_size
        while left:
            need(time.monotonic()<ENTRY_START+120,'source bootstrap deadline')
            part=os.read(leaf,min(left,65536));need(part,'complete bootstrap source');body+=part;left-=len(part)
        signature=lambda s:tuple(getattr(s,k)for k in('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
        need(not os.read(leaf,1) and signature(a)==signature(os.fstat(leaf))==signature(os.stat(path.name,dir_fd=fd,follow_symlinks=False))
            and hashlib.sha256(body).hexdigest()==expected['sha256'],'stable exact captured bootstrap')
    finally:
        if leaf is not None:os.close(leaf)
        os.close(fd)
    need(time.monotonic()<ENTRY_START+120,'bootstrap final close deadline')
    return body

def load(raw,path,name,**bindings):
    m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(bindings);sys.modules[name]=m
    exec(compile(raw,str(path),'exec'),m.__dict__);return m

def main(argv=None):
    parser=argparse.ArgumentParser()
    for k in ('program','review','output','source-sha256'):parser.add_argument('--'+k,required=True)
    for k in ('source-bytes','other-reserve-bytes'):parser.add_argument('--'+k,type=int,required=True)
    args=parser.parse_args(argv)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated/no-site/no-bytecode central interpreter')
    def expired(*_):raise TimeoutError('selected central absolute deadline')
    old_timer=signal.getitimer(signal.ITIMER_REAL)
    need(old_timer==(0.0,0.0),'caller must own outer deadline without inherited ambiguous timer')
    old_handlers={sig:signal.signal(sig,expired)for sig in(signal.SIGALRM,signal.SIGINT,signal.SIGTERM)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,ENTRY_START+120-time.monotonic()))
    env=None;reader=None
    try:
        io=load(bootstrap_read('common_io.py'),HERE/'common_io.py','neural010_central_io')
        boot=load(bootstrap_read('bootstrap.py'),HERE/'bootstrap.py','neural010_central_bootstrap',u=io)
        # Runtime source allowance is independent of the authoring grant. This
        # bounded startup allowance covers actual shared qualification rereads.
        reader=io.Reader(read_limit=268435456,write_limit=1048576,deadline=ENTRY_START+120)
        reader.reserve_read(BOOTSTRAP_RESERVED)
        reader.read_observed=BOOTSTRAP_RESERVED-2;reader.hash_bytes=BOOTSTRAP_RESERVED-2
        env=boot.capture(HERE,{'bytes':args.source_bytes,'sha256':args.source_sha256},reader,ENTRY_START,sys.executable)
        def select_outer_timer(end):
            io.need(time.monotonic()<end,'selected absolute outer readback deadline')
            signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        env['select_outer_timer']=select_outer_timer
        result=env['dispatch'].execute({**vars(args),'actual_argv':ACTUAL_ARGV,'actual_cwd':ACTUAL_CWD},env,reader)
        sys.stdout.buffer.write(io.bounded_canonical(result,65536)+b'\n');sys.stdout.buffer.flush()
        reader.tick()
        return 0
    except BaseException as error:
        costs=(env.get('execution_reader',reader).report()if env is not None else
               reader.report()if reader is not None else{'bootstrap_read_reserved':BOOTSTRAP_RESERVED})
        record={'status':'refused','error_type':type(error).__name__,'costs':costs,'automatic_retry':False,
                'unknown_costs_not_zero':True,'scientifically_qualified':False}
        if env is not None:
            record['reserved_partitions']=env.get('reserved_partitions',{})
            record['phase_dispositions']={k:{a:b for a,b in row.items()if a in ('entered','completed','launch_attempted','failure_type')}for k,row in env.get('phase_states',{}).items()}
            if env.get('execution_reader') is not None and env.get('phase_states'):
                try:
                    target=io.absolute(args.output)/'CENTRAL_FAILURE.json'
                    raw=io.bounded_canonical({'error_type':type(error).__name__,'phases':env['phase_states'],'known_metadata_costs':costs,'retry':False,'unknown_survivors_require_separate_inspection':True},16777216)
                    record['retained_failure']=env['execution_reader'].write_new(target,raw,16777216)
                except BaseException:
                    record['failure_publication']='unknown; original process-local evidence may be lost on exit'
        if hasattr(error,'report'):
            try:record['captured_component_failure']=error.report()
            except BaseException:record['captured_component_failure']='unavailable; not zero'
        sys.stderr.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n');return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,handler in old_handlers.items():signal.signal(sig,handler)

if __name__=='__main__':raise SystemExit(main())
