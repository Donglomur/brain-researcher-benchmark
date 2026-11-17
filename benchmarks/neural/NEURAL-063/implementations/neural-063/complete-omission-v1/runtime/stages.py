"""All seven concrete runtime stages for the accepted complete programme."""
from __future__ import annotations
import time
import os
from owner.io import Artifact, ContractError, canonical, capture, decode
from owner.model import StageResult
from owner.scoring import admit_predictions
from .contracts import CONDITIONS, STAGES, digest, exact, fixed_graph, full_allocation, prediction, profile, rows
from .controller import Controller, prepare_assets, summary
from .custody import reconcile, claims

INPUTS={
'D00':['fit_T','fit_N','validation_T','validation_N','fit_scale','selection','reference_decision','query_index','checkpoint','tokenizer','model_runtime','candidate_development_recipe'],
'D01':['development_bundle','runtime_assets','query_equivalence'],
'Q00':['development_admission','development_bundle','query_T','query_N','query_index','runtime_assets'],
'Q01':['case_plan','development_bundle','runtime_assets','fit_T','fit_N','validation_T','validation_N','fit_scale','selection'],
'Q02':['event_runs','case_plan','query_index'],
'Q03':['mouse_predictions','case_plan','query_index','fit_scale'],
'N00':['candidate_predictions','prediction_capture','event_runs','development_bundle','runtime_assets','checkpoint','tokenizer','model_runtime','report_recipe'],
}
ROLES={k:k for xs in INPUTS.values() for k in xs};ROLES.update(selection='reference_selection',query_equivalence='reference_query_equivalence')

def read(ctx,key,cap=1_500_000_000):return ctx.read_input(key,roles={ROLES[key]},cap=cap)

def read_ref(ctx,raw,role,cap=1_500_000_000):return ctx.store.read_json(raw,roles={role},cap=cap)

def output(ctx,name,value,role=None,visibility='operator'):
 return ctx.write_json(name+'.json',value,role=role or name,visibility=visibility)

def runtime_profile(ctx):
 p=profile(ctx.parameters['runtime_profile'])
 # One exact profile is shared by every stage and condition, including explicit
 # whole-program aggregate/storage allocation. No unknown event-count guess.
 ctx.store.mkdir('runtime-jobs/'+ctx.stage)
 return p

def training(ctx,view):
 return rows(read(ctx,'fit_'+view),view,'fit'),rows(read(ctx,'validation_'+view),view,'validation')

def scale(ctx):
 value=read(ctx,'fit_scale',1_000_000)
 if value.get('schema')!='neural063_fit_scale_v2' or value.get('fit_mice')!=73 or type(value.get('training_target_sd')) not in (int,float) or value['training_target_sd']<=0:raise ContractError('positive FIT73 scale required')
 return value['training_target_sd']

def selected_models(ctx):
 selected=read(ctx,'selection',100_000_000)
 if set(selected.get('selected',{}))!={'T','N'}:raise ContractError('two frozen selected competent reference views required')
 result={}
 for view in ('T','N'):
  record=selected['selected'][view]['model_record']
  result[view]=read_ref(ctx,record['model'],'reference_primary_model',100_000_000)
  if result[view].get('view')!=view:raise ContractError('sealed reference information view mismatch')
 return result

def failure(exc):return {'class':type(exc).__name__,'message':str(exc)[:2048]}

def retain_controller(ctx,controller,status,*,error=None):
 receipt=output(ctx,controller.identity+'_controller',controller.receipt(status,error),'controller_receipt')
 transcript=output(ctx,controller.identity+'_transcript',{'schema':'neural063_controller_transcript_v1','controller':controller.identity,'condition':controller.condition,'kind':controller.kind,'events':controller.events,'workspace_catalog':{k:{'value_sha256':digest(v),'summary':summary(v),'source':controller.workspace_sources.get(k)} for k,v in controller.workspace.items()}},'controller_transcript')
 return receipt,transcript

