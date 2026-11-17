"""Source-owned complete stage controller; real execution requires current authority.

Predeclared jobs use typed artifact references, not guessed future hashes. Each
reference is resolved only from an original completed producer and then bound
into that exact invocation. No historic prediction or target-derived view can
enter a learner merely because it has the desired filename.
"""
from dataclasses import dataclass
import time
from .contracts import need,closed,canonical,digest,descriptor,parse,Custody,Budget,Store
from .programme import programme,planned_support,expected_jobs,expected_groups,group_id,execution_plan_identity,bind_programme
from .evidence import Evidence
from .collection import Collector,barrier
from .openai_gateway import OpenAIExecutor as Executor,OpenAIProcessModel as ProcessModel
from .investigation import Tools,investigate,prepare

@dataclass(frozen=True)
class Artifact:
 pin:dict
 stage:str
 role:str
 producer:str
 condition:object=None
 group:object=None

class ToolGateway:
 """Translate genuine model-selected tools into complete real worker requests."""
 def __init__(self,campaign,context,condition,gid):
  self.campaign=campaign;self.context=context;self.condition=condition;self.gid=gid;self.results={};self.authority=campaign.authority;self.store=campaign.store
 def invoke(self,job,stage,role,payload,budget):
  need(role=='participant_tool'and payload['context']==self.context['binding'],'same original case tool ancestry');a=payload['arguments'];tool=payload['tool']
  if tool=='run_python':
   body={'tool':tool,'source_utf8':a['source_utf8'],'source_sha256':a['source_sha256'],'output_kind':'state'if payload['case_index']is None else'prediction','input_request':{'schema':'NLB017_arbitrary_method_inputs_v1','training':payload['training'],'query':payload['query'],'state':payload['state'],'case_index':payload['case_index'],'context':payload['context'],'output_contract':'nonobject_numeric_state_archive'if payload['case_index']is None else'six_array_expected_spikes_per_bin'}}
  else:
   need(tool=='reference_predict'and payload['query']==self.context['query'],'same original reference query')
   from .f_service import reference_body,reference_slot
   body,bank,bank_identity=reference_body(self.campaign,self.context,self.condition,self.gid,a['reference'],a['state'],payload['case_index'],budget)
   paired=self.campaign.executor.reference_services.get(self.gid.replace('/I-','/F-')+'/programme')
   need(paired is not None and paired.bank==bank_identity,'same original paired F/I bank')
   reference_slot(self.campaign,job,bank,a['reference'])
  kind='state'if tool=='run_python'and payload['case_index']is None else'prediction'
  outputs={kind:{'name':'tool/'+job,'role':'source_state'if kind=='state'else'prediction'}}
  if tool=='run_python':outputs['actual_source']={'name':'tool/'+job+'/actual_source','role':'source'}
  o,result=self.campaign.native(job,stage,'participant_tool',body,outputs,condition=self.condition,gid=self.gid)
  if result is not None and tool=='run_python':need(result['products']['actual_source']['sha256']==a['source_sha256']and result['products']['actual_source']['bytes']==len(a['source_utf8'].encode()),'retained generated source equals original model-emitted bytes')
  self.results[job]=result;return o
 def product(self,observation):
  need(observation.custody.complete and self.results[observation.job]is not None,'real tool completion');return self.results[observation.job]

def allowed_role(stage,role):
 if role in('assessment_target','private_ledger','private_draws'):return stage in('S02','S03','S13','S14')
 if role=='protected_shuffle_seed':return stage in('S04','S03')
 if role=='raw_asset':return stage=='S02'
 if role=='licensed_primary':return stage in('S01','S04','S07','S08','S09')
 if role=='curated_code_B':return stage in('S01','S04','S07','S08','S09')
 if role=='aggregate':return stage in('S15','S16')
 return role in('source','planned_support','public_training','public_query','source_state','prediction','metadata','development','qualification','prior_terminal')

def matched_model_service(spec,participant_groups):
 m=spec['model'];same={'identity':m['model_identity'],'configuration':m['configuration'],'prompt':m['prompt'],'tokenizer':m['tokenizer'],'qualification':m['service_qualification']}
 for g in expected_groups():
  if g['mode']=='I':need(participant_groups[group_id(g)]['model_service']==same,'all I groups use the exact same model/configuration as original F authoring')
 return same

