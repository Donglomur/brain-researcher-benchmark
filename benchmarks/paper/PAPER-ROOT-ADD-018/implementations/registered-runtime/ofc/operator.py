"""Trusted orchestration: complete source workers, independent references, grading."""
from pathlib import Path
import shutil
from .common import require,exact_keys,identity,load,write_new,plain_path,now,census,token
from .contracts import TASK,CONDITIONS,design,submission,plan
from .host import run_condition
from .grader import grade
from .report import assemble

def load_review(path,package,other_reserve_bytes,started=None):
 review=load(path,32768);exact_keys(review,('schema','task_id','implementation_source_id','mode','scientific_authorized','execution','plans','private_targets','reference_programs','allowed_conditions','history_id','wall_seconds','output_reservation_bytes','qualification'))
 require(review['schema']=='ofc-operator-review-v1'and review['task_id']==TASK,'operator review')
 require(type(other_reserve_bytes)is int and other_reserve_bytes>=0,'other reserve')
 require(type(review['wall_seconds'])is int and review['wall_seconds']>0,'wall reservation')
 require(type(review['output_reservation_bytes'])is int and review['output_reservation_bytes']>0,'output reservation')
 def clock_check():
  if started is not None:
   from .lifecycle import DeadlineExceeded
   if now()>=started+review['wall_seconds']:raise DeadlineExceeded('original campaign deadline during review admission')
 clock_check();source=load(Path(package)/'RUNTIME_SOURCE_PINS.json');require(review['implementation_source_id']==identity(source),'review stale implementation')
 for relative,pin in source['files'].items():
  clock_check();loadpin=Path(package)/relative;from .common import bounded_read;bounded_read(loadpin,pin['bytes'],pin);clock_check()
 if review['mode']=='engineering':
  require(review['scientific_authorized']is False and review['execution']['mode']=='trusted_inert_engineering','engineering/scientific boundary')
 else:
  require(review['mode']=='qualified_science'and review['scientific_authorized']is True,'scientific review scope')
  require(review['execution']['mode']=='qualified_docker','qualified science requires external isolation')
  qualification=load(review['qualification']['path'],pin=review['qualification'])
  require(qualification['implementation_source_id']==review['implementation_source_id']and qualification['all_scientific_gates_passed']is True,'scientific gate qualification')
  require(set(qualification['gate_ids'])=={'G%02d'%i for i in range(1,11)},'all10 gate identities')
 return review

def stage_ids(p):
 phases=['build','investigate','fit']
 if p['condition'].startswith('R'):phases+=['analyze']
 else:
  for family in (f for f in p['scope']['family_ids']if f.startswith('I_')):phases+=['predict']*len({q['stream_id']for q in p['public_universes'][family]})
 return ['%05d-%s'%(i+1,phase)for i,phase in enumerate(phases)]

