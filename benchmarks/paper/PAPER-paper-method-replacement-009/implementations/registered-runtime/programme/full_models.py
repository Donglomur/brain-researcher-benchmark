"""Fixed complete decoder families and training-only selection.
Paper reconstruction is named separately from unmodified released modules.
"""
from .full_plan import need
from .domain import Refusal,MissingDefinition

def network(method,views,config):
 import torch
 from torch import nn
 n=[v['train_x'].shape[2]for v in views];t=views[0]['train_x'].shape[1];p=config['outputs'];r=config['rank'];latent=config['read_in']
 class Model(nn.Module):
  def __init__(self):
   super().__init__();self.method=method
   self.bias=nn.ParameterList([nn.Parameter(torch.randn(p,dtype=torch.double))for _ in n])
   if method in('single_rrr','multi_rrr','multi_region_rrr'):
    self.U=nn.ParameterList([nn.Parameter(torch.randn(k,r,dtype=torch.double))for k in n])
    if method=='multi_region_rrr':
     self.regions=list(dict.fromkeys(v['region']for v in views));self.A=nn.Parameter(torch.randn(len(self.regions),r,config['global_rank'],dtype=torch.double));self.B=nn.Parameter(torch.randn(config['global_rank'],t,p,dtype=torch.double))
    else:self.V=nn.Parameter(torch.randn(r,t,p,dtype=torch.double))
   elif method in('multi_linear','multi_mlp'):
    self.read_in=nn.ModuleList([nn.Linear(k,latent)for k in n]);dim=latent*t
    self.backbone=nn.Linear(dim,p)if method=='multi_linear'else nn.Sequential(nn.Linear(dim,config['hidden']),nn.ReLU(),nn.Dropout(config['dropout']),nn.Linear(config['hidden'],p))
   elif method=='mlp':
    need(len(n)==1,'single MLP');hidden=config['hidden_sizes'];need(hidden,'source MLP hidden architecture')
    self.input_layer=nn.Linear(n[0],hidden[0]);self.lower=nn.ModuleList();self.upper=nn.ModuleList()
    for a,z in zip(hidden,hidden[1:]):
     self.lower.extend([nn.Linear(a,z),nn.ReLU(),nn.Dropout(config['dropout'])]);self.upper.extend([nn.Linear(a,z),nn.ReLU(),nn.Dropout(config['dropout'])])
    self.flat_layer=nn.Linear(hidden[-1]*t,hidden[0]);self.output_layer=nn.Linear(hidden[-1],p)
   else:raise Refusal('fixed neural family')
   self.double()
  def forward(self,x,i):
   if self.method in('single_rrr','multi_rrr','multi_region_rrr'):
    v=torch.einsum('rl,ltp->rtp',self.A[self.regions.index(views[i]['region'])],self.B)if self.method=='multi_region_rrr'else self.V
    # No squeeze: explicit R,T,P axes, including R=1 and P=1.
    return torch.einsum('nr,rtp,ktn->kp',self.U[i],v,x)+self.bias[i]
   if self.method in('multi_linear','multi_mlp'):return self.backbone(self.read_in[i](x).flatten(start_dim=1))+self.bias[i]
   x=self.input_layer(x)
   for layer in self.lower:x=layer(x)
   x=torch.relu(self.flat_layer(x.flatten(start_dim=1)))
   for layer in self.upper:x=layer(x)
   return self.output_layer(x)
 return Model()

def loss(target,p,y):
 import torch
 if target in('choice','lick','gabors','static-gratings'):return torch.nn.functional.cross_entropy(p,y.reshape(-1).long())
 return torch.nn.functional.mse_loss(p,y)

