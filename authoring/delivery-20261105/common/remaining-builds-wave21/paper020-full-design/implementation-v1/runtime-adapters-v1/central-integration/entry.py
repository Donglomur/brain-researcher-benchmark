"""Captured central source entry. No scientific imports before fixed routing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

OBSERVING = False
BOOTSTRAP_PIN = {'bytes': 5026, 'sha256': 'b5f5368c32a629ba67b88920cbb37d0adfd6c19417f68a4eead5baa21909a330'}
IO_PIN = {'bytes': 6450, 'sha256': '7ce9e79b0cdcc155cb7fde5316b932b77b99dae9f5ed3cd6444a57387e456a22'}

def _read(path,pin):
    current=Path('/')
    for part in path.parts[1:]:
        current=current/part
        if current.is_symlink():raise ValueError('source symlink forbidden')
    before=path.lstat()
    if not(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size==pin['bytes']):raise ValueError('source extent differs')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        opened=os.fstat(fd)
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(pin['bytes']+1)
        after,named=os.fstat(fd),path.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        if not all(getattr(before,k)==getattr(opened,k)==getattr(after,k)==getattr(named,k)for k in fields):raise ValueError('source changed')
        if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:raise ValueError('source bytes differ')
        return raw
    finally:os.close(fd)

def _module(raw,path,name,**bindings):
    m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(bindings);sys.modules[name]=m
    exec(compile(raw,str(path),'exec'),m.__dict__);return m

def main():
    start=time.monotonic_ns()
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('qualified -I -S -B interpreter required')
    parser=argparse.ArgumentParser()
    for name in ('program','output','review','source-sha256'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--source-bytes',type=int,required=True);parser.add_argument('--other-reserve-bytes',type=int,required=True)
    a=parser.parse_args();here=Path(__file__).absolute().parent
    io=_read(here/'common_io.py',IO_PIN);boot=_read(here/'bootstrap.py',BOOTSTRAP_PIN)
    u=_module(io,here/'common_io.py','_paper020_central_io');b=_module(boot,here/'bootstrap.py','_paper020_central_bootstrap',u=u)
    reader=u.Reader(start,start+120_000_000_000,read_limit=160_000_000,write_limit=100_000_000)
    reader.reserve_read(len(io)+len(boot));reader.read_observed+=len(io)+len(boot);reader.hash_bytes+=len(io)+len(boot)
    source=u.only_pin({'bytes':a.source_bytes,'sha256':a.source_sha256})
    env=b.capture(here,source,reader,start,sys.executable)
    expected=env['here']/('observer_entry.py'if OBSERVING else'entry.py')
    u.need(Path(__file__).absolute()==expected and os.getcwd()==str(env['repo']),'exact fixed central entry/root required')
    env['operands']={'{program}':a.program,'{output}':a.output,'{review}':a.review,'{other_reserve_bytes}':str(a.other_reserve_bytes)}
    registered=env['registration'].qualify(env,reader)
    b.capture_parent(env,reader)
    # The first operator operand access occurs strictly after the fixed gate.
    review,_=reader.json(u.absolute(a.review),131072)
    argv=[sys.executable,*sys.orig_argv[1:]]
    first,command,mode=env['registration'].campaign(env,reader,registered,review,argv,os.getcwd(),observing=OBSERVING)
    operands=env['authority'].admit(env,reader,u.absolute(a.program),a.output,mode,registered,observing=OBSERVING)
    if OBSERVING:
        again=env['registration'].qualify(env,reader);u.need(again==registered,'registry changed before post-exit read')
        second,command,_=env['registration'].campaign(env,reader,again,review,argv,os.getcwd(),observing=True)
        u.need({k:v for k,v in first.items()if k!='metadata_read_charge_bytes'}=={k:v for k,v in second.items()if k!='metadata_read_charge_bytes'},'current observation route changed')
        value=env['external'].observe(env,reader,operands,u.absolute(a.output),second,command)
    else:
        env['route_receipt']=env['registration'].repeat(env,reader,registered,review,first,argv,os.getcwd())
        value=env['dispatch'].run(env,reader,operands,u.absolute(a.output))
    reader.tick();sys.stdout.write(json.dumps(value,sort_keys=True,allow_nan=False)+'\n');sys.stdout.flush()

if __name__=='__main__':main()
