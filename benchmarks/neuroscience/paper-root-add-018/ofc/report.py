"""Full-scope assembly preserves failures, costs, conditions and qualification."""
from .common import require,identity,guard
from .contracts import FAMILIES,CONDITIONS,TASK
def assemble(scope,condition_results,score_records,reference_runs,history):
 guard('report admission');require(len(scope['obligation_ids'])==74 and len(scope['role_ids'])==20 and scope['simulation_cases']==200,'full report scope')
 resultmap={r['condition']:r for r in condition_results};scores={s['condition']:s for s in score_records};require(len(resultmap)==len(condition_results)and set(scores)==set(resultmap),'condition report bijection')
 reports=[]
 for condition,result in resultmap.items():
  guard('report condition')
  record=result['record'];score=scores[condition];require(score['submission_id']==identity(record),'score belongs to another collection')
  require(score['condition']==record['condition']==condition and score['plan_id']==record['plan_id']and score['policy_id']==record['policy_id'],'score condition/plan/policy binding')
  require(score['source_id']==record['receipt_chain']['source_id']and score['model_id']==record['receipt_chain']['model_id'],'score source/model mismatch')
  expected={f for f in FAMILIES if f.startswith(condition[0]+'_')};actual={s['family_id']for s in score['scores']};require(actual==expected and len(actual)==len(score['scores']),'complete family score join')
  rows={r['query_id']:r for r in record['rows']};family_scores={r['family_id']:r for r in score['scores']};obligations=[]
  for oid in scope['obligation_ids']:
   guard('report obligation')
   if condition[0]=='I':obligations.append({'id':oid,'required':True,'status':'historical_reproduction_separate_condition'});continue
   require(oid in rows,'native obligation absent from sealed support');row=rows[oid];family=family_scores[row['family_id']]
   obligations.append({'id':oid,'required':True,'submitted_disposition':row['disposition'],'family_disposition':family['family_disposition'],'candidate_status':family['candidate_status'],'target_status':family['target_status'],'status':'keyed_product_received_unqualified'if row['disposition']=='value'else'required_product_not_validly_delivered'})
  reports.append({'condition':condition,'source_id':score['source_id'],'model_id':score['model_id'],'native_obligations':obligations,'roles':[{'id':role,'required':True,'qualification':'open'}for role in scope['role_ids']],'simulation_cases_required':200,'scores':score['scores'],'execution':result['execution_chain'],'sealed_submission':result['sealed_submission'],'whole_program_improvement_claim':False})
 return {'schema':'ofc-complete-report-v1','task_id':TASK,'scope':scope,'conditions':reports,'condition_order':list(resultmap),'all_four_conditions_present':set(resultmap)==set(CONDITIONS),'all16families_preserved':list(FAMILIES),'reference_runs':reference_runs,'history':history,'open_gates':scope['open_gate_ids'],'full_paper_scientifically_reproduced':False,'scientifically_qualified':False,'new_benchmarks':0,'installed_source_change':0,'limitations':['Complete source and engineering evidence is not authentic scientific qualification.','No full-paper label while complete supplement, native producer, cohort, baseline or inference gates remain open.','Separate complete family values do not create a mixed-unit scalar or erase another family failure.']}
