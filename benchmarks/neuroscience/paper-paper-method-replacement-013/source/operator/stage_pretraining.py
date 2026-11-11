"""Train-partition neural/video-only corpus; no behavior labels or test windows.

This is the prospective leakage-resistant pretraining projection. It does not
assert that the paper's original pretraining used these identical partitions.
"""
import sys,io,argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from contract import *
from stage import windows,npy_size
import numpy as np

def stage_pretraining(q,target,observations,cohort,output,max_bytes,production=True):
    query(q,production);require(cohort in COHORTS,'one declared cortical cohort');out=fresh(output)
    target_binding(q,target)
    c=next(c for c in q['cases'] if c['definition']['id']==f'{cohort}--blocked_speed--improved--100')
    rows=[r for r in rows_for(q,c) if r['split']=='train'];records={r['id']:r for r in target['bridge']['recordings']}
    n=len(rows);neurons=q['cohorts'][cohort]['neurons'];dims={tuple(records[r['recording']]['arrays']['video']['shape'][1:]) for r in rows};require(len(dims)==1,'common video geometry')
    shapes={'neural_history':([n,30,neurons],'<i4'),'neural_current':([n,10,neurons],'<i4'),'video':([n,4,*next(iter(dims))],'|u1')}
    rowspec=[{'path':k+'.npy','bytes':npy_size(*v),'sha256':'0'*64,'shape':v[0],'dtype':v[1]} for k,v in shapes.items()]
    info={'schema':'neuroformer_pretraining_view_v1','cohort':cohort,'files':rowspec,'behavior_labels_included':False,'validation_or_test_included':False,
      'isolation_qualified':False,'policy':'prospective blocked-plan training windows only; original pretraining exposure unqualified'}
    require(type(max_bytes) is int and sum(x['bytes'] for x in rowspec)+len(encode(info))<=max_bytes,'exact pretraining output cap before reads')
    captured={}
    for name,(shape,dtype) in shapes.items():
        a=windows(rows,records,observations,name);require(list(a.shape)==shape and a.dtype.str==dtype,'pretraining geometry')
        b=io.BytesIO();np.save(b,a,allow_pickle=False);captured[name+'.npy']=b.getvalue()
    for d in rowspec:d['sha256']=hashlib.sha256(captured[d['path']]).hexdigest()
    out.mkdir(mode=0o700)
    for name,body in captured.items():(out/name).write_bytes(body)
    save(out/'PRETRAINING.json',info);return info

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ('query','query-sha256','target','observations','cohort','output'):a.add_argument('--'+k,required=True)
    a.add_argument('--max-bytes',type=int,required=True);x=a.parse_args();b=capture(x.query);require(hashlib.sha256(b).hexdigest()==x.query_sha256,'trusted query')
    stage_pretraining(decode(b),load(x.target),x.observations,x.cohort,x.output,x.max_bytes)
if __name__=='__main__':main()
