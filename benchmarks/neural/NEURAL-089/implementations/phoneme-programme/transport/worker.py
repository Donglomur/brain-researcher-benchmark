"""Captured NEURAL089 controller worker; one inherited original clock."""
import time
ENTRY=time.monotonic()
import argparse,hashlib,json,os,signal,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BOOT_PIN={'bytes': 1734, 'sha256': 'bf4545385dd30a3d01884ad184e6df80d4cab431d8c0f996265544f70a2077f4'}

def boot(deadline):
    p=ROOT/'transport/bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('ordinary bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT_PIN['bytes']+1)
    if len(raw)!=BOOT_PIN['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT_PIN['sha256']:raise ValueError('bootstrap pin')
    if time.monotonic()>=deadline:raise TimeoutError('original startup clock')
    m=types.ModuleType('neural089_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__)
    return m,len(raw)+1

def modules(c,bodies):
    science=c.module(bodies,'program/science.py',ROOT,c=c,source_bodies=bodies)
    packet=c.module(bodies,'program/packet.py',ROOT,c=c,science=science)
    policy=c.module(bodies,'program/policy.py',ROOT,c=c,packet=packet)
    outputs=c.module(bodies,'program/outputs.py',ROOT,c=c,packet=packet,policy=policy,science=science)
    native=c.module(bodies,'transport/native.py',ROOT,c=c)
    return science,packet,policy,outputs,native

def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','origin','worker-end'):p.add_argument('--'+name,required=True)
    a=p.parse_args();origin=float(a.origin);end=float(a.worker_end)
    if not origin<=ENTRY<end:raise ValueError('inherited original clock')
    def stop(*_):raise TimeoutError('original worker deadline or interruption')
    for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    startup=min(end,origin+120)
    signal.setitimer(signal.ITIMER_REAL,max(.001,startup-time.monotonic()));result=2
    try:
        source=json.loads(a.source_pin);loader,boot_cost=boot(startup)
        c,manifest,bodies,cost=loader.load(ROOT,source,startup)
        if c.pin(bodies['transport/worker.py'])!=globals().get('_CAPTURED_WORKER_PIN'):raise ValueError('executing captured worker source join')
        if manifest['files']['transport/bootstrap.py']!=BOOT_PIN:raise ValueError('complete bootstrap source join')
        science,packet,policy,outputs,native=modules(c,bodies)
        raw=c.capture(a.selection,32768,json.loads(a.selection_pin),lambda:c.before(startup))
        s=policy.selection(c.parse(raw),source)
        c.need(end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'same original worker endpoint')
        controller=c.module(bodies,'program/controller.py',ROOT,c=c,packet=packet,policy=policy,outputs=outputs,native=native,science=science,SOURCE_READ_CHARGE=cost+boot_cost+len(raw)+1)
        c.before(startup);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        value=controller.run(s,source,bodies,origin,end)
        c.before(end);encoded=c.encoded(value);c.need(len(encoded)<=65536,'bounded compact worker result')
        sys.stdout.buffer.write(encoded);sys.stdout.buffer.flush();c.before(end);result=0
    except BaseException:result=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:result=2
    return result if time.monotonic()<end else 2
if __name__=='__main__':raise SystemExit(main())