def execute(program_file,output,review_file,other_reserve_bytes,condition='all',package=None,*,on_complete=None):
 from .lifecycle import Campaign,DeadlineExceeded,LifecycleError,error_record
 entered=now();package=Path(package or Path(__file__).resolve().parents[1]);documents=design(package);review=load_review(review_file,package,other_reserve_bytes,entered)
 deadline=entered+review['wall_seconds']
 def admission():
  if now()>=deadline:raise DeadlineExceeded('original campaign deadline during input admission')
 admission();candidate=submission(load(program_file));admission();selected=list(CONDITIONS)if condition=='all'else[condition]
 require(set(selected)<=set(review['allowed_conditions']),'condition not selected');require(condition=='all'or condition in CONDITIONS,'unknown condition')
 plans={}
 for k,v in review['plans'].items():
  if k not in selected:continue
  admission();plans[k]=plan(load(v['path'],pin=v),documents);admission()
 require(set(plans)==set(selected),'missing exact condition plan');require(all(p['condition']==k for k,p in plans.items()),'plan condition mismatch')
 jobs={};programs=[];seen=set()
 for cond in selected:jobs['candidate/'+cond]=stage_ids(plans[cond])
 for definition in review['reference_programs']:
  admission();token(definition['id']);require(definition['id']not in seen,'duplicate independent reference');seen.add(definition['id']);ref_program=submission(load(definition['program']['path'],pin=definition['program']));programs.append((definition,ref_program))
  for cond in selected:
   if cond in definition['conditions']:jobs['references/'+definition['id']+'/'+cond]=stage_ids(plans[cond])
 admission();root=plain_path(output);require(not root.exists(),'fresh output required');require(root.parent.is_dir(),'existing output parent required');require(shutil.disk_usage(root.parent).free>=review['output_reservation_bytes']+other_reserve_bytes,'free bytes after other reservations')
 campaign=Campaign(root,review['output_reservation_bytes'],deadline,jobs,clock=now,identity_binding={'root':str(root),'review_id':identity(review),'program_id':identity(candidate),'plan_ids':{k:identity(v)for k,v in plans.items()},'jobs_id':identity(jobs)});results=[];refs=[];score_records=[];report=None;primary=None
 def run_job(label,program,p):
  failure=None;outcome=None
  try:
   with campaign.context.nested('condition '+label,p['budget']['wall_seconds'])as context:
    context.protected('condition start');outcome=run_condition(program,p,documents,review['execution'],root/label,context.deadline,label);context.protected('condition end');return outcome
  except BaseException as e:failure=e;campaign.record_primary_failure(e);raise
  finally:
   record={'job_id':label,'status':'failed'if failure is not None else'closed','first_failure':None if failure is None else error_record(failure),'attempts':sum(a['job_id']==label for a in campaign.attempts),'natural_complete':False if outcome is None else outcome['execution_chain']['natural_complete']}
   try:
    campaign.close_condition(label,record)
    if failure is None:
     try:context.check('condition terminal closure')
     except BaseException as closing_deadline:
      record.update(status='failed',first_failure=error_record(closing_deadline),natural_complete=False)
      try:campaign.slots[(label,None)].put({'state':'condition_closed',**record})
      except BaseException as publication_error:campaign.record_closure_error(publication_error)
      raise
   except BaseException:
    if failure is None:raise
 with campaign.active()as context:
  try:
   context.check('START publication');write_new(root/'START.json',{'review_id':identity(review),'program_id':identity(candidate),'implementation_source_id':review['implementation_source_id'],'conditions':selected,'private_targets_opened':False,'other_reserve_bytes':other_reserve_bytes,'campaign_id':campaign.id,'original_campaign_deadline':deadline,'closure_reserved_before_children':True})
   for cond in selected:results.append(run_job('candidate/'+cond,candidate,plans[cond]));context.protected('next condition')
   for definition,ref_program in programs:
    for cond in selected:
     if cond not in definition['conditions']:continue
     outcome=run_job('references/'+definition['id']+'/'+cond,ref_program,plans[cond]);require(outcome['execution_chain']['source_id']==definition['qualified_source_id'],'actual reference source differs from independent definition');refs.append({'reference_id':definition['id'],'condition':cond,'qualified_source_id':definition['qualified_source_id'],'outcome':outcome});context.protected('next independent reference')
   context.protected('prediction closure');write_new(root/'PREDICTIONS_CLOSED.json',{'candidate_collections':[r['sealed_submission']for r in results],'reference_collections':[r['outcome']['sealed_submission']for r in refs],'all_selected_predictions_closed':True,'selected_conditions':selected})
   for result in results:
    context.protected('private target open');cond=result['condition'];private=load(review['private_targets'][cond]['path'],pin=review['private_targets'][cond]);references={}
    for r in refs:
     context.protected('protected reference join')
     if r['condition']!=cond:continue
     rec=r['outcome']['record'];references[r['reference_id']]={'rows':rec['rows'],'natural_complete':rec['receipt_chain']['natural_complete']and not rec['invalid_families'],'qualified_source_id':r['qualified_source_id'],'plan_id':rec['plan_id'],'policy_id':rec['policy_id'],'public_universe_id':rec['public_universe_id']}
    context.protected('protected grader');scores=grade(plans[cond],result['record'],private,references,scientific_authorization=review['scientific_authorized']);context.protected('score publication');score_records.append(scores);write_new(root/'scores'/f'{cond}.json',scores)
   context.protected('report assembly');report=assemble(plans[selected[0]]['scope'],results,score_records,[{'reference_id':r['reference_id'],'condition':r['condition'],'execution_chain':r['outcome']['execution_chain'],'collection':r['outcome']['sealed_submission']}for r in refs],{'history_id':review['history_id'],'implementation_source_id':review['implementation_source_id']});report['campaign_id']=campaign.id;report['resource_accounting']=campaign.ledger.snapshot();report['resource_accounting']['measurement_cutoff']='before REPORT publication; final counters and identity in custody/campaign.json';report['final_resource_custody']='custody/campaign.json';context.protected('final report');write_new(root/'REPORT.json',report);context.protected('report completion')
  except BaseException as e:
   primary=e;campaign.record_primary_failure(e)
   # Ordinary failure detail is best-effort. The precharged campaign slot is
   # authoritative and keeps the first cause even if every ordinary write fails.
   try:write_new(root/'FAILED.json',{'first_failure':error_record(e),'candidate_results_closed':len(results),'reference_results_closed':len(refs),'original_attempts':campaign.attempts,'resource_accounting':campaign.ledger.snapshot()},closing=True)
   except BaseException as secondary:campaign.record_closure_error(secondary)
  finally:terminal=campaign.finish(primary)
 if primary is not None:raise primary
 campaign.require_outer_success(terminal,'outer output admission after descriptor closes')
 if on_complete is not None:
  try:on_complete(report)
  except BaseException as error:
   campaign.record_closure_error(error);terminal['status']='failed';terminal['outer_failure']=error_record(error);terminal['first_failure']=campaign.first_failure;terminal['closure_errors']=campaign.closure_errors[:3];raise
 campaign.require_outer_success(terminal,'actual outer success return after final output')
 return report