def D00(ctx):
 p=runtime_profile(ctx);qindex=read(ctx,'query_index',100_000_000)
 full_allocation(p,len(qindex['ids']))
 decision=read(ctx,'reference_decision',4_000_000)
 if decision.get('outcome') not in {'eligible_for_full_programme'} and decision.get('disposition')!='eligible_for_full_programme':raise ContractError('actual reference competence route did not admit development')
 recipe=read(ctx,'candidate_development_recipe',4_000_000)
 exact(recipe,{'schema','shared_prompt','initial_program_contract','seed'},'development recipe')
 if recipe['schema']!='neural063_development_recipe_v1' or recipe['seed']!=632026 or not isinstance(recipe['shared_prompt'],str):raise ContractError('one preregistered development recipe/seed required')
 storage=p['host_storage']
 if storage['selected_root']!=str(ctx.store.root):raise ContractError('complete runtime storage must bind this exact protected output root')
 observed=ctx.store.read_json(storage['observation'],roles={'runtime_storage_observation'},cap=4_000_000)
 if observed.get('schema')!='neural063_runtime_storage_observation_v1' or observed.get('selected_root')!=str(ctx.store.root):raise ContractError('separately bound full storage observation required')
 fs=os.statvfs(ctx.store.root);capacity=fs.f_frsize*fs.f_blocks;available=fs.f_frsize*fs.f_bavail
 if capacity!=storage['total_capacity_bytes'] or available<storage['additional_retained_bytes']+storage['scratch_peak_bytes']:raise ContractError('actual full runtime storage cannot meet original allocation')
 storage_ref=output(ctx,'runtime_storage_admission',{'schema':'neural063_runtime_storage_admission_v1','root':str(ctx.store.root),'device':ctx.store.root.stat().st_dev,'actual_capacity_bytes':capacity,'actual_available_bytes':available,'reserved_additional_bytes':storage['additional_retained_bytes'],'scratch_peak_bytes':storage['scratch_peak_bytes'],'observation':storage['observation'],'observed_ns':time.time_ns(),'physical_future_fit':'not inferred; each write remains bounded and failure preserved'})
 assets=prepare_assets(ctx,p);assets_ref=output(ctx,'runtime_assets',assets)
 train={v:training(ctx,v) for v in ('T','N')};sd=scale(ctx);refs=selected_models(ctx);conditions={};artifacts={'runtime_assets':assets_ref,'runtime_storage_admission':storage_ref};failed=[]
 for condition in CONDITIONS:
  mode,view,tools=condition.split('-');fit,validation=train[view]
  identity='development-'+condition;ctl=Controller(ctx,p,identity,'development',condition,assets,fit,validation,sd,reference=refs[view] if tools=='R' else None)
  error=None;program_ref=None;explanation=None
  try:
   prompt=recipe['shared_prompt']+'\nCondition: '+condition+'\nProgram schema: '+canonical(recipe['initial_program_contract']).decode()+'\nComplete FIT/validation row counts: '+str(len(fit))+'/'+str(len(validation))+'. FIT targets are numerical-tool data; validation targets stay in the trusted aggregate selection evaluator.'
   program,explanation=ctl.investigate(prompt,development=True)
   program_ref=output(ctx,identity+'_program',program,'candidate_program',visibility='development')
  except BaseException as exc:error=failure(exc);failed.append(condition)
  receipt,transcript=retain_controller(ctx,ctl,'failed' if error else 'complete',error=error)
  conditions[condition]={'status':'failed' if error else 'complete','program':program_ref.object() if program_ref else None,'explanation':explanation,'controller_receipt':receipt.object(),'transcript':transcript.object(),'training':{'fit':ctx.inputs['fit_'+view].object(),'validation':ctx.inputs['validation_'+view].object()},'failure':error}
  artifacts[identity+'_controller']=receipt;artifacts[identity+'_transcript']=transcript
  if program_ref:artifacts[identity+'_program']=program_ref
 bundle={'schema':'neural063_development_bundle_v1','attempt':ctx.attempt,'profile_sha256':digest(p),'runtime_assets_sha256':assets_ref.sha256,'recipe_sha256':ctx.inputs['candidate_development_recipe'].sha256,'conditions':conditions,'seed':632026,'query_accessed':False,'failed_conditions':failed}
 artifacts['development_bundle']=output(ctx,'development_bundle',bundle)
 return StageResult('failed' if failed else 'complete',artifacts,{'development_jobs':8,'failed_conditions':failed},failed)

