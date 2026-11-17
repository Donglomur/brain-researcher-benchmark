"""Complete collection, target-last barrier, paired mouse-level fixed-reference report."""
import delivery_io as io
import protocol as p
from score import admit,validate_plan
OWNERS=('participant','logistic','hgb')
MODES=('F','I')
def jobs(plan):
 validate_plan(plan);io.need(len(plan['cases'])==136,'all136 held cases')
 return [(o,m,c['case'],a)for o in OWNERS for m in MODES for c in plan['cases']for a in p.ARMS]
def barrier(plan,records,owner):
 expected=jobs(plan);io.need(set(records)==set(expected),'complete3264 job collection')
 cases={c['case']:c for c in plan['cases']}
 with owner.stage('complete_target_free_prediction_admission'):
  for key in expected:
   r=records[key];io.exact(r,['path','pin','fit','infer','state_pin'])
   io.need(r['fit']['complete']is True and r['infer']['complete']is True and r['fit']['retired']is True and r['infer']['retired']is True,'both phases retired')
   admit(io.json_file(r['path'],160_000_000,r['pin']),plan,cases[key[2]],key[3])
 return tuple(expected)
def paired(reports,mode):
 result={}
 for ref in ('logistic','hgb'):
  groups={}
  for split in ('validation','test'):
   for context in p.CONTEXTS:
    for arm in p.ARMS:
     left=reports['participant_'+mode]['metrics'][split][context]['by_arm'][arm]
     right=reports[ref+'_'+mode]['metrics'][split][context]['by_arm'][arm]
     io.need(set(left['by_mouse'])==set(right['by_mouse']),'same fixed mouse support')
     rows={}
     for mouse in sorted(left['by_mouse']):
      a=left['by_mouse'][mouse];b=right['by_mouse'][mouse]
      rows[mouse]=None if a is None or b is None else {'balanced_accuracy_difference':a['balanced_accuracy']-b['balanced_accuracy'],'log_loss_reduction':b['log_loss']-a['log_loss']}
     complete=all(x is not None for x in rows.values())and bool(rows)
     groups[split+'/'+context+'/'+arm]={'by_mouse':rows,'complete_support':complete,'balanced_accuracy_difference':sum(x['balanced_accuracy_difference']for x in rows.values())/len(rows)if complete else None,'log_loss_reduction':sum(x['log_loss_reduction']for x in rows.values())/len(rows)if complete else None}
  result[ref]={'comparisons':groups,'primary':groups['test/CHANGE/POST'],'claim':'descriptive paired mice; four panels/strata are not independent mice; no automatic winner or SOTA claim'}
 return result
def protected_score(plan,records,load_gold,cohort,owner):
 from score import validate_reference
 from metrics import case_metrics,aggregate_records
 # The barrier is called here, not trusted as a caller-supplied flag.
 barrier(plan,records,owner)
 with owner.stage('protected_targets_after_complete_collection_and_retirement'):
  gold=load_gold();validate_reference(gold,plan,cohort);reports={};cases={c['case']:c for c in plan['cases']}
  for who in OWNERS:
   for mode in MODES:
    summaries={a:{}for a in p.ARMS}
    for c in gold['cases']:
     for arm in p.ARMS:
      r=records[(who,mode,c['case'],arm)]
      prob=admit(io.json_file(r['path'],160_000_000,r['pin']),plan,cases[c['case']],arm)
      summaries[arm][c['case']]=case_metrics(c,prob)
    reports[who+'_'+mode]=aggregate_records(gold,summaries)
  return {'reports':reports,'paired_references':{m:paired(reports,m)for m in MODES},'scientifically_qualified':False,'canonical_count_delta':0,'validation_role':'protected diagnostics, never fit or adaptation','test_role':'protected primary CHANGE/POST'}
