"""Concrete explicit-authority dispatcher; registration does not authorize a run."""
import time
BOOT=time.monotonic()
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import encode,need

def dispatch(action,invocation,sha256,origin):
    need(0<=origin<=BOOT,'externally original clock, never a fresh retry allowance')
    if action=='run':
        import observe
        observe.BOOT=origin
        return observe.observe(invocation,sha256)
    if action=='prepare':
        from common import authority
        import prepare
        _,v,budget=authority(invocation,sha256,origin)
        return prepare.prepare(v,origin,budget)
    if action=='score':
        from common import authority
        import grade
        _,v,budget=authority(invocation,sha256,origin)
        return grade.score(v,origin,budget)
    raise ValueError('explicit run/prepare/score operation')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('run','prepare','score'));p.add_argument('--invocation',required=True);p.add_argument('--sha256',required=True);p.add_argument('--origin',type=float,default=BOOT);a=p.parse_args();result=dispatch(a.action,a.invocation,a.sha256,a.origin);print(encode(result).decode(),end='')
    if result.get('success')is False:raise SystemExit(2)
if __name__=='__main__':main()
