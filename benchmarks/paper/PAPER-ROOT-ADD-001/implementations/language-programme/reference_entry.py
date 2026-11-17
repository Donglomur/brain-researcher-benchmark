"""Future exact operator recipes; no producer or fit runs during source construction."""
import sys
from pathlib import Path
sys.path[:0]=['/trusted','/trusted/operator','/trusted/public']
from entry_common import main_args,need

def produce_native():
    import numpy as np
    import reference
    from delivery_io import read,decode,pin,put
    from protocol import SESSIONS,PROTOCOL_SHA,design_check
    from prepare import load_session
    raw=read('/input/prepared/DESIGN.json',500000);d=design_check(decode(raw));rows=[]
    # Exact unchanged reference.compute and load_session, all original sessions.
    for s in SESSIONS:
        result=reference.compute(load_session('/input/prepared',d,s));target=Path('/output')/(s+'.npz')
        np.savez_compressed(target,**result);target.chmod(0o444)
        rows.append({'id':s,'path':target.name,**pin(read(target,32*1024**2))})
    put('/output/submission.json',{'schema':'language_submission_v1','mode':'native','protocol_sha256':PROTOCOL_SHA,'design_sha256':pin(raw)['sha256'],'files':rows},500000)

def main():
    r,v=main_args();need(v['role'] in ('reference_native','reference_strict'),'operator-only reference role')
    if r['mode']=='native':
        need(v['role']=='reference_native' and r['episode'] is None,'whole native reference');produce_native()
    else:
        need(v['role']=='reference_strict','four-baseline episode')
        import baseline
        sys.argv=['baseline.py','--case','/input/case.json','--root','/input','--output','/output/baselines.npz']
        baseline.main()
if __name__=='__main__':main()
