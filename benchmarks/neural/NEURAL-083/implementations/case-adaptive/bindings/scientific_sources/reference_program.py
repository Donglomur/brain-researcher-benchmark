"""Unexecuted independent CSP/shrinkageLDA plus training-only Platt reference."""
import argparse,sys
from pathlib import Path
import delivery_io as io
import protocol as p
import array_io

def fit_readout(x,y,arm):
 import numpy as np
 from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
 from scipy.linalg import eigh
 p.need(set(y)=={0,1} and all((y==k).sum()>=2 for k in (0,1)),'Bothclasses with >=2trainingtrials')
 if arm!='CONTEXT':
  cov=[]
  for cls in (0,1):
   flat=x[y==cls].reshape(-1,20);cov.append(np.cov(flat,rowvar=False,ddof=1))
  total=cov[0]+cov[1];ridge=1e-6*np.trace(total)/20;p.need(np.isfinite(ridge) and ridge>0,'Positivefinite CSP scale')
  values,vectors=eigh(cov[1],total+ridge*np.eye(20));w=vectors[:,[0,1,-2,-1]]
  def feature(a):
   z=np.einsum('ntc,ck->ntk',a,w);v=np.var(z,axis=1,ddof=1);p.need(np.isfinite(v).all() and (v>0).all(),'Positivefinite projectedvariances');return np.log(v)
 else:
  mean=x.mean(0);sd=x.std(0);sd[sd==0]=1
  def feature(a):return (a-mean)/sd
 z=feature(x);model=LinearDiscriminantAnalysis(solver='lsqr',shrinkage='auto',priors=[.5,.5]);model.fit(z,y)
 def decision(a):return model.decision_function(feature(a))
 return decision

def predict(v,x,q,readout_factory=fit_readout,calibrator_factory=None):
 import numpy as np
 p.need(v['arm'] in p.ARMS and v['setting'] in p.SETTINGS,'Declaredcondition')
 train=v['training'];p.need(len(train)==len(x) and len(q)==len(v['query'])==100,'Fullcasealignment')
 p.need(x.shape[1:]==q.shape[1:]==((5,) if v['arm']=='CONTEXT' else (251,20)),'Exactarmgeometry')
 calibration=np.asarray([r['role']=='calibration' for r in train]);use=calibration if calibration.any() else np.ones(len(train),bool)
 xx=x[use];y=np.asarray([r['y'] for r,take in zip(train,use) if take]);groups=[r['person'] for r,take in zip(train,use) if take]
 p.need(all(type(r['y'])is int and r['y'] in (0,1) for r in train),'Trainingbinarylabels')
 # Frozenreference uses allowedtargetcalibration alone whenpresent; otherwise all donors.
 prior=(float(y.sum())+.5)/(len(y)+1)
 if len(set(y))<2:return np.full(100,prior)
 folds=np.asarray([r['inner_fold'] for r,take in zip(train,use) if take]);p.need(np.all((folds>=0)&(folds<5)),'Predeclaredtraining-onlyfolds')
 scores=np.empty(len(y));failed=False
 for fold in range(5):
  test=folds==fold;fit=~test
  if not test.any() or any((y[fit]==cls).sum()<2 for cls in (0,1)):failed=True;break
  model=readout_factory(xx[fit],y[fit],v['arm']);scores[test]=model(xx[test])
 if failed:return np.full(100,prior)
 p.need(np.isfinite(scores).all(),'FiniteOOF scores')
 if calibrator_factory is None:
  from sklearn.linear_model import LogisticRegression
  calibration_model=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,random_state=83083)
 else:calibration_model=calibrator_factory()
 calibration_model.fit(scores[:,None],y)
 if hasattr(calibration_model,'n_iter_'):p.need(np.max(calibration_model.n_iter_)<1000,'Plattcalibrationdidnotreachiterationcap')
 model=readout_factory(xx,y,v['arm']);decisions=model(q)
 probability=calibration_model.predict_proba(np.asarray(decisions)[:,None])[:,list(calibration_model.classes_).index(1)]
 p.need(probability.shape==(100,) and np.isfinite(probability).all() and ((probability>=0)&(probability<=1)).all(),'Finitecompleteprobability')
 return probability

def main():
 a=argparse.ArgumentParser();a.add_argument('--input',type=Path,required=True);a.add_argument('--output',type=Path,required=True);q=a.parse_args();out=io.regular(q.output);p.need(not out.exists(),'Freshoutputbeforefit')
 v=io.json_file(q.input/'case.json',2000000);x=array_io.read(q.input/'training.npy',v['training_pin'],v['training_shape']);query=array_io.read(q.input/'query.npy',v['query_pin'],v['query_shape'])
 base={'schema':'neural083_case_prediction_v1','generation':v['generation'],'case':v['case'],'setting':v['setting'],'arm':v['arm']}
 try:
  prob=predict(v,x,query);result={**base,'status':'complete','predictions':[{'trial':t,'p_right':float(z)} for t,z in zip(v['query'],prob)]}
 except (ValueError,RuntimeError,FloatingPointError,ArithmeticError) as e:result={**base,'status':'abstain','reason':type(e).__name__+':'+str(e)[:200]}
 io.put(out,result,100000)
if __name__=='__main__':main()
