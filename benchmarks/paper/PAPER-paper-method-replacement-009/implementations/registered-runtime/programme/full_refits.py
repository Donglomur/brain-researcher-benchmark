"""Prospective single behavior-PC and matched observed/imposter comparisons.

These fixed computations are not historical S3/S4 parity or a null hypothesis
test. All inputs are fresh post-capture products. No numerical call is made by
source construction. The historical null aggregation remains unissued.
"""
from .native.io import need
from .domain import MissingDefinition

DYNAMIC_FAMILIES=('linear','single_rrr','mlp','multi_rrr','multi_region_rrr','multi_linear','multi_mlp')
LOCAL_FAMILIES=('linear','single_rrr','mlp')
NULL_FAMILIES=('linear','multi_region_rrr')

def roster(recipe):
 rows=recipe['views'];ids=recipe['case_ids']
 need(type(rows)is list and rows and type(ids)is list and ids,'complete selected view roster')
 need([v['case']for v in rows]==ids and len(set(ids))==len(ids),'ordered complete case inverse')
 need(recipe['view_roster_source']is not None,'original session/region membership source remains required')
 for row in rows:
  need(all(type(row[k])is str and row[k]for k in('case','session','animal','region','x','truth')),'exact view identities')
  part=row['partition'];trials=row['trial_ids']
  need(type(part)is list and len(part)==len(trials)and set(part)=={'train','validation','test'},'full three-way original fold support')
  need(len({repr(t)for t in trials})==len(trials),'unique original trial identities')
  need(row['fold_source']is not None,'historical or explicitly prospective fold definition')
 return rows

def materialize_views(a,recipe):
 import numpy as np
 rows=roster(recipe);views=[];sessions={}
 for row in rows:
  x=a[row['x']];y=a[row['truth']]
  need(x.ndim==3 and y.ndim==2 and len(x)==len(y)==len(row['partition']),'full view axes')
  need(np.isfinite(x).all()and np.isfinite(y).all(),'finite full panel support')
  v=dict(row,x_value=x,y_value=y);views.append(v)
  if row['session']in sessions:
   old=sessions[row['session']]
   need(old['animal']==v['animal']and old['trial_ids']==v['trial_ids']and old['partition']==v['partition']and np.array_equal(old['y_value'],y),'same-session regional views have identical target/fold support')
  else:sessions[row['session']]=v
 need(len({v['y_value'].shape[1]for v in views})==1,'shared behavior target axis')
 return views

def fit_condition(views,targets,recipe,methods,condition):
 """Fit every declared family on identical neural/target rows and folds."""
 import numpy as np
 from .interchange import normalize_train_only
 from .full_models import fit_linear_full,fit_neural,predict
 from .full_score import metric
 need(set(targets)=={v['case']for v in views},'complete condition target inverse')
 target=recipe['target'];prepared=[]
 for v in views:
  y=targets[v['case']];need(y.shape==v['y_value'].shape,'same complete behavior extent')
  classification=target in('choice','lick','gabors','static-gratings')
  x,yy,norm=normalize_train_only(v['x_value'],y,v['partition'],classification)
  view={'region':v['region'],'case_id':v['case'],'normalization':norm,'truth':y,'metadata':v}
  for role in('train','validation','test'):
   idx=[i for i,p in enumerate(v['partition'])if p==role];view[role+'_x']=x[idx]
   if role!='test':view[role+'_y']=yy[idx]
  prepared.append(view)
 rows=[]
 for method in methods:
  cfg=recipe['configurations'][method]
  groups=[[v]for v in prepared]if method in LOCAL_FAMILIES else[prepared]
  if method=='multi_region_rrr':need(len({v['region']for v in prepared})>1,'actual complete multiple-region fit, not a renamed single view')
  for group in groups:
   model,selection=fit_linear_full(group[0],target,cfg)if method=='linear'else fit_neural(method,group,target,cfg)
   for index,v in enumerate(group):
    prediction=predict(model,method,v['test_x'],index,target)
    if target not in('choice','lick','gabors','static-gratings'):
     prediction=prediction*v['normalization']['y_sd']+v['normalization']['y_mean']
    meta=v['metadata'];query=[i for i,p in enumerate(meta['partition'])if p=='test']
    score=metric(target,v['truth'][query],prediction,recipe.get('classes'))
    rows.append({'condition':condition,'case':v['case_id'],'session':meta['session'],'animal':meta['animal'],'region':meta['region'],
     'method':method,'query_rows':query,'trial_ids':[meta['trial_ids'][i]for i in query],
     'score':score,'status':'undefined_metric'if score['primary']is None else'complete','selection':selection})
 need(len(rows)==len(views)*len(methods),'all family/case scores retained including undefined values')
 return rows