def D01(ctx):
 p=runtime_profile(ctx);bundle=read(ctx,'development_bundle');assets=read(ctx,'runtime_assets',4_000_000);equivalence=read(ctx,'query_equivalence',4_000_000)
 if bundle.get('schema')!='neural063_development_bundle_v1' or set(bundle.get('conditions',{}))!=set(CONDITIONS) or bundle.get('profile_sha256')!=digest(p) or bundle.get('runtime_assets_sha256')!=ctx.inputs['runtime_assets'].sha256 or assets.get('profile_sha256')!=digest(p):raise ContractError('complete matched eight-condition development freeze required')
 if equivalence.get('status')!='equivalent':raise ContractError('independent actual query reference equivalence required')
 audits={};budgets={}
 for condition in CONDITIONS:
  record=bundle['conditions'][condition]
  if record['status']!='complete':raise ContractError('incomplete development prevents query')
  program=read_ref(ctx,record['program'],'candidate_program');receipt=read_ref(ctx,record['controller_receipt'],'controller_receipt');transcript=read_ref(ctx,record['transcript'],'controller_transcript')
  mode,view,tools=condition.split('-')
  if receipt['status']!='complete' or receipt['checkpoint_sha256']!=assets['checkpoint_sha256'] or receipt['profile_sha256']!=digest(p) or receipt['condition']!=condition:raise ContractError('actual development receipt/checkpoint mismatch')
  if mode=='F':audit=fixed_graph(program,view,tools)
  else:
   exact(program,{'schema','mode','view','tools','system_prompt','artifacts'},'I library')
   if (program['schema'],program['mode'],program['view'],program['tools'])!=('neural063_investigation_library_v1','I',view,tools):raise ContractError('I library identity mismatch')
   audit={'source_sha256':digest(program),'mode':'event-local investigator from sealed library'}
  # The language runtime permits no imports/files/processes/checkpoint access.
  # Every model action/numerical/validation request is captured for independent
  # scientific scrutiny of fitting and selection; there is no asserted audit pass.
  audits[condition]={'program':record['program'],'source_audit':audit,'controller_receipt':record['controller_receipt'],'transcript':record['transcript'],'actual_development_actions':len(transcript['events']),'fit_target_access':'numerical data only','validation_target_access':'trusted aggregate selection evaluator only','query_graph_rule':'sealed fixed slots' if mode=='F' else 'fresh bounded per-event actions'}
  budgets[condition]=receipt['budget']
 if any(x!=next(iter(budgets.values())) for x in budgets.values()):raise ContractError('development resource allocations differ between conditions')
 actual=reconcile(ctx.store.root,p,ctx.attempt,'D00',ctx.store.meter,stop=False)
 value={'schema':'neural063_development_admission_v1','attempt':ctx.attempt,'profile_sha256':digest(p),'development_bundle_sha256':ctx.inputs['development_bundle'].sha256,'runtime_assets_sha256':ctx.inputs['runtime_assets'].sha256,'audits':audits,'actual_closed_development':actual,'reference_query_equivalence_sha256':ctx.inputs['query_equivalence'].sha256}
 out=output(ctx,'development_admission',value)
 return StageResult('complete',{'development_admission':out},{'independently_reconstructed_graphs':4,'sealed_I_libraries':4})

def Q00(ctx):
 p=runtime_profile(ctx);admission=read(ctx,'development_admission');bundle=read(ctx,'development_bundle');assets=read(ctx,'runtime_assets',4_000_000);index=read(ctx,'query_index',100_000_000)
 if admission['development_bundle_sha256']!=ctx.inputs['development_bundle'].sha256 or admission['runtime_assets_sha256']!=ctx.inputs['runtime_assets'].sha256 or admission['profile_sha256']!=digest(p):raise ContractError('query dispatcher admission bindings changed')
 q={v:rows(read(ctx,'query_'+v),v,'query') for v in ('T','N')}
 ids=[r['id'] for r in q['T']]
 if ids!=index['ids'] or ids!=[r['id'] for r in q['N']]:raise ContractError('all eight conditions must share the exact complete query schedule')
 for t,n in zip(q['T'],q['N']):
  if t!={k:v for k,v in n.items() if k!='history'}:raise ContractError('T/N context/timing/schedule differs beyond assigned history field')
 full_allocation(p,len(ids));mice=sorted({x['mouse'] for x in q['T']});cases=[]
 for condition in CONDITIONS:
  view=condition.split('-')[1]
  for mouse in mice:
   events=[r for r in q[view] if r['mouse']==mouse]
   cases.append({'condition':condition,'mouse':mouse,'event_ids':[r['id'] for r in events],'program':bundle['conditions'][condition]['program'],'case_id':digest({'condition':condition,'mouse':mouse})})
 if len(cases)!=152:raise ContractError('all eight by19 complete mouse cases required')
 value={'schema':'neural063_case_plan_v1','attempt':ctx.attempt,'profile_sha256':digest(p),'query_index_sha256':ctx.inputs['query_index'].sha256,'runtime_assets_sha256':ctx.inputs['runtime_assets'].sha256,'development_bundle_sha256':ctx.inputs['development_bundle'].sha256,'cases':cases,'query_rows':q,'events_per_condition':len(ids),'capsules':8*len(ids),'private_dispatch_only':True}
 out=output(ctx,'case_plan',value)
 return StageResult('complete',{'case_plan':out},{'mouse_cases':152,'event_controllers':8*len(ids)})

