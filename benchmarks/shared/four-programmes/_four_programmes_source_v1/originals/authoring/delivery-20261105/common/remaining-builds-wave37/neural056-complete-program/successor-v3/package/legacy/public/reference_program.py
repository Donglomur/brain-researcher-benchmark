"""UNRUN prospective fixed ridge controls, one outer view at a time.
No KernelPCA/feature fitting, target-person access or outcome-dependent tuning.
"""
import argparse
from pathlib import Path
import numpy as np
from common import ARMS,PEOPLE,need,digest,canonical,validate_design
from array_io import capture,metadata,identity,arrays,fresh_output

def fit_predict(x,y,q):
 x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64);q=np.asarray(q,dtype=np.float64);mu=x.mean(0);sd=x.std(0);sd[sd==0]=1;ym=y.mean(0);z=(x-mu)/sd
 coef=np.linalg.solve(z.T@z+np.eye(z.shape[1]),z.T@(y-ym));return (q-mu)/sd@coef+ym

def permutation(concepts):
 unique=sorted(set(concepts));need(len(unique)==1654,'All1654 concepts');groups={c:[i for i,x in enumerate(concepts) if x==c] for c in unique};need(all(len(x)==10 for x in groups.values()),'Whole10-exemplar groups')
 perm=np.empty(len(concepts),dtype=np.int64)
 for i,c in enumerate(unique):
  other=unique[(i+1)%len(unique)]
  for a,b in zip(groups[c],groups[other]):perm[a]=b
 need(np.all(perm!=np.arange(len(perm))),'No identitygroup control');return perm

def run(view,out):
 fresh_output(out);view=Path(view);out=Path(out);c=metadata(view/'case.json',4_000_000);d=validate_design(c['design']);person=c['held_person'];need(person in PEOPLE and c['training_people']==[p for p in PEOPLE if p!=person],'No targetpersoncalibration')
 def load(key,filename,keys,cap):
  b=capture(view/filename,cap);need(identity(b)==c['bindings'][key],'Exactcaseboundfile');return arrays(b,keys,cap)
 y=load('training_response','training_response.npz',('mean',),230_000_000)['mean'];tr=load('train_features','train_features.npz',('representation','low_level'),330_000_000);te=load('test_features','test_features.npz',('representation','low_level'),330_000_000);need(y.shape==(16540,17,100),'Fulltrainingresponses');flat=y.reshape(16540,-1);out.mkdir();rows=[]
 for arm in ARMS:
  key='low_level' if arm=='low_level' else 'representation';yy=flat[permutation(c['training_concept_ids'])] if arm=='response_permuted' else flat
  pred=fit_predict(tr[key],yy,te[key]).reshape(200,17,100);name=person+'__'+arm+'.npz';np.savez_compressed(out/name,prediction=pred);rows.append({'person':person,'arm':arm,'file':name,**identity((out/name).read_bytes())})
 (out/'case_predictions.json').write_bytes(canonical({'schema':'neural056_case_predictions_v1','design_sha256':digest(d),'query_image_ids':d['query_image_ids'],'entries':rows}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--view',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.view,a.output)
