"""Complete F/S dispatcher using newly captured arrays and source-selected recipes.
No archived answer table is a scientific producer. All kernels run after capture.
"""
from pathlib import Path
from .native.io import load,dump,need
from .domain import MissingDefinition
from .full_worker import array_read,array_write

def run_panel(request,inputs,output):
 import numpy as np
 from sklearn.decomposition import PCA
 from sklearn.cluster import KMeans,SpectralClustering
 from sklearn.metrics import adjusted_rand_score
 from scipy.signal import savgol_filter
 panel=request['panel'];recipe=load(inputs/'recipe.json');need(recipe['original_source']is not None,'original panel definition source')
 op=panel['operator']
 if op in('pca_refit','imposter_null'):need(recipe['case_ids']==panel['cases'],'refit recipe retains full intended panel case order')
 a={k:array_read(inputs,v)for k,v in recipe['arrays'].items()};tables={};arrays={};traces=[]
 if op=='schematic':tables['graph']=recipe['original_graph']
 elif op=='psth':
  x=a['x'];labels=a['labels'].reshape(-1)
  for label in np.unique(labels):arrays['condition_'+str(label)]=x[labels==label].mean(axis=0)
 elif op=='projection_ari':
  x=a['x'];y=a['labels'].reshape(-1);u=a['U'];pca=PCA(n_components=recipe['rank']).fit(x.reshape(-1,x.shape[-1]))
  projected=np.einsum('ktn,nr->ktr',x,u);pc=pca.transform(x.reshape(-1,x.shape[-1])).reshape(len(x),x.shape[1],-1)
  arrays.update(rrr=projected,pca=pc);tables['ari']={name:float(adjusted_rand_score(y,KMeans(n_clusters=2,n_init=recipe['n_init'],random_state=recipe['seed']).fit_predict(v.reshape(len(x),-1))))for name,v in [('rrr',projected),('pca',pc)]}
 elif op=='conditional_residual':
  x=a['x'];condition=a['condition'];keys=[tuple(row)for row in condition];means={k:x[[i for i,v in enumerate(keys)if v==k]].mean(axis=0)for k in set(keys)}
  fitted=np.asarray([means[k]for k in keys]);residual=x-fitted;arrays.update(conditional=fitted,residual=residual)
  arrays['spectral_order']=np.argsort(SpectralClustering(n_clusters=recipe['clusters'],random_state=recipe['seed'],affinity='nearest_neighbors').fit_predict(residual.reshape(len(x),-1)))
  need(len(recipe['illustrative_trial_ids'])==96,'original96 trial selection');tables['illustrative_ids']=recipe['illustrative_trial_ids']
 elif op in('trace','state_trace'):arrays.update(a)
 elif op=='fourier':
  arrays['frequency']=np.fft.rfftfreq(a['x'].shape[1],recipe['bin_seconds']);arrays['power']=np.mean(abs(np.fft.rfft(a['x'],axis=1))**2,axis=(0,2))
 elif op=='savgol':
  need(a['decoder'].shape[0]>=17,'literal17-trial filter support');arrays['smoothed']=savgol_filter(a['decoder'],17,3,axis=0)
 elif op=='oracle_error':tables['parameter_rmse']={k:float(np.sqrt(np.mean((a[k]-a['oracle_'+k])**2)))for k in recipe['parameters']}
 elif op=='regional_timing':
  need(recipe['orientation_source']is not None and recipe['width_rule']in('all_above_threshold_span','peak_connected_component'),'selected sign/gauge/width convention')
  for i,region in enumerate(recipe['regions']):
   basis=a['basis'][i]*recipe['sign'][i];time=a['time'];peak=int(np.argmax(basis));threshold=.9*basis[peak];inside=np.flatnonzero(basis>=threshold)
   if recipe['width_rule']=='peak_connected_component':
    lo=hi=peak
    while lo>0 and basis[lo-1]>=threshold:lo-=1
    while hi+1<len(basis)and basis[hi+1]>=threshold:hi+=1
   else:lo,hi=inside[0],inside[-1]
   traces.append({'region':region,'peak_seconds':float(time[peak]),'width_seconds':float(time[hi]-time[lo]),'threshold_fraction':.9})
  tables['timing']=traces
 elif op in('pruning','pca_refit','neuron_rank','imposter_null'):
  tables['refits']=refit_panel(op,a,recipe)
 elif op in('decoding','regional_decoding','external_decoding','lick_decoding','rank_curve','session_scaling'):
  # These are derived only from newly captured independent fits/scores, whose
  # exact source job identities are required by the original panel membership.
  scores=load(inputs/'SCORES.private.json');selected=set(recipe['job_ids']);rows=[r for r in scores['rows']if r['job']in selected]
  need({r['job']for r in rows}==selected,'complete panel job support');tables['scores']=rows
  if op=='session_scaling':need(recipe['training_sizes']==[5,10,20,40,73]and len(recipe['fixed_test_sessions'])==5,'full original scaling support')
 elif op=='historical_bootstrap':
  need(recipe['replicates']==10000 and len(a['difference'])==10,'literal historical10-session/10000-resample diagnostic')
  rng=np.random.default_rng(recipe['seed']);d=a['difference'];observed=d.mean(axis=0);means=np.asarray([d[rng.integers(0,10,10)].mean(axis=0)for _ in range(10000)])
  arrays['bootstrap_difference']=means;tables['literal_uncentered_tail_fraction']=(np.abs(means)>np.abs(observed)).mean(axis=0).tolist();tables['prospective_confirmatory_test']=False
 elif op=='state_graph':tables['graphs']=recipe['graphs'];need(set(recipe['graphs'])=={'single','empirical','oracle'},'all state variants')
 elif op=='oracle':
  from .full_state import empirical_lg,lg_fit,oracle_bmm,source_module
  # Post-barrier diagnostic only: query truth never feeds primary predictions.
  sequences=[{'session':'postcapture_oracle','truth':a['truth'],'decoder':a['decoder']}];cfg=dict(recipe['configuration'],target_session='different_from_oracle')
  if recipe['state_family']=='lg':prior=empirical_lg(sequences,cfg);arrays['oracle'],_=lg_fit(a['decoder'],cfg,prior)
  else:module=source_module(recipe['module']['path'],recipe['module']);arrays['oracle'],prior=oracle_bmm(module,a['truth'],a['decoder'],cfg)
  for k,v in prior.items():
   if k not in('training_sessions','sequence_lengths','recipe'):arrays['parameter_'+k]=np.asarray(v)
 else:raise MissingDefinition('unknown full panel operator')
 leaves={k:array_write(output,'arrays/'+k+'.npy',v)for k,v in arrays.items()}
 dump(output/'PANEL.json',{'panel':panel['id'],'group':panel['group'],'operator':op,'source':recipe['original_source'],'tables':tables,'arrays':leaves,'scientifically_qualified':False})
 render(output,panel,arrays,tables);return {'panel':panel['id'],'products':['PANEL.json','panel.pdf','panel.png']}