def Q01(ctx):
 p=runtime_profile(ctx);plan=read(ctx,'case_plan');bundle=read(ctx,'development_bundle');assets=read(ctx,'runtime_assets',4_000_000);train={v:training(ctx,v) for v in ('T','N')};sd=scale(ctx);refs=selected_models(ctx)
 if plan['profile_sha256']!=digest(p) or plan['development_bundle_sha256']!=ctx.inputs['development_bundle'].sha256 or plan['runtime_assets_sha256']!=ctx.inputs['runtime_assets'].sha256:raise ContractError('fresh event dispatch freeze changed')
 programs={c:read_ref(ctx,bundle['conditions'][c]['program'],'candidate_program') for c in CONDITIONS}
 byview={v:{r['id']:r for r in plan['query_rows'][v]} for v in ('T','N')};records=[];failed=[];artifacts={}
 for case in plan['cases']:
  condition=case['condition'];mode,view,tools=condition.split('-');fit,validation=train[view]
  for event_id in case['event_ids']:
   event=byview[view][event_id]
   if event['mouse']!=case['mouse']:raise ContractError('query mouse/row mismatch')
   identity='event-'+digest({'condition':condition,'id':event_id})
   ctl=Controller(ctx,p,identity,'event',condition,assets,fit,validation,sd,event=event,reference=refs[view] if tools=='R' else None);program=programs[condition];error=None;pred=None
   try:
    if mode=='F':pred,explanation=ctl.fixed(program)
    else:
     ctl.load_artifacts(program['artifacts'])
     pred,explanation=ctl.investigate(program['system_prompt']+'\nCurrent sole event: '+canonical(event).decode())
    pred=ctl.capsule('event_output',{'event':event,'prediction':pred},trusted_capture=True)
   except BaseException as exc:error=failure(exc);failed.append(identity)
   receipt,transcript=retain_controller(ctx,ctl,'failed' if error else 'complete',error=error)
   records.append({'controller':identity,'condition':condition,'mouse':case['mouse'],'id':event_id,'status':'failed' if error else 'complete','prediction':pred,'controller_receipt':receipt.object(),'transcript':transcript.object(),'failure':error})
   artifacts[identity+'_controller']=receipt;artifacts[identity+'_transcript']=transcript
 if len(records)!=plan['capsules']:raise ContractError('full same-schedule event roster did not complete dispatch')
 value={'schema':'neural063_event_runs_v1','attempt':ctx.attempt,'case_plan_sha256':ctx.inputs['case_plan'].sha256,'profile_sha256':digest(p),'records':records,'failed_controllers':failed,'query_targets_accessed':False}
 artifacts['event_runs']=output(ctx,'event_runs',value)
 return StageResult('failed' if failed else 'complete',artifacts,{'event_controllers':len(records),'failed_controllers':len(failed)},failed)

def Q02(ctx):
 p=runtime_profile(ctx);runs=read(ctx,'event_runs');plan=read(ctx,'case_plan');index=read(ctx,'query_index',100_000_000)
 if runs['case_plan_sha256']!=ctx.inputs['case_plan'].sha256 or plan['query_index_sha256']!=ctx.inputs['query_index'].sha256 or runs['profile_sha256']!=digest(p):raise ContractError('collector input bindings changed')
 lookup={}
 for r in runs['records']:
  key=(r['condition'],r['id'])
  if key in lookup or r['status']!='complete':raise ContractError('missing/failed/duplicate event blocks complete mouse capture')
  prediction(r['prediction'],r['id']);lookup[key]=r
 actual=reconcile(ctx.store.root,p,ctx.attempt,'Q01',ctx.store.meter,stop=False)
 cases=[]
 for case in plan['cases']:
  records=[lookup[(case['condition'],i)] for i in case['event_ids']]
  if any(r['mouse']!=case['mouse'] for r in records):raise ContractError('mouse hierarchy changed in collector')
  for r in records:
   receipt=read_ref(ctx,r['controller_receipt'],'controller_receipt')
   if receipt['status']!='complete' or receipt['event_id']!=r['id'] or receipt['condition']!=r['condition']:raise ContractError('sealed event receipt mismatch')
  cases.append({'case_id':case['case_id'],'condition':case['condition'],'mouse':case['mouse'],'predictions':[r['prediction'] for r in records],'controller_receipts':[r['controller_receipt'] for r in records],'transcripts':[r['transcript'] for r in records]})
 if len(lookup)!=8*len(index['ids']) or len(cases)!=152:raise ContractError('all complete original event/mouse outputs required')
 value={'schema':'neural063_mouse_predictions_v1','attempt':ctx.attempt,'query_index_sha256':ctx.inputs['query_index'].sha256,'case_plan_sha256':ctx.inputs['case_plan'].sha256,'event_runs_sha256':ctx.inputs['event_runs'].sha256,'cases':cases,'actual_writer_closure':actual}
 out=output(ctx,'mouse_predictions',value)
 return StageResult('complete',{'mouse_predictions':out},{'complete_mouse_cases':152})

