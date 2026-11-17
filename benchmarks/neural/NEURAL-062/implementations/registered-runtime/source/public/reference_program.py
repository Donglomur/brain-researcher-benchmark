"""Prospective train-only fixed image classifier; no actual fitting executed."""
from pathlib import Path
import json
import protocol as p
import delivery_io as io
import array_io

def run(root):
 import numpy as np
 from sklearn.impute import SimpleImputer
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 root=Path(root);v=io.json_file(root/'VIEW.json',40000000);dim=len(p.names(v['arm']));io.need(v['format']=='neural062_view_v1' and v['feature_names']==list(p.names(v['arm'])) and v['classes']==list(range(8)),'View contract')
 matrices={}
 for name in('train.npy','query.npy'):
  r=v['arrays'][name];matrices[name]=array_io.read(root/name,{k:r[k] for k in('bytes','sha256')},r['shape'])
 tr=matrices['train.npy'];qu=matrices['query.npy'];io.need(tr.shape[1]==dim+2 and qu.shape==(len(v['query_ids']),dim),'Matrix roles');y=tr[:,-2];weights=tr[:,-1];io.need(np.isfinite(y).all() and np.all(y==y.astype(int)) and set(y.astype(int))==set(range(8)) and np.isfinite(weights).all() and np.all(weights>0),'Training labels/weights')
 imp=SimpleImputer(strategy='median',keep_empty_features=True);x=imp.fit_transform(tr[:,:dim]);z=imp.transform(qu) if len(qu) else np.empty((0,dim));scale=StandardScaler();x=scale.fit_transform(x,sample_weight=weights);z=scale.transform(z) if len(z) else z
 model=LogisticRegression(C=1,solver='lbfgs',max_iter=2000,tol=1e-6,random_state=0);model.fit(x,y.astype(int),sample_weight=weights);io.need(max(model.n_iter_)<2000 and list(model.classes_)==list(range(8)),'Convergence/classes')
 prob=model.predict_proba(z) if len(z) else np.empty((0,8))
 return {'format':'neural062_predictions_v1','generation':v['generation'],'case':v['case'],'arm':v['arm'],'probabilities':[{'id':rid,'p':list(map(float,row))} for rid,row in zip(v['query_ids'],prob)]}
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--input',required=True);a.add_argument('--output',required=True);q=a.parse_args();io.put(q.output,run(q.input),160000000)