def single_behavior_pc(a,recipe):
 import numpy as np
 from sklearn.decomposition import PCA
 views=materialize_views(a,recipe)
 need(recipe['target']in('wheel-speed','whisker-motion-energy','running-speed','velocity'),'behavior-PC regression target')
 need(tuple(recipe['models'])==DYNAMIC_FAMILIES and set(recipe['configurations'])==set(DYNAMIC_FAMILIES),'all seven prospective dynamic families')
 # No historical fitting convention is guessed. The selected prospective
 # recipe must state one of these two implemented TRAIN-only basis domains.
 scope=recipe['pca_basis_scope']
 need(scope in('per_session_training','pooled_unique_session_training'),'explicit prospective PCA basis domain; no default')
 unique={}
 for v in views:unique.setdefault(v['session'],v)
 groups=[[v]for v in unique.values()]if scope=='per_session_training'else[list(unique.values())]
 bases={};coordinates={}
 for group in groups:
  train=np.concatenate([v['y_value'][[i for i,p in enumerate(v['partition'])if p=='train']]for v in group],axis=0)
  need(train.shape[0]>=10 and train.shape[1]>=10,'all original first ten behavior PCs; no shortened substitute')
  basis=PCA(n_components=10).fit(train)
  for v in group:
   bases[v['session']]=basis;coordinates[v['session']]=basis.transform(v['y_value'])
 rows=[]
 for pc in range(10):
  targets={}
  for v in views:
   z=coordinates[v['session']];single=np.zeros_like(z);single[:,pc]=z[:,pc]
   targets[v['case']]=bases[v['session']].inverse_transform(single)
  rows.extend(fit_condition(views,targets,recipe,DYNAMIC_FAMILIES,'behavior_pc_'+str(pc+1)))
 return {'recipe':'prospective_single_behavior_pc_v5','historical_S3_parity':False,'pca_fit_scope':scope,
  'target':'one behavior PC reconstructed with fitted training mean; neural predictors unchanged',
  'components':10,'models':list(DYNAMIC_FAMILIES),'case_ids':recipe['case_ids'],
  'expected_scores':10*len(views)*len(DYNAMIC_FAMILIES),'scores':rows,
  'historical_fitting_and_baseline_membership':'unestablished; no historical reproduction claim'}

def matched_imposter_targets(a,views,imposter):
 import numpy as np
 rows=imposter['targets'];ids=[v['case']for v in views]
 need([r['case']for r in rows]==ids,'imposter preserves complete ordered neural view roster')
 need(imposter['source']is not None and imposter['alignment_source']is not None,'original or explicit prospective imposter alignment required')
 targets={};sessions={}
 for v,r in zip(views,rows):
  need(r['source_animal']!=v['animal']and r['source_session']!=v['session'],'different-animal/session null source')
  need(r['target_trial_ids']==v['trial_ids']and len(r['source_trial_ids'])==len(v['trial_ids']),'full explicit imposter-to-query row inverse')
  need(len({repr(t)for t in r['source_trial_ids']})==len(r['source_trial_ids']),'unique matched imposter source rows')
  y=a[r['array']];need(y.shape==v['y_value'].shape and np.isfinite(y).all(),'same finite full imposter target extent')
  if v['session']in sessions:
   old,oldy=sessions[v['session']]
   need(all(old[k]==r[k]for k in('source_session','source_animal','source_trial_ids','target_trial_ids'))and np.array_equal(oldy,y),'same-session region nulls use the same matched imposter')
  else:sessions[v['session']]=(r,y)
  targets[v['case']]=y
 return targets

def paired_null_contrasts(observed,null_rows,case_ids,imposter_id):
 def inverse(rows):
  keys=[(r['case'],r['method'])for r in rows]
  need(len(keys)==len(set(keys))and set(keys)=={(c,m)for c in case_ids for m in NULL_FAMILIES},'complete two-model score vector')
  return dict(zip(keys,rows))
 obs=inverse(observed);null=inverse(null_rows);out=[]
 for case in case_ids:
  rows=[obs[(case,m)]for m in NULL_FAMILIES]+[null[(case,m)]for m in NULL_FAMILIES]
  need(all(r['query_rows']==rows[0]['query_rows']and r['trial_ids']==rows[0]['trial_ids']for r in rows),'observed and null models have identical evaluated support')
  values=[r['score']['primary']for r in rows];missing=any(v is None for v in values)
  gain=None if values[0]is None or values[1]is None else values[1]-values[0]
  null_gain=None if values[2]is None or values[3]is None else values[3]-values[2]
  out.append({'case':case,'imposter':imposter_id,'observed_linear':values[0],'observed_multi_region_rrr':values[1],
   'null_linear':values[2],'null_multi_region_rrr':values[3],'original_gain':gain,'null_gain':null_gain,
   'paired_difference_in_differences':None if missing else gain-null_gain,
   'status':'undefined_metric'if missing else'complete','query_rows':rows[0]['query_rows'],'trial_ids':rows[0]['trial_ids']})
 return out

def matched_imposter_null(a,recipe):
 views=materialize_views(a,recipe)
 need(set(recipe['configurations'])==set(NULL_FAMILIES),'matched linear and multi-region RRR configurations')
 imposters=recipe['imposters'];ids=[r['id']for r in imposters]
 need(ids==recipe['imposter_ids']and len(set(ids))==len(ids)and ids,'complete original selected imposter denominator')
 # Validate all matching envelopes before any observed or null model is fitted.
 targets=[matched_imposter_targets(a,views,r)for r in imposters]
 observed=fit_condition(views,{v['case']:v['y_value']for v in views},recipe,NULL_FAMILIES,'observed')
 scores=[];contrasts=[]
 for row,target in zip(imposters,targets):
  null=fit_condition(views,target,recipe,NULL_FAMILIES,'imposter:'+row['id']);scores.extend(null)
  contrasts.extend(paired_null_contrasts(observed,null,recipe['case_ids'],row['id']))
 return {'recipe':'prospective_matched_imposter_v5','historical_S4_aggregation':None,
  'aggregation_status':'UNISSUED: exact original reduction, p-value and thresholds unavailable',
  'observed_scores':observed,'null_scores':scores,'paired_contrasts':contrasts,
  'expected_cases':len(views),'expected_imposters':len(ids),'expected_matched_contrasts':len(views)*len(ids),
  'selection_uses_query_scores':False,'historical_parity':False,'scientifically_qualified':False}
