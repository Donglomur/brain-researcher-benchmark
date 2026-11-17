"""Prospective fixed-split source-formula references, not original random two-fold CV.

The rank-100 centered stimulus basis and its Gram matrix preserve projected-neuron
Euclidean retrieval. Algebraic equivalence remains a numerical qualification gate.
"""
from .core import need
def row_zscore(x):
 import numpy as np
 z=x-x.mean(axis=-1,keepdims=True)
 return z/(.001+np.sqrt((z*z).mean(axis=-1,keepdims=True)))
def target_coefficients(latent,basis):
 import numpy as np
 need(basis.shape==(10000,100) and latent.shape[1]==100,"complete source stimulus geometry")
 centered=basis-basis.mean(0);gram=centered.T@centered
 scale=.001+np.sqrt(np.einsum('ij,jk,ik->i',latent,gram,latent)/10000)
 return latent/scale[:,None],gram
def fit_ridge(x,y,penalty):
 import numpy as np
 need(x.shape==(1000,10000) and y.shape==(1000,100),"complete fixed training support")
 need(penalty in (.01,.1,1,10,100,1000),"fixed ridge family")
 z=row_zscore(x)
 # Source primal (X'X/n + lambda I)^-1 X'Y/n, via its exact dual.
 # y represents source per-row-zscored projected inputs. Do not column-center.
 weights=z.T@np.linalg.solve(z@z.T/len(z)+penalty*np.eye(len(z)),y)/len(z)
 return {"weights":weights,"penalty":penalty}
def predict(model,x):return row_zscore(x)@model["weights"]
def retrieval(predictions,prototypes,truth,gram):
 import numpy as np
 need(predictions.shape==prototypes.shape==(1000,100) and gram.shape==(100,100),"full coefficient geometry")
 need(len(truth)==1000 and sorted(truth)==list(range(1000)),"complete protected query permutation")
 yy=np.einsum('ij,jk,ik->i',prototypes,gram,prototypes);correct=[]
 for start in range(0,1000,64):
  x=predictions[start:start+64]
  d=np.einsum('ij,jk,ik->i',x,gram,x)[:,None]+yy[None,:]-2*x@gram@prototypes.T
  need(np.isfinite(d).all(),"finite projected-neuron distances")
  correct.extend((d.argmin(1)==np.asarray(truth[start:start+64])).tolist())
 return correct
def select_penalty(development,grid):
 import numpy as np
 need(len(development)==10 and tuple(grid)==(.01,.1,1,10,100,1000),"fixed development programme")
 scores=[]
 for penalty in grid:
  per_network=[]
  for d in development:
   need(len(d['train_x'])==len(d['query_x'])==len(d['truth'])==len(d['delays_seconds']),'complete endpoint-specific mixed training/query support')
   curves=[]
   for tx,qx,truth in zip(d['train_x'],d['query_x'],d['truth']):
    model=fit_ridge(tx,d['train_y'],penalty)
    curves.append(sum(retrieval(predict(model,qx),d['prototypes'],truth,d['gram']))/1000)
   from .scoring import normalized_auc
   per_network.append(normalized_auc(curves,d['delays_seconds']))
  scores.append(float(np.mean(per_network)))
 return grid[max(range(len(grid)),key=lambda i:scores[i])]
def evaluate_reference(training,queries,reference_id,selected_penalty=None):
 need(reference_id in ("source_formula_ridge10","development_selected_ridge"),"fixed reference")
 penalty=10 if reference_id=="source_formula_ridge10" else selected_penalty
 need(penalty in (.01,.1,1,10,100,1000),"development-selected fixed penalty")
 need(len(training['x'])==len(queries),'all endpoint-specific training sets')
 return [predict(fit_ridge(tx,training['y'],penalty),qx) for tx,qx in zip(training['x'],queries)]