class Campaign:
 def __init__(self,authority,source_sha,spec,design,selection,store):
  self.authority=authority;self.source=source_sha;self.spec=spec;self.selection=selection;self.store=store;self.store.budget.authority=authority;self.custody=Custody('campaign');self.originals={};self.artifacts={};self.group_budgets={};self.actor_originals={}
  self.identity=programme(spec,design['roster'],design['contrasts']);need(self.identity==selection['programme_sha256'],'current selection names exact pre-exposure programme');need(spec['execution_plan_sha256']==execution_plan_identity(selection),'entire pre-exposure code/prompt/recipe/runtime plan')
  # Admit/pack the complete factored operand table before recursive binding.
  # This avoids a second parsed descriptor graph; original Store raw-read
  # custody remains retained and must be included in deployment sizing.
  native=selection['native_jobs']
  if type(native)is dict and native.get('schema')=='NLB017_factored_native_jobs_v1':
   from .factored_runtime import FactoredRuntime
   selection['native_jobs']=FactoredRuntime.from_selected(store,native);del native
  selection=bind_programme(selection,self.identity);self.selection=selection
  self.planned=planned_support(store.json(spec['planned_support']));self.support=None
  self.evidence=Evidence(authority,self.identity,source_sha,design['dag'],design['lineage'],design['gates'],store,selection['checkpoint_reviews'])
  self.executor=Executor(authority,store,source_sha,selection['native_jobs']);self.jobs=expected_jobs(spec);self.design=design
  need(selection['reference_limits']['cpu_seconds']<=720000 and selection['reference_limits']['model_tokens']==0,'separate finite expert construction budget');self.reference_budget=Budget(selection['reference_limits'],min(selection['reference_original_deadline'],store.budget.deadline),parent=store.budget,custody=self.custody);self.external_reference_costs=set()
  need(set(selection['participant_groups'])=={group_id(g)for g in expected_groups()},'all 100 group configurations')
  matched_model_service(spec,selection['participant_groups'])
  need(selection['original_deadline']==store.budget.deadline,'original deadline not renewed')
  for row in selection['initial_artifacts']:
   closed(row,{'name','pin','role','producer'});need(row['role']in('source','planned_support','qualification','metadata','protected_shuffle_seed','raw_asset','licensed_primary','curated_code_B'),'initial artifact capability');need(row['pin']in list(authority.input_pins),'selected initial artifact');self.artifacts[row['name']]=Artifact(row['pin'],'P02',row['role'],row['producer'])
  self.collector=None;self.pending_report=None;self.f_authoring_joins={};self.f_authoring_consumed=set();self.f_authoring_custodies={}
 def group_budget(self,gid):
  if gid not in self.group_budgets:
   s=self.selection['participant_groups'][gid];limits=s['limits'];need(limits['cpu_seconds']<=14400 and limits['model_tokens']<=2097152,'matched finite cumulative allowance')
   peer=gid.replace('/F-','/I-')if '/F-'in gid else gid.replace('/I-','/F-');need(s['limits']==self.selection['participant_groups'][peer]['limits'],'F/I exact matched resources')
   started=time.monotonic()
   if '/F-'in gid:
    from .contracts import finite
    started=s['authoring_original_started'];finite(started);need(0<started<=time.monotonic()and s['original_deadline']<=started+172800,'original F authoring clock, never a fresh execution clock')
   self.group_budgets[gid]=Budget(limits,min(started+172800,s['original_deadline'],self.store.budget.deadline),parent=self.store.budget,custody=self.custody);self.group_budgets[gid].original_started=started
  return self.group_budgets[gid]
 def admit_f_authoring(self):
  """Concrete exact original source/usage consumer before the S04 data freeze."""
  from .authoring import consume
  need(self.evidence.active=='S01'and 'S02'not in self.evidence.done and not self.f_authoring_joins,'one pre-exposure full F authoring admission')
  actions={a['job']:a for a in self.selection['stages']['S07']['jobs']}
  for g in expected_groups():
   if g['mode']!='F':continue
   gid=group_id(g);s=self.selection['participant_groups'][gid];job=gid+'/programme';need(job in actions and actions[job]['role']=='participant_F','original full F action')
   ref=actions[job]['body']['submitted_source'];closed(ref,{'artifact'});a=self.artifacts[ref['artifact']]
   need(a.role=='source'and a.stage=='P02','captured source already selected before empirical exposure')
   budget=self.group_budget(gid);reader=Store(self.store.root,budget,Custody('F_authoring:'+gid));self.f_authoring_custodies[gid]=reader.custody
   m=self.spec['model'];expected={'group':gid,'seed':g['agent_seed'],'code_view':g['code_view'],'public_context':self.spec['code_views'][g['code_view']],'captured_source':a.pin,'root_source':self.source,'model':m['model_identity'],'configuration':m['configuration'],'prompt':m['prompt'],'tokenizer':m['tokenizer'],'runtime':m['runtime'],'service_qualification':m['service_qualification'],'original_started':s['authoring_original_started'],'original_deadline':s['original_deadline'],'monotonic_domain':s['authoring_clock_domain']}
   try:self.f_authoring_joins[gid]=consume(reader,self.authority,s['authoring'],expected,budget,self.f_authoring_consumed)
   finally:self.custody.facts.setdefault('F_authoring_original_custody',{})[gid]=reader.custody.snapshot()
  need(len(self.f_authoring_joins)==50,'all original fifty F authors before programme freeze')
  pin=self.store.write('evidence/F_AUTHORING.json',canonical({'schema':'NLB017_full_F_authoring_admission_v1','programme':self.identity,'all50_original_joins':self.f_authoring_joins,'pre_empirical':True}),64*2**20)
  self.artifacts['f_authoring']=Artifact(pin,'S01','metadata','exact_original_external_F_authors')
 def admit_operator_evidence(self,new_authority,checkpoint,pin):
  """Trusted operator control channel only, never a participant/model tool.

  Late exact independent review pins may be admitted after their actual
  producers exist. This does not replace sources, outcomes, recipes, budgets,
  the original clock, or consumed attempts.
  """
  need(new_authority.campaign==self.authority.campaign and new_authority.root_source==self.source,'same frozen campaign/source')
  need(new_authority.expires_at<=self.authority.expires_at,'no authorization time renewal');need(set(new_authority.stages)<=set(self.authority.stages)and set(new_authority.native_roles)<=set(self.authority.native_roles),'no role escalation')
  need(pin in list(new_authority.input_pins),'new exact independent evidence selected');self.store.read(pin,16*2**20)
  self.authority=new_authority;self.store.budget.authority=new_authority;self.evidence.authority=new_authority;self.executor.authority=new_authority
  if checkpoint in self.evidence.checkpoints:self.evidence.selected_reviews[checkpoint]=pin
  else:
   need(checkpoint in('E07','E09','E10'),'only typed native qualification products');self.selection['stages']['S05']['evidence'][checkpoint]={'qualification':{'report':pin}}
 def initialize_preconditions(self):
  for key in('E01','E02','E03'):self.evidence.external(key,self.selection['preconditions'][key])
 def resolve(self,value,stage,condition=None,gid=None):
  if type(value)is dict and set(value)=={'artifact_sha256'}:
   name=value['artifact_sha256'];need(type(name)is str and bool(name),'exact artifact hash reference')
   pin=self.resolve({'artifact':name},stage,condition,gid);descriptor(pin)
   return pin['sha256']
  if type(value)is dict and set(value)=={'artifact'}:
   name=value['artifact'];need(name in self.artifacts,'unproduced artifact');a=self.artifacts[name];need(allowed_role(stage,a.role),'forbidden information lineage')
   if a.role=='curated_code_B'and gid is not None:need(gid.split('/')[1].endswith('-B'),'paper-only arm cannot read code-view B')
   if a.group is not None:need(a.group==gid,'no cross-arm/case answer reuse')
   if a.condition is not None:need(a.condition==condition,'no intact source/query state in shuffled or restricted view')
   reader=self.store if gid is None else Store(self.store.root,self.group_budget(gid),self.custody);reader.read(a.pin,1024*2**20);return a.pin
  if type(value)is dict:return{k:self.resolve(v,stage,condition,gid)for k,v in value.items()}
  if type(value)is list:return[self.resolve(v,stage,condition,gid)for v in value]
  return value
 def native(self,job,stage,role,body,outputs,*,condition=None,gid=None):
  self.authority.check(stage,role);budget=self.group_budget(gid)if gid else self.reference_budget if role in('reference_train','reference_development','reference_predict','tool_only')else self.store.budget;payload=self.resolve(body,stage,condition,gid)
  if role=='participant_F':
   need(stage=='S07'and gid in self.f_authoring_joins and payload['submitted_source']==self.f_authoring_joins[gid]['captured_source'],'actual F execution consumes already joined original authoring')
   from .f_service import FrozenReferenceService
   selected_service=self.selection['participant_groups'][gid]['reference_service'];closed(selected_service,{'context','slots','io_reserve'})
   context=self.resolve(selected_service['context'],stage,condition,gid)
   service=FrozenReferenceService(self,context,condition,gid,job,payload['submitted_source'],selected_service['slots'],selected_service['io_reserve'])
   self.executor.bind_reference_service(job,service)
   need('reference_service'not in payload,'public service binding is source-owned')
   payload={**payload,'reference_service':service.public}
  if role=='participant_tool':
   need(gid is not None and gid.split('/')[1]in('F-A','F-B','I-A','I-B'),'exact tool owner')
   if '/F-'in gid:need(stage=='S07'and payload['tool']=='reference_predict'and self.executor.service_owns_slot(gid,job),'only original live F service may invoke its selected slot')
   else:need(stage in('S08','S09'),'original I actor stage')
   self.executor.select_tool_variant(job,payload['tool'],'participant_'+gid.split('/')[1][-1])
  from .native_selection import worker_context
  s=worker_context(self.selection['worker_contexts'],job,self.executor.selected);closed(s,{'input_root','output_root','authority','declared_inputs','bindings'})
  inputs=self.resolve(s['declared_inputs'],stage,condition,gid)
  concrete=self.executor.selected[job]
  if 'dynamic_input_policy'in concrete:
   policy=concrete['dynamic_input_policy'];closed(policy,{'schema','max_files','max_bytes','manifest_path'});need(policy['schema']=='NLB017_exact_current_input_leaves_v1','closed dynamic input derivation')
   pins={}
   def gather(x):
    if type(x)is dict and set(x)=={'path','bytes','sha256'}:descriptor(x);need(x['path']not in pins or pins[x['path']]==x,'input path identity conflict');pins[x['path']]=x
    elif type(x)is dict:
     for v in x.values():gather(v)
    elif type(x)is list:
     for v in x:gather(v)
   gather(payload);gather(inputs);gather(s['authority']);need(len(pins)<=policy['max_files']and sum(p['bytes']for p in pins.values())<=policy['max_bytes'],'complete finite physical input set')
   rows=[]
   for pin in pins.values():
    if pin==s['authority']:kind='operator_control';producer='current_operator'
    else:
     matches=[a for a in self.artifacts.values()if a.pin==pin];need(matches,'input must originate in current exact artifact census');a=matches[0];need(allowed_role(stage,a.role)and(a.group is None or a.group==gid)and(a.condition is None or a.condition==condition),'current same-view input ancestry');kind=a.role;producer=a.producer
     if kind=='curated_code_B'and gid is not None:need(gid.split('/')[1].endswith('-B'),'A cannot mount B code')
    rows.append({'source':pin,'role':kind,'producer':producer})
   reader=Store(self.store.root,budget,self.custody);manifest=reader.write(policy['manifest_path'],canonical({'schema':'NLB017_input_mount_set_v1','programme':self.identity,'job':job,'files':sorted(rows,key=lambda r:r['source']['path'])}),8*2**20)
   concrete['input_manifests']=[*concrete['input_manifests'],manifest]
   for row in rows:concrete['sandbox']['mounts'].append({'host':str(self.store.path(row['source']['path'])),'guest':'/inputs/'+row['source']['path'],'access':'ro','role':row['role'],'manifest':manifest,'member':row['source']['path']})
   inputs=list(pins.values())
  request={'schema':'NLB017_worker_request_v2','job':job,'source':concrete['source'],'role':role,'stage':stage,'body':payload,'declared_inputs':inputs,'input_root':s['input_root'],'output_root':s['output_root'],'deadline':budget.deadline,'authority':s['authority'],'expected_root_source':self.source,'bindings':{**s['bindings'],'programme':self.identity,'job':job,'role':role,'source':concrete['source'],'inputs':concrete['input_manifests']}}
  try:o=self.executor.invoke(job,stage,role,request,budget)
  finally:
   if job in self.executor.originals:self.originals[job]=self.executor.originals[job]
  if not o.custody.complete:return o,None
  result=self.executor.product(o);need(set(outputs)<=set(result['products']),'required actual product census')
  for key,row in outputs.items():
   closed(row,{'name','role'});need(row['name']not in self.artifacts,'immutable one-shot artifact');self.artifacts[row['name']]=Artifact(result['products'][key],stage,row['role'],job,condition,gid)
  return o,result
 def stage_jobs(self,stage):
  actions=self.selection['stages'][stage]['jobs'];seen=set()
  if stage=='S15':need(len(actions)==1 and actions[0]['role']=='aggregate_report','S15 worker produces only one complete aggregate projection')
  expected={k for k,v in self.jobs.items()if v['stage']==stage}
  if stage in('S05','S06','S07'):need({a['job']for a in actions}==expected,'complete exact stage job census')
  for a in actions:
   need(a['job']not in seen,'one invocation in stage');seen.add(a['job'])
   o,d=self.native(a['job'],stage,a['role'],a['body'],a['outputs'],condition=a.get('condition'),gid=a.get('group'))
   if a['job']in self.jobs and self.collector is not None:
    if d is None:self.collector.record_failure(a['job'],o)
    else:
     key=a['collection_product'];self.collector.add(a['job'],d['products'][key],o,d['bindings'])
   if d is None and not a['role'].startswith('participant'):raise o.custody.first_error
  return seen
 def issue(self,key,artifact_names):
  pins=[self.artifacts[n].pin for n in artifact_names]
  if key in('E06','E12'):
   need(len(self.f_authoring_joins)==50 and 'f_authoring'in self.artifacts,'full original F authoring evidence required')
   if self.artifacts['f_authoring'].pin not in pins:pins.append(self.artifacts['f_authoring'].pin)
  terminal=self.custody.snapshot();terminal['complete']=self.custody.first_error is None
  return self.evidence.product(key,pins,terminal)
 def verify_external_product(self,key,row):
  # This is a separately selected qualification report, never an arbitrary
  # caller-supplied passed flag. It must carry all actual original producers.
  pin=row['report'];need(pin in list(self.authority.input_pins),'current qualification report selection');doc=self.store.json(pin)
  need(doc['schema']=='NLB017_original_qualification_product_v1'and doc['programme']==self.identity and doc['source']==self.source and doc['product']==key,'qualification source/programme identity')
  need(doc['information_lineage']in('training_only','training_inner_development','training_resource_metadata'),'no assessment qualification shortcut')
  need(doc['producer_terminals']and not doc['unresolved'],'complete qualification observations')
  if key in('E09','E10'):
   from .operator_lifecycle import development_output_binding
   expected=development_output_binding(self);need(doc.get('current_stage_outputs')==expected,'qualification must bind exact original complete S05 outputs')
   need(all(row['process']in doc['producer_terminals']for row in expected.values()),'qualification retains every original training producer terminal')
  for p in doc['producer_terminals']:
   t=self.store.json(p);need(t['terminal']['complete']and t['terminal']['first_error']is None and t['exit_code']==0 and t['absence']is True and t['reaped']and all(t['stream_eof'].values()),'actual qualification producer')
   if p['sha256']not in self.external_reference_costs and p not in[o.persistence.get('process')for o in self.originals.values()]:
    need(t['costs']['cpu_seconds']is not None,'known original qualification CPU');self.reference_budget.charge('cpu_seconds',t['costs']['cpu_seconds']);self.external_reference_costs.add(p['sha256'])
  self.artifacts['qualification/'+key]=Artifact(pin,self.evidence.active,'qualification','independent_operator');return self.issue(key,['qualification/'+key])
 def advance(self,stage):
  self.evidence.enter(stage);self.custody.phase=stage
  try:
   if stage=='S01':
    for a in self.artifacts.values():
     if a.role in('source','planned_support','metadata'):self.store.read(a.pin,128*2**20)
    self.admit_f_authoring()
   elif stage=='S04':
    need('S02'not in self.evidence.done and len(self.f_authoring_joins)==50,'pre-activity source and original authoring commitment');self.store.write('programme/COMMIT.json',canonical(self.spec),16*2**20)
    # The private seed is read only by the privileged projection worker; this
    # public commitment carries its exact descriptor, never seed bytes.
    from .programme import SHUFFLE_RULE
    commit=self.store.json(self.spec['shuffle_commitment']);need(commit['schema']=='NLB017_target_free_shuffle_commitment_v2'and commit['planned_support_sha256']==digest(canonical(self.planned))and commit['rule']==SHUFFLE_RULE,'prospective exact rule and map identity')
   elif stage in('S02','S03','S05','S06','S07'):
    if stage=='S05'and self.collector is None:
     self.support=self.store.json(self.artifacts['prepared/support'].pin);self.collector=Collector(self.spec,self.identity,self.support,self.store,self.executor.selected)
    if stage=='S05':self.verify_external_product('E07',self.selection['stages']['S05']['evidence']['E07']['qualification'])
    self.stage_jobs(stage)
    if stage=='S05':
     from .operator_lifecycle import development_output_binding
     return {'status':'awaiting_original_development_qualifications','stage_remains_active':'S05','required_products':['E09','E10'],'current_stage_outputs':development_output_binding(self),'original_deadline':self.store.budget.deadline,'no_job_reentry':True}
   elif stage in('S08','S09'):self.actor_stage(stage)
   elif stage=='S10':
    need(self.executor.all_absent(),'all actual native producers absent');need(not self.collector.failures,'failed actors prevent global release')
   elif stage=='S11':
    pin=self.collector.complete_predictions(lambda p:self.store.read(p,32*2**20));self.artifacts['collection']=Artifact(pin,stage,'metadata','collector')
    from .operator_lifecycle import register_collection_predictions
    register_collection_predictions(self,pin)
   elif stage=='S12':
    pin=barrier(self.store,self.artifacts['collection'].pin,self.identity,self.jobs,self.authority);self.artifacts['release']=Artifact(pin,stage,'metadata','barrier')
   elif stage in('S13','S14'):
    self.evidence.target(stage);self.stage_jobs(stage)
   elif stage=='S15':
    from .operator_lifecycle import capture_actual_costs
    costs=capture_actual_costs(self);self.artifacts['actual_costs']=Artifact(costs,stage,'metadata','original_resource_ledgers')
    self.stage_jobs(stage);return self.start_report()
   elif stage=='S16':need(not self.collector.failures,'incomplete global disposition');self.stage_jobs(stage)
   else:raise ValueError('closed stage surface')
   return self.finish_stage(stage)
  except BaseException as e:self.custody.fail(e,stage);self.evidence.abort(e,self.custody);raise
 def resume_development(self):
  need(self.evidence.active=='S05'and self.evidence.failed is None,'only original pending S05 qualification pause')
  expected={k for k,v in self.jobs.items()if v['stage']=='S05'}
  need(expected<=set(self.collector.products)and not self.collector.failures,'complete actual original development producers')
  for key in('E09','E10'):
   pin=self.selection['stages']['S05']['evidence'][key]['qualification']['report'];descriptor(pin)
  try:return self.finish_stage('S05')
  except BaseException as error:self.custody.fail(error,'S05_qualification_completion');self.evidence.abort(error,self.custody);raise
 def finish_stage(self,stage):
  need(self.evidence.active==stage,'same original active stage')
  for product in self.design['dag_stages'][stage]['evidence_products']:
   if product in self.evidence.evidence:continue
   row=self.selection['stages'][stage]['evidence'][product]
   if 'qualification'in row:self.verify_external_product(product,row['qualification'])
   else:self.issue(product,row['artifacts'])
  terminal=self.custody.snapshot();terminal['complete']=True;self.evidence.leave(terminal)
  return self.store.write('stages/'+stage+'.json',canonical({'schema':'NLB017_stage_closure_v1','programme':self.identity,'stage':stage,'evidence':dict(self.evidence.evidence),'actual_originals':{k:dict(o.persistence)for k,o in self.originals.items()},'artifact_census':{k:a.__dict__ for k,a in self.artifacts.items()},'budget':self.store.budget.snapshot()}),512*2**20)
 def start_report(self):
  from .reporting import produce_report,rubric_contract
  need(self.evidence.active=='S15'and 'E14'in self.evidence.evidence and 'S14'in self.evidence.done and self.pending_report is None,'single report after complete protected assessment')
  s=self.selection['reporting'];closed(s,{'model_service','job','seed','max_tokens','limits','original_deadline','aggregate_artifact'})
  need(self.selection['stages']['S15']['evidence']=={'E17':{'artifacts':['report/text','report/judgment']}},'E17 requires actual report and judgment')
  artifact=self.artifacts[s['aggregate_artifact']];need(artifact.stage=='S15'and artifact.role=='aggregate','actual same-stage aggregate producer')
  rubric_contract(self.store.json(self.spec['rubric'],2**20))
  budget=Budget(s['limits'],min(s['original_deadline'],self.store.budget.deadline),parent=self.store.budget,custody=self.custody)
  model=ProcessModel(self.executor,**s['model_service']);report_store=Store(self.store.root,budget,Custody('postfreeze_report'))
  try:result=produce_report(model,report_store,artifact.pin,self.spec['rubric'],self.identity,s['job'],s['seed'],budget,s['max_tokens'])
  finally:
   if s['job']in self.executor.originals:self.originals[s['job']]=self.executor.originals[s['job']]
  self.artifacts['report/text']=Artifact(result['report'],'S15','aggregate',s['job'])
  self.artifacts['report/blinded_input']=Artifact(result['blinded_packet'],'S15','aggregate',s['job'])
  self.pending_report={'result':result,'aggregate':artifact.pin,'rubric':self.spec['rubric'],'budget':budget,'started_before_independent_reviews':True}
  return {'status':'awaiting_exact_independent_report_reviews','report':result['report'],'blinded_packet':result['blinded_packet'],'stage_remains_active':'S15','original_deadline':budget.deadline,'no_prediction_reentry':True}
 def admit_report_judgment(self,new_authority,review_pins,adjudication_pin):
  from .reporting import grade_report
  need(self.evidence.active=='S15'and self.pending_report is not None,'actual original pending report')
  need(new_authority.campaign==self.authority.campaign and new_authority.root_source==self.source and new_authority.expires_at<=self.authority.expires_at,'same original authority without renewal')
  need(set(new_authority.stages)<=set(self.authority.stages)and set(new_authority.native_roles)<=set(self.authority.native_roles),'no reporting privilege escalation')
  need(type(review_pins)is list and len(review_pins)==2 and review_pins[0]!=review_pins[1],'two distinct exact independent review sources')
  for pin in [*review_pins,*([adjudication_pin]if adjudication_pin is not None else[])]:descriptor(pin);need(pin in list(new_authority.input_pins),'operator selects original report review source')
  pending=self.pending_report;budget=pending['budget'];budget.admit();reader=Store(self.store.root,budget,Custody('independent_report_judgment'))
  report_pin=pending['result']['report'];reviews=[reader.json(pin,2**20)for pin in review_pins];adjudication=None if adjudication_pin is None else reader.json(adjudication_pin,2**20)
  result=grade_report(reader.read(report_pin,2**20),report_pin,reviews,adjudication,pending['aggregate'],pending['rubric'],reader.json(pending['rubric'],2**20))
  result['original_review_pins']=review_pins;result['original_adjudication_pin']=adjudication_pin
  pin=reader.write('reports/JUDGMENT.json',canonical(result),4*2**20)
  self.authority=new_authority;self.store.budget.authority=new_authority;self.evidence.authority=new_authority;self.executor.authority=new_authority
  self.artifacts['report/judgment']=Artifact(pin,'S15','aggregate','independent_selected_reviewers');pending['judgment']=pin
  return self.finish_stage('S15')
 def actor_stage(self,stage):
  for g in expected_groups():
   if g['mode']!='I':continue
   gid=group_id(g);config=self.selection['participant_groups'][gid];budget=self.group_budget(gid);model=ProcessModel(self.executor,**config['model_service'])
   indices=[None]if stage=='S08'else range(574)
   for i in indices:
    key=gid+('/preparation'if i is None else'/case-%04d'%i);need(key not in self.actor_originals,'fresh case actor, no replay')
    original=Custody('actual_broker:'+key);self.actor_originals[key]=original;before=set(self.executor.originals);before_models=set(self.executor.model_attempts)
    try:
     from .operator_lifecycle import selected_case_context
     context=self.resolve(config['preparation_context']if i is None else selected_case_context(config,gid,i),stage,g['condition'],gid)
     from .programme import allowed_references
     need(tuple(context['references'])==allowed_references(g['condition']),'complete allowed condition-specific reference set');need(all(v['reference']in context['references']for v in context['states'].values()),'no neural state in restricted condition')
     need(context['job_prefix']==key and context['case_index']==i,'fresh exact actor context');need(context['binding']['programme']==self.identity,'actor programme binding')
     if i is not None:
      shared_pin=self.artifacts[gid+'/shared_preparation'].pin;shared=self.store.json(shared_pin,32*2**20);need(shared['schema']=='NLB017_shared_preparation_v1'and shared['frozen']is True and shared['case_answers']==[],'actual original shared preparation')
      for name,state in shared['visible_states'].items():
       if state.get('kind')=='participant_numeric_state':need(state['group_binding']==context['binding']['group'],'same frozen preparation group')
      context['states']=shared['visible_states'];context['shared_preparation_frozen']=True;context['prior_case_answers']=[];context['initial_messages']=[*context['initial_messages'],{'role':'system','content':shared['policy']}];context['initial_context_sha256']=digest(canonical(context['initial_messages']));context['shared_preparation']=shared_pin
     tools=Tools(ToolGateway(self,context,g['condition'],gid),Store(self.store.root,budget,original),self.spec['tool_policy'],context);messages=context['initial_messages']
     result=prepare(model,tools,messages,context,budget,config['max_model_exchanges'])if i is None else investigate(model,tools,messages,context,budget,config['max_model_exchanges'])
     original.original_result=result;original.complete=True
    except BaseException as e:original.fail(e,'actual_model_tool_loop');result=None
    children={k:o for k,o in self.executor.originals.items()if k not in before};original.original_children=children
    # Preserve original model accounting owners even if result acquisition
    # failed before a worker product or process receipt could be published.
    for model_job in self.executor.model_attempts:
     if model_job not in before_models:original.fail(None,'original_model_exchange',self.executor.model_attempts[model_job])
    # A broker is explicitly a composite actor, never a fabricated OS process.
    record={'schema':'NLB017_actual_broker_terminal_v1','job':key,'programme':self.identity,'children':{k:o.persistence.get('process')for k,o in children.items()},'complete':original.complete and bool(children)and all(o.custody.complete and o.absence is True for o in children.values()),'original':original.snapshot(),'budget':budget.snapshot(),'case_index':i,'group':gid,'no_prior_case_answers':True}
    try:
     pin=self.store.write('actors/'+digest(key.encode())+'.json',canonical(record),16*2**20)
     if result is None or not record['complete']:self.collector.failures[key]={'classification':'actual_broker_failed','terminal':pin};continue
     product=self.store.write('actors/'+digest(key.encode())+'.result.json',canonical(result),32*2**20)if i is None else result['prediction']
     self.collector.products[key]={'product':product,'terminal':pin,'bindings':{'programme':self.identity,'job':key,'role':self.jobs[key]['role'],'source':config['source'],'inputs':context['binding']}}
     if i is None:self.artifacts[gid+'/shared_preparation']=Artifact(product,stage,'source_state',key,g['condition'],gid)
    except BaseException as e:original.fail(e,'broker_terminal_publication');self.collector.failures[key]={'classification':'broker_custody_failed','known_original':record}
 def incomplete(self):return {'schema':'NLB017_incomplete_campaign_v1','programme':self.identity,'evidence':self.evidence.disposition(),'collection':None if self.collector is None else self.collector.abort_metadata(),'original_error':self.custody.snapshot(),'target_opened':'S13'in self.evidence.done,'valid_earlier_scores_retained':self.artifacts.get('grade')is not None,'scientific_completion':False}
 def claims(self):
  need('S16'in self.evidence.done and self.evidence.failed is None,'whole actual study closure')
  for key,c in self.evidence.checkpoints.items():
   if 'CLAIMS'in c['required_before']:self.evidence.checkpoint(key)
  return {'programme':self.identity,'complete_scoped_claims':True,'evidence':self.evidence.disposition(),'generalization':'one historically public source/session only'}