def fit_neural(method,views,target,configuration):
 import torch,numpy as np
 need(configuration['recipe']in('paper_method_reconstruction','prospective40'),'named corrected trainer')
 configs=configuration['candidates'];need(configs and configuration['selection']=='equal_session_validation_loss','fixed training-only selector')
 if configuration['recipe']=='paper_method_reconstruction':
  need(all(c['epochs']==2000 and c['batch_size']==16 for c in configs),'paper 2000 epochs/batch16')
  if method in('multi_rrr','multi_region_rrr'):need(all(c['learning_rate']==.01 and c['weight_decay']==1 for c in configs),'paper shared-model fixed optimizer')
  if method in('single_rrr','mlp'):need(configuration['table_s2_source']is not None and len(configs)==30,'original30 TableS2 configurations required')
 best=None;history=[]
 for ordinal,cfg in enumerate(configs):
  torch.manual_seed(cfg['seed']);model=network(method,views,cfg);optimizer=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
  scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=cfg['cosine_period'])
  fit=[(torch.as_tensor(v['train_x'],dtype=torch.double),torch.as_tensor(v['train_y'],dtype=torch.double))for v in views]
  valid=[(torch.as_tensor(v['validation_x'],dtype=torch.double),torch.as_tensor(v['validation_y'],dtype=torch.double))for v in views]
  selected=None
  for epoch in range(cfg['epochs']):
   model.train()
   # Released max_size_cycle structure: a fresh shuffled session iterator is
   # restarted when exhausted; every optimizer step consumes one batch/session.
   batches=[list(torch.randperm(len(x)).split(cfg['batch_size']))for x,y in fit]
   for step in range(max(len(v)for v in batches)):
    optimizer.zero_grad();objective=0.
    for i,(x,y)in enumerate(fit):
     if step and step%len(batches[i])==0:batches[i]=list(torch.randperm(len(x)).split(cfg['batch_size']))
     idx=batches[i][step%len(batches[i])];objective=objective+loss(target,model(x[idx],i),y[idx])/len(fit)
    objective.backward();optimizer.step()
   scheduler.step();model.eval()
   with torch.no_grad():
    vals=[]
    for i,(x,y)in enumerate(valid):
     count=len(x)if configuration['recipe']=='prospective40'else(len(x)//cfg['batch_size'])*cfg['batch_size']
     need(count>0,'historical validation drop-last has nonempty support')
     vals.append(loss(target,model(x[:count],i),y[:count]))
    score=float(sum(vals)/len(vals))
   need(np.isfinite(score),'finite validation loss')
   if selected is None or score<selected[0]:selected=(score,epoch,{k:v.detach().clone()for k,v in model.state_dict().items()})
  history.append({'candidate':ordinal,'validation_loss':selected[0],'epoch':selected[1],'configuration':cfg})
  if best is None or selected[0]<best[0]:best=(selected[0],ordinal,model,selected[2])
 best[2].load_state_dict(best[3]);return best[2],{'selected':best[1],'candidates':history,'selection_domain':'training/validation only','query_tuning':False}

def fit_linear_full(view,target,configuration):
 import numpy as np
 from sklearn.linear_model import LogisticRegression,Ridge
 from sklearn.metrics import log_loss,mean_squared_error
 x=view['train_x'].reshape(len(view['train_x']),-1);v=view['validation_x'].reshape(len(view['validation_x']),-1)
 y=view['train_y'];vy=view['validation_y'];clf=target in('choice','lick','gabors','static-gratings');best=None;rows=[]
 for ordinal,penalty in enumerate(configuration['penalties']):
  model=LogisticRegression(C=penalty,penalty='l2',max_iter=configuration['max_iter'],random_state=configuration['seed'])if clf else Ridge(alpha=penalty)
  model.fit(x,y.reshape(-1)if clf else y);pred=model.predict_proba(v)if clf else model.predict(v)
  value=log_loss(vy.reshape(-1),pred,labels=model.classes_)if clf else mean_squared_error(vy,pred)
  need(np.isfinite(value),'finite linear validation loss');rows.append({'candidate':ordinal,'penalty':penalty,'validation_loss':float(value)})
  if best is None or value<best[0]:best=(value,ordinal,model)
 return best[2],{'selected':best[1],'candidates':rows,'selection_domain':'training/validation only','query_tuning':False}

def predict(model,method,x,index,target):
 import numpy as np
 if method=='linear':
  p=model.predict_proba(x.reshape(len(x),-1))if target in('choice','lick','gabors','static-gratings')else model.predict(x.reshape(len(x),-1))
 else:
  import torch
  model.eval()
  with torch.no_grad():p=model(torch.as_tensor(x,dtype=torch.double),index)
  if target in('choice','lick','gabors','static-gratings'):p=torch.softmax(p,dim=1)
  p=p.detach().cpu().numpy()
 if target in('choice','lick'):p=p[:,1:2]
 return np.asarray(p).reshape(len(x),-1)
