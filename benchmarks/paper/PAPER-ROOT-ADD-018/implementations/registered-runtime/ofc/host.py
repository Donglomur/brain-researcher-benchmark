"""Submitted build/investigation/learning/prediction/analysis, never reference replay."""
from pathlib import Path
from . import contracts
from .common import require,Refusal,identity,load,write_new,copy_new,relative,seal_tree,verify_tree,now,make_dir,guard
from .supervisor import Supervisor
from .lifecycle import current,DeadlineExceeded,BudgetExceeded,UnresolvedContainment,error_record
from .universe import validate_query
from .collector import collect

def source_bundle(submission,destination,budget):
 destination=Path(destination);make_dir(destination);total=0
 for row in submission['files']:
  total+=row['bytes'];require(total<=budget['source_bytes'],'source budget');copy_new(Path(submission['source_root'])/relative(row['path']),destination/row['path'],row,budget['source_bytes'])
 seal=seal_tree(destination,budget['file_count'],budget['source_bytes']);return seal
def inputs_for(plan,phase,query_ids=None):
 """Select only operator-declared views. Targets/references are not input roles."""
 selected=[];lane=plan['condition'][0];arm=plan['condition'][-1]
 for item in plan['public_inputs']:
  required={'id','path','bytes','sha256','role','phases','family_ids','query_ids','arm','available_through'}
  require(set(item)==required,'public input schema');require(item['role']in('paper','training','validation','native_historical','author_code','query_projection'),'input exposure role')
  require(item['arm']in('A','B','both'),'input arm')
  if item['role']=='author_code':require(item['arm']=='B','author source only B')
  if item['role']=='native_historical':require(lane=='R','historical outcome in prospective plan')
  if phase not in item['phases']or item['arm']not in(arm,'both'):continue
  if item['role']=='author_code'and arm=='A':continue
  if phase=='predict':
   require(item['role']in('query_projection',),'only exact query projections may accompany prediction')
   qmap={q['query_id']:q for rs in plan['public_universes'].values()for q in rs};selected_queries=[qmap[k]for k in query_ids or []]
   allowed={i for q in selected_queries for i in q['public_input_ids']}
   if item['id']not in allowed:continue
   require(item['query_ids']and set(item['query_ids'])<=set(query_ids or []),'query projection support')
   require(set(item['family_ids'])=={q['family_id']for q in selected_queries},'projection family boundary')
   require(all((item['available_through']['trial_ordinal'],item['available_through']['bin_ordinal'])<=(q['cutoff']['trial_ordinal'],q['cutoff']['bin_ordinal'])for q in selected_queries),'projection future watermark')
  elif item['role']=='query_projection':continue
  selected.append(item)
 return selected
