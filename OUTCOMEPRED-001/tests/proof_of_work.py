"""Only genuine source-recomputed, primitive complete banks are accepted."""
import json
from pathlib import Path
import numpy as np
import prediction_contract as q

METHOD_SHA256='77f75622ff40896214f6545faffb914ded3fcfe7285c65e994d71939a96a59eb'
SOURCE_MANIFEST_SHA256='d87c000f92d2aa54b4eaa0de50d5ffd7ab3035141d1fccd45b4e674d1c56d63d'
SOURCE_SHA256='f46fa114f07a00080cdc1860913df245326a17bf249d3749ee659cabd157784a'
BUILDER_ID='original-nwb-bisect-trust-exact-v2'
ARRAYS=q.COUNT_FIELDS+['labels','folds','scores','model_analysis','model_fold','scaler_mean','scaler_scale','coef','intercept','gradient_inf']

def load_reference(path=Path(__file__).with_name('reference.npz')):
    with np.load(path,allow_pickle=False) as z:
        q.require(set(z.files)==set(ARRAYS)|{'reference_json'},'Legacy/incomplete bank: genuine original-source regeneration required')
        text=z['reference_json']; q.require(text.shape==() and text.dtype.kind=='U','Primitive reference metadata required')
        ref=json.loads(str(text),parse_constant=lambda x: (_ for _ in ()).throw(AssertionError('Nonfinite bank JSON')))
        ref.update({k:np.array(z[k]) for k in ARRAYS})
    q.match(ref['provenance'],dict(builder_id=BUILDER_ID,source_manifest_sha256=SOURCE_MANIFEST_SHA256,method_contract_sha256=METHOD_SHA256,source_sha256=SOURCE_SHA256,status='complete'),'bank provenance')
    n,u=len(ref['labels']),len(ref['unit_id'])
    q.require(len(ref['source_rows'])==548 and u==867 and n>=10,'Wrong original-source support')
    q.require(ref['analysis'].tolist()==list(q.NAMES),'Wrong analysis axis')
    for k in ('source_trial_row','trial_id','source_unit_row','unit_id','labels','folds','model_analysis','model_fold'): q.int_array(ref[k],k)
    q.require(np.array_equal(ref['source_unit_row'],np.arange(u)) and len(set(ref['unit_id'].tolist()))==u,'Wrong original unit axis')
    q.require(ref['spike_count'].shape==(21,n,u) and np.all(q.int_array(ref['spike_count'],'counts')>=0),'Incomplete original count tensor')
    q.require(ref['folds'].shape==ref['labels'].shape==ref['trial_id'].shape==ref['source_trial_row'].shape==(n,),'Wrong trial axes')
    q.require(set(ref['labels'].tolist())=={0,1} and np.sum(ref['labels']==0)*2==n and set(ref['folds'].tolist())==set(range(5)),'Invalid balanced cohort/folds')
    selected=[r for r in ref['source_rows'] if r['selected']]
    for key,field in [('source_trial_row','source_trial_row'),('trial_id','trial_id'),('labels','rewarded'),('folds','fold')]:
        q.require(np.array_equal(ref[key],np.array([r[field] for r in selected])),'Source selection does not bind bank axis')
    for key,idx in [('window_start_s',1),('window_end_s',2)]:
        q.require(np.array_equal(ref[key],np.array([w[idx]/1000 for w in q.WINDOWS])),'Wrong fixed windows')
    q.require(ref['scores'].shape==(21,n) and np.isfinite(ref['scores']).all(),'Incomplete OOF source scores')
    for k in ('scaler_mean','scaler_scale','coef'): q.require(ref[k].shape==(105,u) and np.isfinite(ref[k]).all(),'Invalid model/scaler state')
    for k in ('intercept','gradient_inf','model_analysis','model_fold'): q.require(ref[k].shape==(105,) and np.isfinite(ref[k]).all(),'Invalid model identity/state')
    q.require(np.all(ref['scaler_scale']>0) and np.all((ref['gradient_inf']>=0)&(ref['gradient_inf']<=1e-9)),'Invalid public model completion')
    seen=set()
    for row,(ai,fold) in enumerate(zip(ref['model_analysis'],ref['model_fold'])):
        key=int(ai),int(fold); q.require(key not in seen and 0<=ai<21 and 0<=fold<5,'Wrong model key'); seen.add(key)
        test=ref['folds']==fold
        score=((ref['spike_count'][ai,test]-ref['scaler_mean'][row])/ref['scaler_scale'][row])@ref['coef'][row]+ref['intercept'][row]
        q.require(np.allclose(score,ref['scores'][ai,test],atol=1e-10,rtol=1e-10),'Source/model/score arithmetic differs')
    q.require(len(seen)==105,'Incomplete model support')
    q.validate_metadata(ref['metadata'],ref)
    return ref
