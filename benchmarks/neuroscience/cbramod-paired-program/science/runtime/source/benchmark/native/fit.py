"""Actual official model/criterion/optimizer with target-free derived fit loop.

Preserves batch-stepped cosine, multi-LR, zero-initialized strict monitor and
checkpoint semantics. The original trainer remains untouched in official/.
Canonical validation flattens ISRUC per epoch and retains singleton batches;
this is an explicit benchmark adaptation, not exact official-evaluator replay.
"""
import copy,math,time
from .policy import DATASETS,need

def validation(components,trainer,task):
 torch=components['torch'];trainer.model.eval();truths=[];preds=[]
 # Native scientific imports occur only inside this future-native route.
 import numpy as np
 from sklearn.metrics import cohen_kappa_score,roc_auc_score,r2_score
 with torch.no_grad():
  for x,y in trainer.data_loader['val']:
   out=trainer.model(x.cuda())
   if task=='multiclass':out=out.argmax(dim=-1)
   elif task=='binary':out=torch.sigmoid(out)
   truths.extend(y.detach().cpu().reshape(-1).tolist())
   preds.extend(out.detach().cpu().reshape(-1).tolist())
 need(len(truths)==len(preds) and len(truths)>0,'complete validation predictions')
 if task=='multiclass':v=cohen_kappa_score(truths,preds)
 elif task=='binary':v=roc_auc_score(truths,preds)
 else:v=r2_score(truths,preds)
 need(math.isfinite(float(v)),'undefined validation monitor is a failed run, no support deletion')
 return float(v)

def fit(components,trainer,plan,deadline):
 torch=components['torch'];task=DATASETS[plan['dataset_id']][1];best=0.;state=None;selected=None;trace=[]
 for epoch in range(plan['params']['epochs']):
  need(time.monotonic()<deadline,'whole execution deadline');trainer.model.train();steps=0
  for x,y in trainer.data_loader['train']:
   need(time.monotonic()<deadline,'whole execution deadline')
   trainer.optimizer.zero_grad();pred=trainer.model(x.cuda());y=y.cuda()
   loss=trainer.criterion(pred.transpose(1,2)if plan['dataset_id']=='ISRUC'else pred,y)
   need(bool(torch.isfinite(loss).all()),'nonfinite training loss fails whole run')
   loss.backward()
   if plan['params']['clip_value']>0:torch.nn.utils.clip_grad_norm_(trainer.model.parameters(),plan['params']['clip_value'])
   trainer.optimizer.step();trainer.optimizer_scheduler.step();steps+=1
  need(steps==trainer.data_length and steps>0,'complete epoch training support')
  monitor=validation(components,trainer,task);need(time.monotonic()<deadline,'whole execution deadline')
  trace.append({'epoch':epoch+1,'steps':steps,'monitor':monitor})
  if monitor>best:
   best=monitor;selected=epoch+1;state=copy.deepcopy(trainer.model.state_dict())
 need(state is not None,'official strict-positive monitor selected no checkpoint; no invented fallback')
 trainer.model.load_state_dict(state);trainer.model.eval()
 return {'selected_epoch':selected,'monitor':best,'epochs':trace,
  'selection':'strict greater than0; first strict maximizer',
  'test_targets_accessed_by_fit':False,'exact_official_evaluator_parity':False}
