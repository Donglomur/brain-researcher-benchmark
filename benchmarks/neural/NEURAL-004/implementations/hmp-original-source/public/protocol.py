"""Finite retrospective HMP contract; no scientific imports."""
import math,hashlib,json
PEOPLE=tuple(str(i) for i in range(26))
STAGES=tuple('interval_'+str(i) for i in range(6))+('encoding_1_2','decision_3_4')
EFFECTS=('mean_ms','contrast_speed_ms','contrast_accuracy_ms','motor_side_ms','rotated_speed_ms','rotated_accuracy_ms')
CURVES=('linear','pieron','fechner')
CONDITIONS=('speed','accuracy')
REASONS=(None,'rank_deficient','insufficient_support','fit_failed')
MODE='retrospective_loo_stage_v1'
def need(test,message):
 if not test:raise ValueError(message)
def metric_keys():
 return tuple(['hmp_'+str(k)+'_nats_per_trial' for k in (4,5,6)]+[s+'/'+e for s in STAGES for e in EFFECTS]+['event_'+str(k)+'/response_lag_'+e for k in range(5) for e in ('mean_ms','contrast_speed_ms','contrast_accuracy_ms')]+[s+'/'+c+'/'+m+'_rmse_ms' for s in STAGES for c in CONDITIONS for m in CURVES])
KEYS=metric_keys()
def cell(value,support,reason=None):
 return {'value':None if value is None else float(value),'support':int(support),'reason':reason}
def validate(report,dataset_sha256):
 need(type(dataset_sha256)is str and len(dataset_sha256)==64 and all(c in '0123456789abcdef' for c in dataset_sha256),'Exact SHA256 identity')
 need(type(report)is dict and set(report)=={'schema','mode','dataset_sha256','people'},'Exact report keys')
 need(report['schema']=='neural004_report_v1' and report['mode']==MODE and report['dataset_sha256']==dataset_sha256,'Report identity')
 need(type(report['people'])is list and len(report['people'])==26,'All26people')
 for pid,row in zip(PEOPLE,report['people']):
  need(type(row)is dict and set(row)=={'person','n_trials','design_rank','negative_interval_trials','metrics'} and row['person']==pid,'Ordered26person identities')
  n=row['n_trials'];need(type(n)is int and 1<=n<=100000,'Finite trial support')
  need(type(row['design_rank'])is int and 0<=row['design_rank']<=5 and type(row['negative_interval_trials'])is int and 0<=row['negative_interval_trials']<=n,'Rank/negative interval support')
  need(type(row['metrics'])is dict and set(row['metrics'])==set(KEYS),'Exact metric identities')
  for key,x in row['metrics'].items():
   need(type(x)is dict and set(x)=={'value','support','reason'},'Exact metric cell')
   need(type(x['support'])is int and 0<=x['support']<=100000 and x['reason'] in REASONS,'Metric support/reason')
   v=x['value']
   if v is None:need(x['support']==0 and x['reason'] is not None,'Explicit undefined metric')
   else:
    need(type(v)in (int,float) and -1e12<=v<=1e12 and math.isfinite(v) and x['support']>0 and x['reason'] is None,'Bounded finite metric')
    if key.endswith('_rmse_ms'):need(v>=0,'Nonnegative RMSE')
   if key.startswith('hmp_'):need(v is not None and x['support']==n,'All fixed-count HMP outcomes required')
  m=row['metrics']
  for a,b,c in [('encoding_1_2','interval_1','interval_2'),('decision_3_4','interval_3','interval_4')]:
   for e in EFFECTS:
    u,v,w=(m[z+'/'+e] for z in (a,b,c))
    need((u['value'] is None)==(v['value'] is None)==(w['value'] is None),'Shared linear contrast missingness')
    if u['value'] is not None:need(abs(u['value']-v['value']-w['value'])<=1e-6*max(1,abs(u['value']),abs(v['value']),abs(w['value'])),'Dual-stage linear identity')
 return report
