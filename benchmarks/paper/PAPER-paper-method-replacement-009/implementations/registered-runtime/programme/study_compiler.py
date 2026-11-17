"""Actual finite catalogue→complete case/fold/reference/panel dispatch compiler.
Input is an authenticated original protocol catalogue, not a runtime receipt.
"""
from copy import deepcopy
from .full_plan import validate,need,COHORTS,CONDITIONS,PANEL_OPERATORS

def compile_study(catalogue):
 need(catalogue['schema']=='trial_original_catalogue_v4','source catalogue version')
 need(catalogue['source_bindings']and catalogue['original_definition']is not None,'original source-selected catalogue')
 cases=deepcopy(catalogue['cases']);jobs=[];reference_ids={}
 # Case order is original catalogue order; no filename enumeration or hash sort.
 for case in cases:
  ids=[]
  for method in('linear','single_rrr','mlp'):
   key='ref-'+str(len(jobs));ids.append(key)
   jobs.append({'id':key,'role':'reference','arm':'paper_data','method':method,'cases':[case['id']],
    'fold':case['fold'],'prior_training_cases':[],'configuration':catalogue['configurations'][case['target']][method],
    'split':case['split'],'depends_on':[]})
  reference_ids[case['id']]=ids
 # Shared models follow source-selected empirical groupings, not all-pairs
 # Cartesian products or a replacement forty-session population.
 for group in catalogue['shared_groups']:
  for method in group['methods']:
   need(method in('multi_rrr','multi_region_rrr','multi_linear','multi_mlp'),'fixed shared family')
   jobs.append({'id':'ref-'+str(len(jobs)),'role':'reference','arm':'paper_data','method':method,'cases':group['cases'],
    'fold':group['fold'],'prior_training_cases':[],'configuration':group['configurations'][method],'split':group['split'],'depends_on':[]})
 for group in catalogue['state_folds']:
  method=group['method'];need(group['source']is not None,'source-owned whole non-target cohort definition');need(method in('hmm','bmm_hmm','empirical_bmm_hmm','lg_ar1','empirical_lg_ar1'),'complete state family')
  query=[c for c in cases if c['id']in group['query_cases']];training=[c for c in cases if c['id']in group['training_cases']]
  need(not({c['session']for c in query}&{c['session']for c in training}),'held session excluded from full empirical prior fit')
  need(set(group['training_cases'])=={c['id']for c in cases if c['id']in group['prior_population_cases']and c['session']not in{q['session']for q in query}},'all non-target sessions retained; no partial prior training substitute')
  jobs.append({'id':'state-'+str(len(jobs)),'role':'reference','arm':'paper_data','method':method,'cases':group['query_cases'],
   'fold':group['fold'],'prior_training_cases':group['training_cases'],'configuration':group['configuration'],'split':group['split'],
   'depends_on':[reference_ids[c][1]for c in group['query_cases']]})
 # Frozen candidate programme/policy is invoked in fresh fold-specific workers.
 # Other folds' products and coordinator feedback are never input views.
 for fold in catalogue['candidate_folds']:
  need(fold['source']is not None,'source-owned original/prospective fold definition')
  query=[c for c in cases if c['id']in fold['query_cases']];training=[c for c in cases if c['id']in fold['training_cases']]
  need(not({c['session']for c in query}&{c['session']for c in training}),'candidate fold session separation')
  for arm in CONDITIONS:
   jobs.append({'id':'candidate-'+str(len(jobs)),'role':'candidate','arm':arm,'method':'improved','cases':fold['query_cases'],
    'fold':fold['id'],'prior_training_cases':fold['training_cases'],'configuration':fold['configuration'],'split':fold['split'],'depends_on':[]})
 panels=deepcopy(catalogue['panels'])
 operations={}
 for key,kind in [('prepare','prepare'),('score','score'),('literal_release','literal_release')]+[(j['id'],'candidate'if j['role']=='candidate'else'reference')for j in jobs]+[(p['id'],'panel')for p in panels]:
  operations[key]=deepcopy(catalogue['operation_caps'][kind])
 study={k:deepcopy(catalogue[k])for k in('canonical','recipe','cohorts','limits','artifact_caps','resource_plan')}
 study.update(schema='trial_full_study_v4',cases=cases,jobs=jobs,panels=panels,operations=operations,
  source_bindings=catalogue['source_bindings'],original_definition=catalogue['original_definition'],
  history='Cross-validation with original source-selected fold order; folds are not independent people',
  compiler='programme.study_compiler.compile_study')
 return validate(study)