def run_condition(submission,plan,documents,execution,output,full_deadline,job_id):
 """Each condition gets fresh source/build/model/context and original receipts."""
 submission=contracts.submission(submission);plan=contracts.plan(plan,documents)
 require(set(submission['declared_obligations'])==set(plan['scope']['obligation_ids']),'participant omitted scope')
 root=Path(output);make_dir(root);b=plan['budget'];source_dir=root/'source';source=source_bundle(submission,source_dir,b)
 require(execution['mode']!='trusted_inert_engineering'or source['id']in execution['allowed_inert_source_ids'],'inert source approval')
 sup=Supervisor(root/'stages',b,execution,full_deadline,job_id);request_counter=0;outputs=[];build=None;model=None;modelseal=None;failure=None
 # A worker only sees the public contract, never the protected commitment/preimage.
 public_scope={'task_id':contracts.TASK,'condition':plan['condition'],'scope':plan['scope'],'policy_id':plan['policy_id'],'seed_manifest':plan['seed_manifest']}
 def invoke(phase,payload,stream=None,extras=None,dialogue=None):
  nonlocal request_counter
  request_counter+=1;sid='%05d-%s'%(request_counter,phase);base=root/'requests'/sid;make_dir(base)
  ids=[x['query_id']for x in payload.get('queries',[])]
  assetroot=base/'inputs';make_dir(assetroot);assets=inputs_for(plan,phase,ids);total=0
  for item in assets:
   relative(item['id']);total+=item['bytes'];require(total<=b['input_bytes'],'public input bytes');copy_new(item['path'],assetroot/item['id'],item,b['input_bytes'])
  # Private IDs/targets/masks/reference models never enter this request.
  req={'schema':'ofc-worker-request-v1','phase':phase,'source_id':source['id'],'model_id':None if modelseal is None else modelseal['id'],'public_contract':public_scope,'payload':payload,'input_ids':[x['id']for x in assets],'stream_id':stream}
  rid=identity(req);req['request_id']=rid;rq=base/'request';write_new(rq/'request.json',req)
  mounts={'source':source_dir,'request':rq,'inputs':assetroot}
  if build is not None:mounts['build']=build
  if model is not None:mounts['model']=model
  mounts.update(extras or {})
  # Prefix streams carry all permitted observation values inside each query;
  # no future projection assets are mounted for the whole stream.
  if dialogue is not None:require(all(not q['public_input_ids']for q in dialogue),'stream assets require inline bounded projections; no future asset pre-mount')
  result,obs=sup.run(sid,submission['entrypoints'][phase],mounts,rid,source['id'],dialogue=dialogue)
  return result,obs
 try:
  build,_=invoke('build',{'dependency_lock':submission['dependency_lock'],'dependency_environment':plan['dependency_environment']})
  investigation,_=invoke('investigate',{'allowed_feedback':'sealed validation view only; bounded once per submitted plan','native_requests':plan['native_requests']if plan['condition'][0]=='R'else[]})
  # Investigations are real submitted-source executions; their files are sealed
  # and supplied to fit as build artifacts, without any test/ref feedback.
  investigation_seal=seal_tree(investigation,b['file_count'],b['output_bytes'])
  model,_=invoke('fit',{'investigation_seal':investigation_seal,'native_requests':plan['native_requests']if plan['condition'][0]=='R'else[],'fixed_method_selection':submission['seed_policy']},extras={'investigation':investigation})
  modelseal=seal_tree(model,b['file_count'],b['output_bytes']);require(modelseal['files'],'fit must produce nonempty fitted state')
  if plan['condition'][0]=='R':outputs.append(invoke('analyze',{'native_requests':plan['native_requests']}))
  else:
   for family in (f for f in contracts.FAMILIES if f.startswith('I_')):
    streams={}
    for row in plan['public_universes'][family]:validate_query(row);streams.setdefault(row['stream_id'],[]).append(row)
    for stream,queries in sorted(streams.items()):
     require(queries==sorted(queries,key=lambda q:(q['cutoff']['trial_ordinal'],q['cutoff']['bin_ordinal'])),'noncausal query order')
     # One fresh process per target/session stream; only one prefix query is
     # sent at a time. Durable response commitment precedes the next query.
     outputs.append(invoke('predict',{'family_id':family,'protocol':'prefix_commit_v1'},stream,dialogue=queries))
  verify_tree(source_dir,source,b['file_count'],b['source_bytes']);verify_tree(model,modelseal,b['file_count'],b['output_bytes'])
 except BaseException as e:
  failure=error_record(e);original_failure=e
 chain={'campaign_id':current().campaign.id,'source_id':source['id'],'source_seal':source,'model_id':None if modelseal is None else modelseal['id'],'model_seal':modelseal,'submission_id':identity(submission),'plan_id':identity(plan),'stages':sup.attempts,'natural_complete':failure is None,'failure':failure,'original_attempt_terminal_custody_complete':all(a.get('terminal_custody_saved',False)for a in sup.attempts)}
 try:write_new(root/'EXECUTION_CHAIN.json',chain,closing=True)
 except BaseException as e:
  chain['publication_error']=error_record(e)
  if failure is not None:raise original_failure from e
  raise
 try:current().campaign.assert_terminal_custody()
 except BaseException as custody_error:
  if failure is not None:raise original_failure from custody_error
  raise
 current().protected('condition collector admission')
 if failure is not None and isinstance(original_failure,(DeadlineExceeded,BudgetExceeded,UnresolvedContainment)):raise original_failure
 # Collector completeness always materializes every missing row on failure.
 try:record,pin=collect(plan,outputs,chain,root/'closed')
 except (DeadlineExceeded,BudgetExceeded,UnresolvedContainment):raise
 except BaseException as e:
  chain={**chain,'natural_complete':False,'collector_exception':error_record(e)}
  write_new(root/'COLLECTION_FAILURE.json',chain['collector_exception']);current().protected('fallback collector admission');record,pin=collect(plan,[],chain,root/'failed-closed')
 current().protected('condition return');return {'condition':plan['condition'],'sealed_submission':pin,'record':record,'execution_chain':chain}
