"""Two-arm protected scoring, complete dispositions and equal-animal effects."""
from .native.io import load,dump,need
from .full_worker import array_read

def metric(target,y,p,classes=None):
 import numpy as np
 from sklearn.metrics import roc_auc_score,accuracy_score,r2_score,log_loss,brier_score_loss
 from scipy.stats import pearsonr
 need(y.shape[0]==p.shape[0]and np.isfinite(y).all()and np.isfinite(p).all(),'matched finite score support')
 if target in('choice','lick'):
  yy=y.reshape(-1);pp=p.reshape(-1);need(np.all((pp>=0)&(pp<=1)),'probability bounds')
  return {'primary':None if len(np.unique(yy))!=2 else float(roc_auc_score(yy,pp)),
   'accuracy':float(accuracy_score(yy,pp>=.5)),'brier':float(brier_score_loss(yy,pp)),
   'log_loss':float(log_loss(yy,np.c_[1-pp,pp],labels=[0,1])),'primary_name':'AUROC'}
 if target in('gabors','static-gratings'):
  need(np.all(p>=0)and np.allclose(p.sum(axis=1),1),'multiclass probabilities')
  return {'primary':float(accuracy_score(y.reshape(-1),np.asarray(classes)[p.argmax(axis=1)])),
   'macro_auc':float(roc_auc_score(y.reshape(-1),p,multi_class='ovr',average='macro',labels=classes))if len(np.unique(y))==p.shape[1]else None,'primary_name':'accuracy'}
 if target=='prior':
  yy=y.reshape(-1);pp=p.reshape(-1);value=None if len(yy)<2 or np.ptp(yy)==0 or np.ptp(pp)==0 else float(pearsonr(yy,pp).statistic)
  return {'primary':value,'primary_name':'Pearson'}
 value=None if y.shape[0]<2 or np.all(np.var(y,axis=0)==0)else float(r2_score(y,p,multioutput='uniform_average'))
 return {'primary':value,'primary_name':'R2'}

def equal_animal(rows):
 import numpy as np
 groups={}
 for row in rows:
  if row['value']is not None:groups.setdefault(row['animal'],{}).setdefault(row['session'],[]).append(row['value'])
 means={a:float(np.mean([np.mean(v)for v in sessions.values()]))for a,sessions in groups.items()}
 return {'value':None if not means else float(np.mean(list(means.values()))),'animal_values':means,'animals':len(means),'sessions':sum(len(v)for v in groups.values()),'unit':'equal animal; sessions and regions averaged within animal'}

def score_worker(request,inputs,output):
 import numpy as np
 study=load(inputs/'study.json');index=load(inputs/'SCORE_INPUTS.json');cases={c['id']:c for c in study['cases']};predictions={};dispositions=[]
 # ALL prediction arrays and their complete coordinate envelopes are parsed
 # before the first protected truth array is read. No interleaved tuning.
 for row in index['outputs']:
  doc=load(inputs/row['manifest']);job=next(j for j in study['jobs']if j['id']==doc['job'])
  need(doc['cases']==job['cases']and doc['arm']==job['arm'],'full score job inverse')
  need(len(doc['predictions'])==len(job['cases'])and{r['case']for r in doc['predictions']}==set(job['cases']),'one complete prediction per intended case')
  for item in doc['predictions']:
   case=cases[item['case']];meta=load(inputs/index['case_metadata'][case['id']]);query=[i for i,p in enumerate(meta['partition'])if p=='test']
   need(item['query_rows']==query and item['trial_ids']==[meta['trial_ids'][i]for i in query],'complete same original query order')
   value=array_read(inputs,item['prediction']);need(len(value)==len(query)and np.isfinite(value).all(),'all predictions finite before target')
   predictions[(job['id'],case['id'])]=(value,item.get('classes'))
 target={}
 for key,path in index['private_cases'].items():
  meta=load(inputs/path);truth=array_read(inputs,meta['arrays']['truth']);query=[i for i,p in enumerate(meta['partition'])if p=='test'];target[key]=truth[query]
 results=[]
 for job in study['jobs']:
  if job['role']=='panel':continue
  for key in job['cases']:
   case=cases[key];p=predictions.get((job['id'],key));y=target.get(key)
   row={'job':job['id'],'case':key,'role':job['role'],'arm':job['arm'],'method':job['method'],'target':case['target'],'session':case['session'],'animal':case['animal'],'cohort':case['cohort']}
   if p is None or y is None:row.update(status='unavailable',reason='missing_full_prediction_or_truth_support',metrics=None)
   else:row.update(status='complete',reason=None,metrics=metric(case['target'],y,p[0],p[1]))
   results.append(row)
 # References are frozen by validation-only selector in the captured manifest,
 # not selected by any query metric. Full expected denominators remain visible.
 selection=index['reference_selection'];effects=[]
 for target_name in('choice','prior','wheel-speed','whisker-motion-energy'):
  expected=[c for c in study['cases']if c['cohort']=='prospective40'and c['target']==target_name]
  for arm in('paper_data','paper_data_author_code'):
   pairs=[];missing=[]
   for case in expected:
    refs=[r for r in results if r['case']==case['id']and r['job']==selection[case['id']]]
    candidates=[r for r in results if r['case']==case['id']and r['role']=='candidate'and r['arm']==arm]
    need(len(candidates)<=1,'one frozen evaluated candidate per arm/case')
    if len(refs)!=1 or len(candidates)!=1 or refs[0]['metrics']is None or candidates[0]['metrics']is None or refs[0]['metrics']['primary']is None or candidates[0]['metrics']['primary']is None:missing.append(case['id']);continue
    pairs.append({'animal':case['animal'],'session':case['session'],'value':candidates[0]['metrics']['primary']-refs[0]['metrics']['primary']})
   effects.append({'target':target_name,'arm':arm,'paired_effect':equal_animal(pairs),'expected_cases':len(expected),'matched_cases':len(pairs),'missing':missing,'complete_support':not missing})
 arm_effects=[]
 for target_name in('choice','prior','wheel-speed','whisker-motion-energy'):
  expected=[c for c in study['cases']if c['cohort']=='prospective40'and c['target']==target_name];pairs=[];missing=[]
  for case in expected:
   byarm={arm:[r for r in results if r['case']==case['id']and r['role']=='candidate'and r['arm']==arm]for arm in('paper_data','paper_data_author_code')}
   if any(len(v)!=1 or v[0]['metrics']is None or v[0]['metrics']['primary']is None for v in byarm.values()):missing.append(case['id']);continue
   pairs.append({'animal':case['animal'],'session':case['session'],'value':byarm['paper_data_author_code'][0]['metrics']['primary']-byarm['paper_data'][0]['metrics']['primary']})
  arm_effects.append({'target':target_name,'contrast':'code_arm_minus_paper_data_arm','paired_effect':equal_animal(pairs),'expected_cases':len(expected),'matched_cases':len(pairs),'missing':missing,'complete_support':not missing,'causal':False})
 result={'schema':'trial_full_protected_score_v4','rows':results,'effects':effects,'paired_arm_effects':arm_effects,'co_primary_targets':4,
 'multiplicity':'four targets and both arms reported; no confirmatory rule selected','confidence_interval':None,'superiority_margin':None,
 'meaningful_improvement_qualified':False,'causal_code_benefit_claim':False,'all_expected_support':len(study['cases'])}
 dump(output/'SCORES.private.json',result);return result
