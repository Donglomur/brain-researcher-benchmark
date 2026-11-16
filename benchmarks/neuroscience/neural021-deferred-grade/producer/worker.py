"""Root-selected full92 worker; inherits the observer's original absolute clock."""
import time
ENTRY=time.monotonic()
import argparse,hashlib,json,os,signal,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
BOOT={'bytes': 1613, 'sha256': '4dcfda207b80696918afd539804ab666c384e2cccf2d17ea767c446a0ae2d5c0'}
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural021_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m
def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','origin','worker-end'):p.add_argument('--'+name,required=True)
    a=p.parse_args();origin=float(a.origin);end=float(a.worker_end)
    if not origin<=ENTRY<end:raise ValueError('inherited original clock')
    def stop(*_):raise TimeoutError('original worker deadline or interruption')
    for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
    result=2
    try:
        source=json.loads(a.source_pin);c,manifest,bodies,_=boot().load(HERE,source,min(end,origin+120))
        policy=c.module(bodies,'policy.py',HERE,c=c)
        s=policy.selection(c.parse(c.capture(a.selection,32768,json.loads(a.selection_pin),lambda:c.before(end))),source)
        c.need(end==origin+policy.whole(s['fit_seconds'],s['infer_seconds'])-20,'same original worker endpoint')
        bundle=c.module(bodies,'output_bundle.py',HERE)
        native=c.module(bodies,'native.py',HERE,c=c,bundle=bundle)
        controller=c.module(bodies,'controller.py',HERE,c=c,policy=policy,native=native)
        value=controller.run(s,source,bodies,manifest,origin,end)
        c.before(end);print(json.dumps(value,separators=(',',':')),flush=True);c.before(end);result=0
    except BaseException:result=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:result=2
    return result if time.monotonic()<end else 2
if __name__=='__main__':raise SystemExit(main())