def Q03(ctx):
 p=runtime_profile(ctx);mice=read(ctx,'mouse_predictions');plan=read(ctx,'case_plan');index=read(ctx,'query_index',100_000_000);conditions={}
 if mice['case_plan_sha256']!=ctx.inputs['case_plan'].sha256 or mice['query_index_sha256']!=ctx.inputs['query_index'].sha256:raise ContractError('whole-arm admission source binding changed')
 for condition in CONDITIONS:
  cases=[c for c in mice['cases'] if c['condition']==condition]
  if len(cases)!=19 or len({c['mouse'] for c in cases})!=19:raise ContractError('all19 complete query mice required per arm')
  values=sorted([r for c in cases for r in c['predictions']],key=lambda r:r['id']);admit_predictions(values,index['ids']);conditions[condition]=values
 actual=reconcile(ctx.store.root,p,ctx.attempt,None,ctx.store.meter,stop=False)
 pred={'schema':'neural063_candidate_predictions_v2','query_index_sha256':ctx.inputs['query_index'].sha256,'fit_scale_sha256':ctx.inputs['fit_scale'].sha256,'conditions':conditions}
 pref=output(ctx,'candidate_predictions',pred)
 cap={'schema':'neural063_prediction_capture_v1','attempt':ctx.attempt,'profile_sha256':digest(p),'candidate_predictions_sha256':pref.sha256,'candidate_predictions':pref.object(),'query_index_sha256':ctx.inputs['query_index'].sha256,'mouse_predictions_sha256':ctx.inputs['mouse_predictions'].sha256,'conditions':list(CONDITIONS),'all_event_count':8*len(index['ids']),'actual_writer_closure':actual,'captured_ns':time.time_ns()}
 cref=output(ctx,'prediction_capture',cap)
 return StageResult('complete',{'candidate_predictions':pref,'prediction_capture':cref},{'complete_arms':8,'mice_per_arm':19})

