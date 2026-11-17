"""One-person/one-arm projection; complete pool remains operator-private."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from protocol import SUBJECTS,ARMS,FIT,VALIDATION,QUERY
from io_contract import capture,decode
import arrays
from signals_core import standardize_fit
from prepare_pool import Writer,need


def design(nuisance,ocular,dynamic,arm,fit_indices,query_indices):
    need(arm in ARMS,'Fixed arm')
    n=np.asarray(nuisance,float);e=np.asarray(ocular,float);d=np.asarray(dynamic,float)
    need(n.ndim==e.ndim==2 and len(n)==len(e)==len(d) and d.shape[1:]==(30,192),'Same video axes and dynamic geometry')
    parts=[n]
    if arm in ('nuisance_eye','full','full_shift500ms'):parts.append(e)
    if arm in ('nuisance_dynamic','full','full_shift500ms'):
        d=d.copy()
        if arm=='full_shift500ms':d[query_indices]=np.roll(d[query_indices],5,axis=1)
        parts.append(d.reshape(len(d),-1))
    x=np.concatenate(parts,axis=1)
    # Query shift occurs BEFORE applying the unchanged FIT-coordinate scaler.
    # Training/validation designs and selection therefore match full exactly.
    return standardize_fit(x,fit_indices)[0]


def local(root,name):
    need(type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts,'Relative prepared asset')
    p=root
    for part in Path(name).parts:p=p/part;need(not p.is_symlink(),'No symlink prepared asset components')
    return p


def stage(root,sha,person,arm,out,cap,*,owner=None):
    need(person in SUBJECTS and arm in ARMS,'Exact person/arm')
    body=capture(root/'POOL.json',20_000_000,owner=owner);need(hashlib.sha256(body).hexdigest()==sha,'Frozen operator pool')
    pool=decode(body);need(pool['schema']=='neural080_pool_v1' and [r['subject'] for r in pool['subjects']]==list(SUBJECTS),'Full six-person pool')
    r=next(r for r in pool['subjects'] if r['subject']==person)
    n=arrays.load(local(root,r['nuisance']['path']),r['nuisance'],(1102,2630),max_bytes=32_000_000,owner=owner)
    e=arrays.load(local(root,r['ocular']['path']),r['ocular'],(1102,1200),max_bytes=12_000_000,owner=owner)
    d=arrays.load(local(root,pool['dynamic']['path']),pool['dynamic'],(1102,30,192),max_bytes=60_000_000,owner=owner)
    x=design(n,e,d,arm,np.asarray(FIT)-1,np.asarray(QUERY)-1)
    fit=arrays.load(local(root,r['fit_targets']['path']),r['fit_targets'],(900,127,150),max_bytes=160_000_000,owner=owner)
    val=arrays.load(local(root,r['validation_targets']['path']),r['validation_targets'],(100,127,150),max_bytes=20_000_000,owner=owner)
    writer=Writer(out,cap)
    for name,ids in (('fit',FIT),('validation',VALIDATION),('query',QUERY)):writer.array('x_'+name+'.npy',x[np.asarray(ids)-1])
    writer.array('y_fit.npy',fit);writer.array('y_validation.npy',val)
    scope={'schema':'neural080_scope_v1','subject':person,'arm':arm,'query_sha256':pool['query']['sha256'],
           'fit_video_ids':list(FIT),'validation_video_ids':list(VALIDATION),'query_video_ids':list(QUERY),
           'feature_columns':x.shape[1],'target_shape':[127,150],'files':list(writer.files),
           'query_targets_supplied':False,'operator_pool_must_not_be_mounted':True,'actual_replay_verified':False}
    scope_descriptor=writer.json('SCOPE.json',scope);return {'retained_bytes':writer.used,'arm':arm,'subject':person,'scientific_runs':0,'scope_descriptor':scope_descriptor}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('pool','out'):p.add_argument('--'+key,type=Path,required=True)
    for key in ('pool-sha256','subject','arm'):p.add_argument('--'+key,required=True)
    p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
    print(json.dumps(stage(a.pool,a.pool_sha256,a.subject,a.arm,a.out,a.max_output_bytes)))
