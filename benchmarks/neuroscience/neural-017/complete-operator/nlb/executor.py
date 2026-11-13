"""Production source/containment dispatcher; test substitution is explicit."""
from .contracts import need,closed,canonical,parse,digest,Budget,Custody,Store
import copy
from .isolation import LinuxCgroupSandbox
from .process import run,persist,Observation
from .worker_runtime import validate_terminal,receipt_limits

class Executor:
 def __init__(self,authority,store,source_sha,selected_jobs,*,isolation_class=LinuxCgroupSandbox,process_run=run):
  from .native_selection import select_native_jobs,native_census
  self.authority=authority;self.store=store;self.source=source_sha;self.selected=select_native_jobs(selected_jobs,store);self.process_census,self.original_parents=native_census(self.selected);self.isolation_class=isolation_class;self.process_run=process_run;self.originals={};self.counts={};self.invocation_stores={};self.attempt_custodies={};self.tool_variant_choices={};self.reference_services={};self.model_attempts={}
 def bind_reference_service(self,job,service):
  need(job not in self.reference_services and job not in self.attempt_custodies and service.job==job and service.campaign.executor is self,'fresh source-owned frozen-program service')
  self.reference_services[job]=service
 def service_owns_slot(self,gid,job):
  service=self.reference_services.get(gid+'/programme')
  return service is not None and service.active_slot==job and job in service.slots and gid+'/programme'in self.originals and not self.originals[gid+'/programme'].custody.complete
 def select_tool_variant(self,job,tool,participant_profile):
  """One precommitted slot, one actual kind, one immutable source/profile choice."""
  from .runtime_policy import tool_variant_profile
  need(job in self.selected and job not in self.tool_variant_choices and job not in self.attempt_custodies,'fresh tool variant slot')
  slot=self.selected[job];closed(slot,{'stage','role','parent_group','process_limit','tool_variants'})
  need(slot['role']=='participant_tool'and slot['stage']in('S07','S08','S09'),'participant tool slot')
  closed(slot['tool_variants'],{'reference_predict'}if slot['stage']=='S07'else{'run_python','reference_predict'})
  if slot['stage']=='S07':need(self.service_owns_slot(slot['parent_group'],job),'only active original frozen-program gateway slot')
  # Validate both options before selecting either; an arbitrary payload cannot
  # supply its own runtime, source manifest, mounts or new resource envelope.
  for kind,variant in slot['tool_variants'].items():
   for key in('stage','role','parent_group','process_limit'):need(variant[key]==slot[key],'same original cumulative tool slot')
   tool_variant_profile(kind,participant_profile,variant['sandbox']['runtime_profile'])
  need(tool in slot['tool_variants'],'closed actual tool kind');chosen=copy.deepcopy(slot['tool_variants'][tool])
  self.tool_variant_choices[job]={'tool':tool,'participant_profile':participant_profile,'original_slot':copy.deepcopy(slot),'selected_source':chosen['source'],'selected_runtime_profile':chosen['sandbox']['runtime_profile']}
  self.selected[job]=chosen
  return chosen
 def invoke(self,job,stage,role,payload,budget):
  need(job not in self.attempt_custodies and job not in self.originals,'no replay of consumed invocation');c=Custody('invoke:'+job);c.original_request=payload;self.attempt_custodies[job]=c
  try:return self._invoke(job,stage,role,payload,budget,c)
  except BaseException as e:
   c.fail(e,'invocation')
   # Allocation or sandbox construction can fail before an original process
   # exists. No child was launched: release its exact held allocation once,
   # while preserving this consumed invocation and its original failure.
   if job not in self.originals and job in budget.child_leases and not budget.child_leases[job]['joined']:
    try:
     limits=budget.child_leases[job]['limits'];zero={'limits':limits,'used':dict.fromkeys(Budget.IO_KEYS,0),'reserved':dict.fromkeys(Budget.IO_KEYS,0)}
     budget.settle_io(job,zero);c.facts['known_no_launch_worker_io']=zero
    except BaseException as secondary:c.fail(secondary,'prelaunch_child_allocation_release')
   try:c.facts['known_budget']=budget.snapshot()
   except BaseException as secondary:c.fail(secondary,'invocation_budget_snapshot')
   c.raise_if_failed()
 def _invoke(self,job,stage,role,payload,budget,custody):
  self.authority.check(stage,role);budget.admit();need(job in self.selected and job not in self.originals,'fresh exact selected invocation');s=self.selected[job]
  if role=='participant_tool':
   need(job in self.tool_variant_choices,'tool source/profile selected before dispatch');choice=self.tool_variant_choices[job]
   need(payload['body']['tool']==choice['tool']and s['sandbox']['runtime_profile']==choice['selected_runtime_profile']and s['source']==choice['selected_source'],'actual request matches consumed tool variant')
   custody.facts['tool_variant']={k:v for k,v in choice.items()if k!='original_slot'}
  required={'stage','role','source','input_manifests','argv','sandbox','stream_limit','max_product_bytes','process_limit','parent_group','result_path','worker_io_limits','completion_io_limits','worker_receipt_limits'};need(set(s)in(required,required|{'dynamic_input_policy'}),'closed native invocation')
  need(s['stage']==stage and s['role']==role,'selected invocation role');scoped=Store(self.store.root,budget,custody);self.invocation_stores[job]=scoped;scoped.read(s['source'],16*2**20)
  for pin in s['input_manifests']:scoped.read(pin,16*2**20)
  parent=s['parent_group'];self.counts[parent]=self.counts.get(parent,0)+1
  original_parent=self.original_parents[job]if self.original_parents is not None else self.selected.original_parent(job)
  need(parent==original_parent,'original source-owned process parent');census=self.process_census[parent];need(type(s['process_limit'])is int and s['process_limit']==census and self.counts[parent]<=census,'exact finite lifetime launch census')
  budget.charge('tool_calls',1);receipts=receipt_limits(s['worker_receipt_limits'])
  if role=='participant_F':self.reference_services[job].admit_parent_io(s)
  child_limits=budget.lease_io(job,s['worker_io_limits'],s['completion_io_limits'])
  need(child_limits['write_bytes']>=sum(receipts.values())and child_limits['created_files']>=3,'finite child terminal capacity')
  envelope={'schema':'NLB017_executor_worker_envelope_v2','job':job,'source':s['source'],'io_limits':child_limits,'receipt_limits':receipts,'deadline':budget.deadline,'payload':payload}
  request={'stage':stage,'role':role,'argv':s['argv'],'stdin':canonical(envelope),'stream_limit':s['stream_limit'],'input_manifests':s['input_manifests'],'source':s['source'],'cpu_remaining':budget.available('cpu_seconds')}
  iso=self.isolation_class(self.authority,job,role,s['sandbox'],scoped)
  # Caller owns the carrier BEFORE any launch/clock/finalizer can raise.
  o=Observation(job,dict(request),custody=Custody('process:'+job));o.custody.original=o;custody.original=o;self.originals[job]=o
  try:
   service=self.reference_services.get(job)
   need((service is not None)==(role=='participant_F'),'every frozen program has exactly its live reference interface')
   extra={'reference_service':service}if service is not None else{}
   returned=self.process_run(job,request,budget,iso,observation=o,**extra);need(returned is o,'same original caller-owned process')
  except BaseException as e:o.custody.fail(e,'process_dispatch_or_finalization');budget.stop('unresolved original process '+job)
  terminal_custody=None
  try:
   if not o.launch_attempted:
    budget.settle_io(job,{'limits':child_limits,'used':dict.fromkeys(Budget.IO_KEYS,0),'reserved':dict.fromkeys(Budget.IO_KEYS,0)})
   else:
    need(o.reaped and o.absence is True,'do not inspect live/uncontained worker outputs')
    terminal_custody=Custody('worker_terminal_capture:'+job);terminal_store=Store(self.store.root,budget,terminal_custody)
    name=s['result_path'].rsplit('/',1)[0]+'/TERMINAL.json';pin,raw=terminal_store.capture(name,receipts['terminal_bytes'])
    body=validate_terminal(raw,job,s['source'],child_limits,payload.get('bindings'))
    o.persistence['worker_terminal']=pin;o.costs['worker_io']=body['final_io'];o.custody.facts['original_worker_terminal']=body
    budget.settle_io(job,body['final_io'])
    need(body['terminal']['complete']is True and body['terminal']['first_error']is None,'worker failure retained before result admission')
  except BaseException as e:
   o.custody.fail(e,'worker_terminal_join')
   if not budget.child_leases[job]['joined']:budget.unknown_child(job)
  finally:
   if terminal_custody is not None:o.custody.fail(None,'original_worker_terminal_capture',terminal_custody)
  scoped.custody=o.custody;persist(o,scoped,'processes/'+digest(job.encode()));return o
 def product(self,observation):
  need(observation.custody.complete and observation.exit_code==0 and observation.absence is True,'complete actual producer')
  scoped=self.invocation_stores[observation.job];result_pin,raw=scoped.capture(self.selected[observation.job]['result_path'],8*2**20);d=parse(raw);closed(d,{'schema','job','source','products','bindings'})
  need(d['schema']=='NLB017_worker_result_v1'and d['job']==observation.job and d['source']==self.selected[observation.job]['source'],'actual worker response identity')
  prefix=self.selected[observation.job]['result_path'].rsplit('/',1)[0];mapped={}
  from .contracts import descriptor
  for key,p in d['products'].items():
   descriptor(p);mapped[key]={**p,'path':prefix+'/'+p['path']};scoped.read(mapped[key],self.selected[observation.job]['max_product_bytes'])
  observation.persistence['worker_result']=result_pin;return {**d,'products':mapped,'original_worker_result':result_pin}
 def all_absent(self):return all(o.absence is True and o.reaped for o in self.originals.values())