def N00(ctx):
 p=runtime_profile(ctx);pred=read(ctx,'candidate_predictions');capture_bundle=read(ctx,'prediction_capture');runs=read(ctx,'event_runs');development=read(ctx,'development_bundle');oldassets=read(ctx,'runtime_assets',4_000_000);assets=prepare_assets(ctx,p);recipe=read(ctx,'report_recipe',4_000_000)
 exact(recipe,{'schema','prompt','required_topics','seed'},'shared reporting recipe')
 topics={'estimand','method_features','uncertainty_limits','alternatives','executable_evidence','no_causal_or_online_claim'}
 if recipe['schema']!='neural063_report_recipe_v1' or set(recipe['required_topics'])!=topics or recipe['seed']!=632026:raise ContractError('all eight jobs require the same fixed scientific reporting recipe')
 if assets!=oldassets or capture_bundle['candidate_predictions_sha256']!=ctx.inputs['candidate_predictions'].sha256:raise ContractError('report model/runtime or immutable prediction capture changed')
 reports={};artifacts={}
 for condition in CONDITIONS:
  identity='report-'+condition;ctl=Controller(ctx,p,identity,'report',condition,assets,[],[],1.0)
  own=[r for r in runs['records'] if r['condition']==condition]
  # Each report identity gets only its own immutable material. Prediction APIs,
  # training tables, target bindings, other arms and scores are absent.
  transcript_values=[read_ref(ctx,r['transcript'],'controller_transcript') for r in own]
  dev=read_ref(ctx,development['conditions'][condition]['transcript'],'controller_transcript')
  ctl.workspace={'own_predictions':pred['conditions'][condition],'own_training_transcript':dev,'own_event_transcripts':transcript_values}
  error=None;narrative=None
  try:
   conversation=[recipe['prompt'],'Required topics: '+','.join(sorted(topics)),'Return exactly JSON actions numeric {code,result_key}, inspect {key}, or finish {narrative:{each required topic:string},evidence:[own workspace keys]}. This is a separate post-capture report: no prediction invocation/mutation and no query labels/scores/sibling material. Available own immutable material: '+canonical({k:summary(v) for k,v in ctl.workspace.items()}).decode()]
   while True:
    action=decode(ctl.model('\n'.join(conversation)).encode());ctl.events.append({'operation':'report_action','action':action})
    if action.get('action')=='finish':
     exact(action,{'action','narrative','evidence'},'report finish')
     if set(action['narrative'])!=topics or any(not isinstance(v,str) or not v.strip() for v in action['narrative'].values()) or not isinstance(action['evidence'],list) or any(k not in ctl.workspace for k in action['evidence']):raise ContractError('complete grounded narrative topics/evidence required')
     value={'schema':'neural063_candidate_narrative_v1','condition':condition,'topics':action['narrative'],'evidence':{k:digest(ctl.workspace[k]) for k in action['evidence']},'candidate_predictions_sha256':ctx.inputs['candidate_predictions'].sha256,'recipe_sha256':ctx.inputs['report_recipe'].sha256,'checkpoint_sha256':assets['checkpoint_sha256']}
     narrative=output(ctx,identity+'_narrative',value,'candidate_narrative',visibility='report');break
    if action.get('action')=='numeric':
     exact(action,{'action','code','result_key'},'report numeric action')
     if action['result_key'] in ctl.workspace:raise ContractError('report workspace overwrite denied')
     ctl.workspace[action['result_key']]=ctl.numeric(action['code']);ctl.bind_workspace_source(action['result_key']);answer=summary(ctl.workspace[action['result_key']])
    elif action.get('action')=='inspect':
     from .controller import inspect_value
     exact(action,{'action','key'},'report inspect action');ctl.usage['tool_calls']+=1;ctl.remaining();answer=inspect_value(ctl.workspace[action['key']])
    else:raise ContractError('report cannot invoke candidate/reference/validation APIs')
    conversation.append('Action: '+canonical(action).decode()+'\nResult: '+canonical(answer).decode())
  except BaseException as exc:error=failure(exc)
  receipt,transcript=retain_controller(ctx,ctl,'failed' if error else 'complete',error=error)
  reports[condition]={'status':'failed' if error else 'complete','controller_receipt':receipt.object(),'transcript':transcript.object(),'narrative':narrative.object() if narrative else None,'failure':error}
  artifacts[identity+'_controller']=receipt;artifacts[identity+'_transcript']=transcript
  if narrative:artifacts[identity+'_narrative']=narrative
 terminal={'schema':'neural063_narrative_receipts_v1','attempt':ctx.attempt,'prediction_capture_sha256':ctx.inputs['prediction_capture'].sha256,'profile_sha256':digest(p),'reports':reports,'jobs':8,'recipe_sha256':ctx.inputs['report_recipe'].sha256}
 nref=output(ctx,'narrative_receipts',terminal);artifacts['narrative_receipts']=nref
 actual=reconcile(ctx.store.root,p,ctx.attempt,None,ctx.store.meter,stop=False)
 life={'schema':'neural063_lifecycle_custody_v1','attempt':ctx.attempt,'profile_sha256':digest(p),'prediction_capture_sha256':ctx.inputs['prediction_capture'].sha256,'narrative_receipts_sha256':nref.sha256,'registered_jobs':actual['registered_jobs'],'actual_reconciliation':actual,'targets_or_scores_accessed':False}
 artifacts['lifecycle_custody']=output(ctx,'lifecycle_custody',life)
 failed=[k for k,v in reports.items() if v['status']=='failed']
 return StageResult('complete_with_narrative_failures' if failed else 'complete',artifacts,{'mandatory_report_jobs':8,'failed_reports':failed},failed)

HANDLERS={k:globals()[k] for k in STAGES}
def run(stage,ctx):
 ctx.require_scientific()
 if stage not in HANDLERS or set(ctx.inputs)!=set(INPUTS[stage]):raise ContractError('exact full concrete runtime stage input set required')
 return HANDLERS[stage](ctx)
