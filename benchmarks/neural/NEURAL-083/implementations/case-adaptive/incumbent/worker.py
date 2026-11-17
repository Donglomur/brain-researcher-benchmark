"""Captured complete54x2x4x3 worker; inherits one original enclosing clock."""
import time
ENTRY=time.monotonic()
import argparse,hashlib,json,os,signal,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
BOOT={'bytes': 1613, 'sha256': '7854891fba8402ac945edc6ad9d792be1b974521349dcc190a71f308798ab027'}
def boot():
    p=HERE/'bootstrap.py'
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('bootstrap path')
    with p.open('rb') as f:raw=f.read(BOOT['bytes']+1)
    if len(raw)!=BOOT['bytes'] or hashlib.sha256(raw).hexdigest()!=BOOT['sha256']:raise ValueError('bootstrap pin')
    m=types.ModuleType('neural083_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

def main():
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','origin','worker-end'):p.add_argument('--'+name,required=True)
    a=p.parse_args();origin=float(a.origin);end=float(a.worker_end)
    if not origin<=ENTRY<end:raise ValueError('inherited original clock')
    def stop(*_):raise TimeoutError('original worker deadline or interruption')
    old={};result=2
    try:
        for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):
            old[sig]=signal.getsignal(sig);signal.signal(sig,stop)
        signal.setitimer(signal.ITIMER_REAL,max(.001,min(end,origin+120)-time.monotonic()))
        source=json.loads(a.source_pin);c,manifest,bodies,cost=boot().load(HERE,source,min(end,origin+120))
        contracts=c.module(bodies,'contracts.py',HERE,c=c)
        scientific=c.module(bodies,'scientific_protocol.py',HERE)
        store=c.module(bodies,'store.py',HERE,c=c,contracts=contracts,scientific=scientific)
        policy=c.module(bodies,'policy.py',HERE,c=c,contracts=contracts)
        selection_raw=c.capture(a.selection,32768,json.loads(a.selection_pin),lambda:c.before(end));s=policy.selection(c.parse(selection_raw),source)
        c.need(end==origin+s['limits']['whole_seconds']-s['limits']['observer_seconds'],'same original worker endpoint')
        c.before(min(end,origin+120));signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        native=c.module(bodies,'native.py',HERE,c=c);native.IMAGE=s['image']
        controller=c.module(bodies,'controller.py',HERE,c=c,policy=policy,contracts=contracts,store=store,native=native)
        value=controller.run(s,source,bodies,origin,end,cost+len(selection_raw)+1)
        c.before(end);print(json.dumps(value,separators=(',',':')),flush=True);c.before(end);result=0
    except BaseException:result=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:result=2
        for sig,handler in old.items():
            try:signal.signal(sig,handler)
            except BaseException:result=2
    return result if time.monotonic()<end else 2
if __name__=='__main__':raise SystemExit(main())
