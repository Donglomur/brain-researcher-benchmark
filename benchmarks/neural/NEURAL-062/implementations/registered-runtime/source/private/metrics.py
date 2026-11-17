"""Matched-support class/experiment/mouse metrics; source-derived artifact score only."""
from collections import defaultdict
import math,statistics
import protocol as p
EPS=1e-12
def mean(v):return sum(v)/len(v) if v else None
def point(label,prob):
 chosen=max(range(8),key=lambda i:prob[i]);return int(chosen==label),-math.log(max(EPS,prob[label]))
def case_metrics(case,prob):
 cells=defaultdict(list)
 for r in case['rows']:cells[(r['experiment'],r['bin'],r['label'])].append(point(r['label'],prob[r['id']]))
 strata=defaultdict(dict)
 for (exp,b,label),values in cells.items():strata[(exp,b)][label]=(mean([v[0] for v in values]),mean([v[1] for v in values]))
 exps=defaultdict(list)
 for (exp,b),by in strata.items():
  p.need(set(by)==set(range(8)),'All8classes in matched stratum');exps[exp].append((mean([v[0] for v in by.values()]),mean([v[1] for v in by.values()])))
 exp_metrics={e:(mean([x[0] for x in v]),mean([x[1] for x in v])) for e,v in exps.items()}
 missing=sorted(set(case['expected_experiments'])-set(exps));return {'balanced_accuracy':mean([v[0] for v in exp_metrics.values()]),'log_loss':mean([v[1] for v in exp_metrics.values()]),'supported_experiments':len(exps),'expected_experiments':len(case['expected_experiments']),'unsupported_experiments':missing,'matched_strata':len(strata),'query_observations':len(case['rows'])}
def aggregate(reference,pred):
 records={}
 for arm in p.ARMS:records[arm]={c['case']:case_metrics(c,pred[(c['case'],arm)]) for c in reference['cases']}
 return aggregate_records(reference,records)
def aggregate_records(reference,records):
 out={}
 for split in('validation','test'):
  out[split]={}
  for context in p.CONTEXTS:
   selected=[c for c in reference['cases'] if c['split']==split and c['context']==context];expected={c['mouse'] for c in selected};byarm={}
   for arm in p.ARMS:
    mouse=defaultdict(list)
    for c in selected:mouse[c['mouse']].append(records[arm][c['case']])
    values={s:None if any(v['balanced_accuracy'] is None for v in vv) else {'balanced_accuracy':mean([v['balanced_accuracy'] for v in vv]),'log_loss':mean([v['log_loss'] for v in vv])} for s,vv in mouse.items()};complete=all(v is not None for v in values.values()) and set(values)==expected
    byarm[arm]={'complete_mouse_image_set_support':complete,'by_mouse':values,'balanced_accuracy':mean([v['balanced_accuracy'] for v in values.values()]) if complete else None,'log_loss':mean([v['log_loss'] for v in values.values()]) if complete else None,'descriptive_mouse_SE_log_loss':statistics.stdev([v['log_loss'] for v in values.values()])/math.sqrt(len(values)) if complete and len(values)>1 else None}
   a=byarm['CONTEXT']['log_loss'];b=byarm['POST']['log_loss'];pre=byarm['PRE']['log_loss']
   out[split][context]={'by_arm':byarm,'descriptive_POST_log_loss_reduction_over_CONTEXT':None if a is None or b is None else a-b,'descriptive_POST_log_loss_reduction_over_PRE':None if pre is None or b is None else pre-b}
 primary=out['test']['CHANGE']['by_arm']['POST']['balanced_accuracy']
 return {'metrics':out,'case_coverage_and_metrics':records,'primary_score':primary,'primary_definition':'testmouse-macro matched-support CHANGE/POST balanced accuracy; prediction validity only','increment_ranking_qualified':False,'comparison_recipe_verified':False,'runtime_isolation_verified':False,'causal_onset_claim':False}
