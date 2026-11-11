"""Fixed C=1 logistic and prospective HGB; separate FIT and INFER containers.

Serialized estimator state is read ONLY inside the isolated reference process.
It is never unpickled in the host controller or participant evaluator.
"""
from pathlib import Path
import delivery_io as io
import array_io
import protocol as p
VERSION='1.3.2'
HGB_PARAMS=dict(loss='log_loss',learning_rate=0.1,max_iter=100,max_leaf_nodes=31,
 max_depth=None,min_samples_leaf=20,l2_regularization=0.0,max_bins=255,
 categorical_features=None,monotonic_cst=None,interaction_cst=None,
 warm_start=False,early_stopping=False,scoring='loss',validation_fraction=None,
 n_iter_no_change=10,tol=1e-7,verbose=0,random_state=0,class_weight=None)
def environment():
 import sklearn
 io.need(sklearn.__version__==VERSION,'exact prospective sklearn version')
def view(root,phase):
 v=io.json_file(root/'VIEW.json',40_000_000)
 io.need(v['format']=='neural062_phase_view_v1'and v['phase']==phase and v['feature_names']==list(p.names(v['arm']))and v['classes']==list(range(8)),'fixed view contract')
 io.need(v['array_name']==('train.npy'if phase=='fit'else'query.npy'),'disjoint phase array')
 r=v['array'];a=array_io.read(root/v['array_name'],{k:r[k]for k in('bytes','sha256')},r['shape'])
 return v,a
def fit(root,output,kind,mode):
 environment()
 import numpy as np
 import pickle
 from sklearn.impute import SimpleImputer
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 from sklearn.ensemble import HistGradientBoostingClassifier
 io.need(mode in('F','I')and kind in('logistic','hgb'),'reference coordinates')
 root=Path(root);v,tr=view(root,'fit');dim=len(p.names(v['arm']))
 io.need(tr.shape[1]==dim+2,'training extent');x=tr[:,:dim];y=tr[:,-2];w=tr[:,-1]
 io.need(np.isfinite(y).all()and np.all(y==y.astype(int))and set(y.astype(int))==set(range(8))and np.isfinite(w).all()and np.all(w>0),'eight labels/positive fixed weights')
 # Identical original train-only imputation/scaling for both fixed references.
 imp=SimpleImputer(strategy='median',keep_empty_features=True);x=imp.fit_transform(x)
 scale=StandardScaler();x=scale.fit_transform(x,sample_weight=w)
 model=LogisticRegression(C=1,solver='lbfgs',max_iter=2000,tol=1e-6,random_state=0)if kind=='logistic'else HistGradientBoostingClassifier(**HGB_PARAMS)
 model.fit(x,y.astype(int),sample_weight=w)
 io.need(list(model.classes_)==list(range(8)),'all classes')
 if kind=='logistic':io.need(max(model.n_iter_)<2000,'original convergence requirement')
 # Same fixed reference in F/I. Neither validation nor test mice is a fitting/tuning set.
 state={'schema':'neural062.reference-state.v1','generation':v['generation'],'case':v['case'],'arm':v['arm'],'kind':kind,'mode':mode,'sklearn':VERSION,'selection':'none','fit_input':v['array']}
 blob=pickle.dumps((imp,scale,model),protocol=5);io.need(len(blob)<=32_000_000,'sealed estimator extent')
 out=io.fresh(output);io.put_bytes(out/'model.pkl',blob,32_000_000);state['model_pin']=io.pin(blob)
 io.put(out/'state.json',state,200_000)
def infer(root,state_root,output,kind,mode):
 environment()
 import numpy as np
 import pickle
 root=Path(root);v,query=view(root,'infer');state_root=Path(state_root);s=io.json_file(state_root/'state.json',200_000)
 io.need(s['schema']=='neural062.reference-state.v1'and s['kind']==kind and s['mode']==mode and s['sklearn']==VERSION and all(s[k]==v[k]for k in('generation','case','arm')),'same-cell sealed state')
 # Host validates exact whole state tree and read-only mount before this call.
 imp,scale,model=pickle.loads(io.read(state_root/'model.pkl',32_000_000,s['model_pin']))
 dim=len(p.names(v['arm']));io.need(query.shape==(len(v['query_ids']),dim),'complete query')
 x=scale.transform(imp.transform(query))if len(query)else np.empty((0,dim))
 prob=model.predict_proba(x)if len(query)else np.empty((0,8))
 io.need(prob.shape==(len(v['query_ids']),8)and np.isfinite(prob).all(),'full predictions')
 out=io.fresh(output);io.put(out/'prediction.json',{'format':'neural062_predictions_v1','generation':v['generation'],'case':v['case'],'arm':v['arm'],'probabilities':[{'id':k,'p':list(map(float,r))}for k,r in zip(v['query_ids'],prob)]},160_000_000)
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--phase',choices=['fit','infer'],required=True);a.add_argument('--input',required=True);a.add_argument('--state');a.add_argument('--output',required=True);a.add_argument('--kind',choices=['logistic','hgb'],required=True);a.add_argument('--mode',choices=['F','I'],required=True);q=a.parse_args()
 if q.phase=='fit':fit(q.input,q.output,q.kind,q.mode)
 else:infer(q.input,q.state,q.output,q.kind,q.mode)
