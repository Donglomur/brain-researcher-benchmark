"""Causal prospective restricted-wait reference fits; native uses author source."""
def divisive_features(offers,horizon,alpha):
 import numpy as np
 r=np.asarray(offers,float)
 if horizon<1 or alpha<=0:raise ValueError('predeclared positive history parameters')
 # Prospective previous-only history. Original j-N:j current-inclusive source
 # remains the native lane and is never silently replaced by this endpoint.
 return np.array([r[t]/(1+alpha*sum(r[max(0,t-horizon):t]))for t in range(len(r))])

def inference_features(ordinal_offers,transition,emission,initial):
 import numpy as np
 T=np.asarray(transition,float);E=np.asarray(emission,float);p=np.asarray(initial,float);out=[]
 if T.shape!=(3,3)or E.shape!=(3,5):raise ValueError('three-block five-offer model')
 for offer in ordinal_offers:
  p=T.T@p;p=p*E[:,offer-1]
  if p.sum()<=0:raise ValueError('zero posterior support')
  p=p/p.sum();out.append(p.copy())
 return np.asarray(out)

def restricted_wait_fit(features,observed_catch_wait,mask,regularization):
 import numpy as np
 from scipy.optimize import minimize
 X=np.asarray(features,float);y=np.asarray(observed_catch_wait,float);mask=np.asarray(mask,bool)
 if len(X)!=len(y)or len(mask)!=len(y)or not np.any(mask):raise ValueError('complete train catch support')
 if np.any((y[mask]<0)|(y[mask]>100)):raise ValueError('restricted waiting domain')
 X=np.column_stack((np.ones(len(X)),X));Xm=X[mask];ym=y[mask]
 def prediction(w):return 100/(1+np.exp(-np.clip(Xm@w,-700,700)))
 def objective(w):return np.mean((prediction(w)-ym)**2)+regularization*np.dot(w[1:],w[1:])
 fit=minimize(objective,np.zeros(X.shape[1]),method='BFGS')
 if not fit.success:raise ValueError('reference optimization failed: '+fit.message)
 return {'weights':fit.x,'training_objective':float(fit.fun),'regularization':regularization,'native_equivalence':False,'target':'observed_restricted100s'}

def restricted_wait_predict(model,features):
 import numpy as np
 X=np.column_stack((np.ones(len(features)),np.asarray(features,float)))
 return 100/(1+np.exp(-np.clip(X@model['weights'],-700,700)))