class ProcessModel:
 """A real separately qualified model gateway executable, not a canned policy.

 The selected gateway owns actual model/API authentication and provider identity.
 It must return original provider response and complete token usage as products.
 No default executable, model, credential or service is silently selected here.
 """
 def __init__(self,executor,identity,configuration,prompt,tokenizer,qualification):
  self.executor=executor;self.identity=identity;self.configuration=configuration;self.prompt=prompt;self.tokenizer=tokenizer;self.qualification=qualification
 def exchange(self,job,stage,messages,seed,budget,remaining_tokens):
  need(job not in self.executor.model_attempts,'one original model exchange attempt')
  owner=Custody('model_exchange:'+job);self.executor.model_attempts[job]=owner
  usage={'request_allowance':remaining_tokens,'allowance_held':False,'invocation_attempted':False,
         'dispatch_state':'not_attempted','provider_usage':None,'charged_tokens':None,
         'charge_attempted':False,'charge_attempted_tokens':None,'charge_status':'not_attempted','usage_status':'not_dispatched'}
  owner.facts['model_usage']=usage;o=None;reply=None;receipt=None
  scoped=Store(self.executor.store.root,budget,owner)
  def release_hold():
   if usage['allowance_held']:
    # Actual Budget._hold has no external effect; it transfers the same original
    # aggregate hold through all ancestors. It never refunds charged usage.
    budget._hold('model_tokens',-remaining_tokens);usage['allowance_held']=False
  def charge_once(tokens,phase):
   release_hold();usage['charge_attempted']=True;usage['charge_attempted_tokens']=tokens
   before=budget.used['model_tokens'];usage['charge_status']='attempted'
   try:budget.charge('model_tokens',tokens);usage['charge_status']='returned'
   except BaseException as error:
    usage['charge_status']='failed_or_unknown';owner.fail(error,phase);budget.stop('unresolved model token accounting '+job)
    owner.raise_if_failed()
   finally:
    # A request to debit is not itself evidence that the debit happened. This
    # source-owned counter delta survives both pre- and post-effect failures.
    usage['charged_tokens']=budget.used['model_tokens']-before
  try:
   need(self.qualification in list(self.executor.authority.input_pins),'actual model service qualification open')
   scoped.read(self.qualification,8*2**20);budget.admit()
   need(type(remaining_tokens)is int and remaining_tokens>0 and remaining_tokens<=budget.available('model_tokens'),'original residual model token allowance')
   budget._hold('model_tokens',remaining_tokens);usage['allowance_held']=True
   payload={'schema':'NLB017_actual_model_request_v1','model':self.identity,'configuration':self.configuration,'prompt':self.prompt,'tokenizer':self.tokenizer,'seed':seed,'messages':messages,'max_remaining_total_tokens':remaining_tokens}
   owner.original_request=payload;usage['invocation_attempted']=True
   o=self.executor.invoke(job,stage,'model_exchange',payload,budget);owner.original=o
   owner.fail(None,'original_model_process',o.custody);owner.raise_if_failed()
   d=self.executor.product(o)
   body=scoped.json(d['products']['exchange'],8*2**20);owner.original_exchange=body
   closed(body,{'schema','request_sha256','model','configuration','tokenizer','provider_response','usage','assistant'})
   need(body['schema']=='NLB017_actual_model_exchange_v1'and body['request_sha256']==digest(canonical(payload))and body['model']==self.identity and body['configuration']==self.configuration and body['tokenizer']==self.tokenizer,'exact original model roundtrip')
   scoped.read(body['provider_response'],8*2**20)
   closed(body['usage'],{'input_tokens','output_tokens','total_tokens','status','reasoning_tokens','cached_input_tokens','unknown_token_classes'})
   u=body['usage'];need(u['status']=='provider_reported'and all(type(u[k])is int and u[k]>=0 for k in('input_tokens','output_tokens','total_tokens','reasoning_tokens','cached_input_tokens'))and u['total_tokens']==u['input_tokens']+u['output_tokens']and u['reasoning_tokens']<=u['output_tokens']and u['cached_input_tokens']<=u['input_tokens']and u['unknown_token_classes']==[],'actual complete token accounting; reasoning is included in output, cache in input')
   # Once authenticated usage is known, preserve and debit it before validating
   # the assistant or building any receipt. Later failures do not debit twice.
   usage['provider_usage']=dict(u);usage['usage_status']='known_provider_usage'
   o.costs['model_tokens']=u['total_tokens'];charge_once(u['total_tokens'],'known_model_usage_charge')
   need(u['total_tokens']<=remaining_tokens,'request token partition exceeded');closed(body['assistant'],{'content','tool_calls'})
   reply=body['assistant'];receipt={'exchange':d['products']['exchange'],'original_process':o.persistence['process'],'tokens':u['total_tokens']}
  except BaseException as error:
   # Executor records an Observation before its only process dispatch. Its
   # absence (or launch_attempted=False) is source-owned known no launch; a
   # launch attempt whose outcome is unknown must consume the old allowance.
   if o is None:o=self.executor.originals.get(job)
   if o is not None:
    owner.original=o;owner.fail(None,'original_model_process',o.custody)
   owner.fail(error,'model_exchange')
   possible=o is not None and (o.launch_attempted or o.dispatched)
   usage['dispatch_state']='observed_started'if o is not None and o.dispatched else'unknown_after_launch_attempt'if possible else'known_not_dispatched'
   if usage['provider_usage']is None and possible:
    usage['usage_status']='unknown_after_dispatch';budget.stop('unknown original model usage '+job)
    o.costs['model_tokens']=None;o.costs['unknown_token_allowance']=remaining_tokens
    if not usage['charge_attempted']:
     try:charge_once(remaining_tokens,'unknown_model_usage_charge')
     except BaseException as secondary:owner.fail(secondary,'unknown_usage_settlement')
   elif usage['provider_usage']is None:
    usage['usage_status']='known_not_dispatched';usage['charged_tokens']=0
   elif not usage['charge_attempted']:
    # An interrupted settlement cannot be silently called a known-cost success.
    budget.stop('unsettled known original model usage '+job)
  finally:
   if o is not None:
    usage['dispatch_state']='observed_started'if o.dispatched else'unknown_after_launch_attempt'if o.launch_attempted else'known_not_dispatched'
   try:release_hold()
   except BaseException as secondary:
    owner.fail(secondary,'model_allowance_release');budget.stop('unresolved original model allowance '+job)
   try:owner.facts['original_budget_after_exchange']=budget.snapshot()
   except BaseException as secondary:owner.fail(secondary,'model_budget_snapshot');budget.stop('unknown original model budget '+job)
   if o is not None:
    # Copy the final usage disposition into the original process owner without
    # creating recursive custody links; the broker also keeps this owner.
    o.custody.facts['model_usage']=dict(usage)
    if usage['usage_status']=='unknown_after_dispatch':o.costs['unknown_token_reservation_consumed']=usage['charged_tokens']
    if owner.first_error is not None:o.custody.fail(owner.first_error,'model_exchange')
  owner.complete=owner.first_error is None;owner.raise_if_failed()
  return reply,receipt