def refit_panel(op,a,recipe):
 if op=='pca_refit':
  from .full_refits import single_behavior_pc
  return single_behavior_pc(a,recipe)
 if op=='imposter_null':
  from .full_refits import matched_imposter_null
  return matched_imposter_null(a,recipe)
 import numpy as np
 from sklearn.decomposition import PCA
 from .full_models import fit_linear_full,predict,fit_neural
 from .full_score import metric
 x=a['x'];y=a['truth'];part=recipe['partition'];target=recipe['target'];rng=np.random.default_rng(recipe['seed']);variants=[]
 if op=='pruning':
  importance=np.abs(a['U'][:,0]);n=x.shape[2]
  for strategy,order in [('least',np.argsort(importance)),('most',np.argsort(-importance)),('random',rng.permutation(n))]:
   for percent in range(0,100,5):variants.append((strategy+':'+str(percent),x[:,:,order[int(n*percent/100):]],y,'linear',recipe['configuration']))
 elif op=='neuron_rank':
  for row in recipe['grid']:variants.append((row['id'],x[:,:,row['unit_indices']],y,'single_rrr',row['configuration']))
 rows=[]
 for name,xx,yy,method,cfg in variants:
  view={'region':recipe['region']}
  for role in('train','validation','test'):
   idx=[i for i,p in enumerate(part)if p==role];view[role+'_x']=xx[idx]
   if role!='test':view[role+'_y']=yy[idx]
  model,selection=fit_linear_full(view,target,cfg)if method=='linear'else fit_neural(method,[view],target,cfg)
  p=predict(model,method,view['test_x'],0,target);query=[i for i,v in enumerate(part)if v=='test'];rows.append({'variant':name,'score':metric(target,yy[query],p,recipe.get('classes')),'selection':selection})
 return rows

def render(output,panel,arrays,tables):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 fig,ax=plt.subplots(figsize=(8,5));ax.set_title(panel['id']+' / '+panel['operator'])
 if arrays:
  for name,value in arrays.items():
   v=np.asarray(value)
   if v.ndim==1:ax.plot(v,label=name)
   elif v.ndim>=2:ax.plot(v.reshape(v.shape[0],-1).mean(axis=1),label=name+' mean')
  ax.legend()
 else:ax.axis('off');ax.text(0,1,str(tables)[:6000],va='top',wrap=True,fontsize=6)
 fig.tight_layout();fig.savefig(output/'panel.pdf');fig.savefig(output/'panel.png',dpi=160);plt.close(fig)
