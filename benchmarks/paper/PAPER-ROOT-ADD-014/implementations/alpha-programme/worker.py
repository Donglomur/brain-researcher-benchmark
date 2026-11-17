"""Fresh subprocess worker; parent captures and freezes every source before launch."""
import time
BOOT=time.monotonic()
import argparse
import json
from pathlib import Path
import signal
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('--selection',required=True);p.add_argument('--output',required=True);p.add_argument('--origin',required=True,type=float)
    a=p.parse_args();root=Path(__file__).absolute().parent
    if not 0<=BOOT-a.origin<120:raise TimeoutError('original unrenewed startup')
    previous={s:signal.getsignal(s) for s in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM)}
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise ValueError('fresh worker timer')
    def expired(*_):raise TimeoutError('original whole work clock')
    primary=None
    try:
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,a.origin+120-time.monotonic())
        sys.path.insert(0,str(root))
        import controller
        from common import capture,parse,pin
        with Path(a.selection).open('rb') as f:raw=f.read(1048577)
        if len(raw)>1048576:raise ValueError('bounded frozen selection')
        v=controller.selected(parse(raw))
        # Parent has immutable custody; engine reauthenticates the full tree every phase.
        end=a.origin+120+sum(v['producer_seconds'][c['mode']]+360 for c in controller.protocol.phases())+600
        if time.monotonic()>=a.origin+120:raise TimeoutError('original startup before clock handoff')
        signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
        b=json.loads((root/'BINDINGS.json').read_bytes())
        controller.execute(v,b,a.output,a.origin,root)
        if time.monotonic()>=end:raise TimeoutError('original worker publication deadline')
    except BaseException as e:primary=e;raise
    finally:
        failures=[]
        for action in [lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda s=s,h=h:signal.signal(s,h) for s,h in previous.items()]:
            try:action()
            except BaseException as e:failures.append(type(e).__name__)
        if failures:
            if primary is None:raise RuntimeError('worker alarm cleanup uncertainty:'+','.join(failures))
            primary.add_note('worker alarm cleanup uncertainty:'+','.join(failures))
if __name__=='__main__':main()
