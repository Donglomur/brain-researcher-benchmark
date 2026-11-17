"""Matched development, frozen F execution and event-local I investigation.

The model receives only this controller's prompts and tool results. Arbitrary
numerical scripts never receive checkpoint files or a model/broker capability.
VALIDATION targets remain inside the trusted scalar selection evaluator; every
supervised numerical fit can read FIT targets only.
"""
from __future__ import annotations
import json
import time
import resource
from owner.io import ContractError, Artifact, canonical, capture, decode
from owner.scoring import absolute
from .contracts import CONDITIONS, digest, exact, fixed_graph, job_budget, prediction
from .jobs import run_capsule, JobFailure

SYSTEM='''You are developing or applying one omission-conditional calcium-response predictor. Use only the supplied information view and bounded actions. No network, external files, source identities, other query events or query feedback is available. FIT targets may train parameters. VALIDATION features and a protected aggregate selection evaluator may choose methods; validation targets cannot train parameters. Return exactly one JSON action. Tools: numeric {code,result_key}; inspect {key}; reference {} when R; validate {key} only in development. Development finish {program,explanation}; query finish {prediction:{id,values:[three finite numbers]},explanation}. F query is a sealed fixed graph, never an investigator. Numerical code gets data, inputs and artifacts and sets result; NumPy/SciPy/math and bounded plotting are available, imports/files/processes/reflection are denied. Numeric results remain in named private workspace and are summarized for the model. No hidden trial/retry or alternate checkpoint is available.'''


def features_only(rows):return [{k:v for k,v in r.items() if k!='target'} for r in rows]

def summary(value):
 body=canonical(value)
 if len(body)<=4096:return value
 if isinstance(value,dict):shape={'kind':'object','keys':sorted(value)[:100]}
 elif isinstance(value,list):shape={'kind':'array','length':len(value)}
 else:shape={'kind':type(value).__name__}
 return {'stored_bytes':len(body),'sha256':digest(value),'summary':shape,'access':'inspect returns a bounded prefix description; numeric can consume the entire stored value without a model-token truncation'}


def inspect_value(value):
 if isinstance(value,list):return {'length':len(value),'first':value[:3],'last':value[-3:]}
 if isinstance(value,dict):return {k:summary(v) for k,v in value.items()}
 return value


def prepare_assets(ctx,p):
 qualified=ctx.qualification
 if qualified.get('runtime_profile_sha256')!=digest(p) or any(qualified.get(k)!=ctx.inputs[k].object() for k in ('checkpoint','tokenizer','model_runtime')):raise ContractError('worker assets must be the exact parent-admitted independent qualification')
 if ctx.stage=='N00' and qualified.get('report_recipe')!=ctx.inputs['report_recipe'].object():raise ContractError('report recipe differs from qualified identity')
 runtime=ctx.read_input('model_runtime',roles={'model_runtime'},cap=4_000_000)
 exact(runtime,{'schema','profile_sha256','checkpoint_sha256','tokenizer_sha256','versions','exposure_declaration'},'local model runtime')
 if runtime['schema']!='neural063_local_model_runtime_v1' or runtime['profile_sha256']!=digest(p) or runtime['checkpoint_sha256']!=ctx.inputs['checkpoint'].sha256 or runtime['tokenizer_sha256']!=ctx.inputs['tokenizer'].sha256:raise ContractError('same exact checkpoint/tokenizer/local runtime/profile required')
 if set(runtime['versions'])!={'numeric','model','reference','validation','event_output'} or any(set(v)!={'python','numpy','torch','transformers'} for v in runtime['versions'].values()):raise ContractError('exact actual interpreter/library pins for all five capsule operations required')
 if not isinstance(runtime['exposure_declaration'],str) or not runtime['exposure_declaration']:raise ContractError('checkpoint training/public-data exposure must be explicitly declared, including unknown')
 files=[];names=set()
 from .jobs import authenticate_file
 for key in ('checkpoint','tokenizer'):
  bundle=ctx.read_input(key,roles={key},cap=4_000_000)
  if bundle.get('schema')!='neural063_local_asset_manifest_v1' or not isinstance(bundle.get('files'),list) or not bundle['files']:raise ContractError('complete local model asset manifest required')
  for item in bundle['files']:
   exact(item,{'name','artifact'},'local asset entry');name=item['name']
   if (not isinstance(name,str) or '/' in name or '\\' in name or name.startswith('.') or name in names or not name.endswith(('.json','.safetensors','.model','.txt'))):raise ContractError('ordinary flat nonpickle checkpoint/tokenizer file required')
   names.add(name);ref=authenticate_file(item['artifact'],ctx)
   if ref.visibility!='operator' or ref.role not in {'checkpoint_file','tokenizer_file'}:raise ContractError('operator model asset required')
   files.append(item)
 if 'config.json' not in names or not any(n.endswith('.safetensors') for n in names):raise ContractError('complete local safetensors/config checkpoint required')
 return {'schema':'neural063_runtime_assets_v1','profile_sha256':digest(p),'files':files,'checkpoint_bytes':sum(Artifact.parse(x['artifact']).bytes for x in files),'checkpoint_sha256':ctx.inputs['checkpoint'].sha256,'tokenizer_sha256':ctx.inputs['tokenizer'].sha256,'model_runtime_sha256':ctx.inputs['model_runtime'].sha256,'report_generator_sha256':qualified['report_generator']['sha256'],'qualification_environment_sha256':qualified['environment']['sha256'],'versions':runtime['versions'],'exposure_declaration':runtime['exposure_declaration']}


class Controller:
 def __init__(self,ctx,p,identity,kind,condition,assets,fit,validation,scale,*,event=None,reference=None):
  self.ctx,self.p,self.identity,self.kind,self.condition=ctx,p,identity,kind,condition
  self.mode,self.view,self.tools=condition.split('-');self.assets=assets;self.fit=fit;self.validation=validation;self.scale=scale;self.event=event;self.reference=reference
  self.budget=job_budget(kind,p);self.started=time.monotonic();self.events=[];self.workspace={};self.workspace_sources={};self.job_receipts=[];self.ordinal=0;self.failed_usage_unknown=[];self.last_receipt=None
  self.usage={k:0 for k in ('model_calls','tool_calls','input_tokens','output_tokens','cpu_core_seconds','gpu_device_seconds','logical_read_bytes','logical_write_bytes','retained_bytes')};self.usage.update(ram_peak_bytes=0,vram_peak_bytes=0,trusted_capture_calls=0)
 def remaining(self):
  self.ctx.require_scientific()
  b=dict(self.budget);b['wall_seconds']=max(0,min(self.budget['wall_seconds']-(time.monotonic()-self.started),self.ctx.limits['monotonic_deadline']-time.monotonic()-self.p['cleanup_wall_seconds']))
  for k in ('cpu_core_seconds','gpu_device_seconds','input_tokens','output_tokens','model_calls','tool_calls','read_bytes','write_bytes','retained_bytes'):
   uk={'read_bytes':'logical_read_bytes','write_bytes':'logical_write_bytes'}.get(k,k)
   b[k]-=self.usage[uk]
   if b[k]<0:raise ContractError('controller aggregate allowance exceeded: '+k)
  if b['wall_seconds']<=0 or b['cpu_core_seconds']<1:raise ContractError('controller finite wall/CPU allowance exhausted')
  return b
 def account(self,usage,receipt,operation):
  self.job_receipts.append(receipt)
  record=decode(capture(receipt['path'],16_000_000,descriptor=Artifact.parse(receipt),meter=self.ctx.store.meter))
  self.usage['gpu_device_seconds']+=record['gpu_device_seconds']
  engine_cpu=record.get('last_engine_stats',{}).get('cpu_stats',{}).get('cpu_usage',{}).get('total_usage',0)/1e9
  self.usage['cpu_core_seconds']+=max(engine_cpu,usage.get('cpu_core_seconds',0))
  for k in ('input_tokens','output_tokens','logical_read_bytes','logical_write_bytes'):self.usage[k]+=usage.get(k,0)
  self.usage['retained_bytes']+=record['stdout']['bytes']+record['stderr']['bytes']+record['unparsed_stream']['bytes']+receipt['bytes']
  io=record['operator_logical_io_before_receipt']
  self.usage['logical_read_bytes']+=io['read_bytes']+receipt['bytes']
  self.usage['logical_write_bytes']+=io['write_bytes']+receipt['bytes']
  self.usage['ram_peak_bytes']=max(self.usage['ram_peak_bytes'],usage.get('ram_peak_bytes',0),record.get('last_engine_stats',{}).get('memory_stats',{}).get('usage',0))
  self.usage['vram_peak_bytes']=max(self.usage['vram_peak_bytes'],usage.get('vram_peak_bytes',0),record.get('gpu_peak_bytes',0))
  identity=record.get('actual_capsule_identity') or {}
  if identity.get('worker_uids')!=[self.p['worker_uid']]*3 or identity.get('worker_gids')!=[self.p['worker_gid']]*3 or identity.get('supervisor_uids')!=[self.p['uid']]*4 or identity.get('supervisor_gids')!=[self.p['gid']]*4:raise ContractError('actual isolated controller identities differ from exact matched profile')
  expected=self.assets['versions'].get(operation)
  if expected!=record.get('runtime'):raise ContractError('actual package/interpreter identity differs from pinned same runtime')
  self.remaining()
 def capsule(self,operation,payload,*,trusted_capture=False):
  budget=self.remaining();counter='model_calls' if operation=='model' else 'tool_calls'
  if not trusted_capture and budget[counter]<1:raise ContractError('controller call budget exhausted')
  if trusted_capture:
   if self.kind!='event' or self.usage['trusted_capture_calls']!=0:raise ContractError('exactly one fresh protected event capture required')
   self.usage['trusted_capture_calls']+=1
  else:self.usage[counter]+=1
  self.ordinal+=1
  if operation=='model':budget['wall_seconds']=min(budget['wall_seconds'],budget['gpu_device_seconds'])
  request=dict(payload,operation=operation,read_bytes=budget['read_bytes'],write_bytes=budget['write_bytes'])
  try:
   result,used,receipt=run_capsule(self.ctx,self.p,self.identity,self.ordinal,request,budget,checkpoint_mounts=self.assets['files'] if operation=='model' else ())
  except JobFailure as exc:
   self.job_receipts.append(exc.receipt);self.failed_usage_unknown.append(exc.receipt['sha256'])
   # Actual failed-job counters remain in the independently retained receipt;
   # no successful accounting or prediction is fabricated for the failed action.
   raise
  except BaseException:
   self.failed_usage_unknown.append('uncompleted-claim:'+self.identity+':'+str(self.ordinal));raise
  self.account(used,receipt,operation);self.last_receipt=receipt
  self.events.append({'operation':operation,'request_sha256':digest(request),'receipt':receipt,'result_summary':summary(result)})
  return result
 def model(self,prompt,max_new_tokens=None):
  b=self.remaining();limit=min(b['output_tokens'],max_new_tokens if max_new_tokens is not None else 8192)
  if limit<1:raise ContractError('no output tokens remain')
  return self.capsule('model',{'prompt':prompt,'max_new_tokens':int(limit),'input_tokens_remaining':b['input_tokens'],'cpu_threads':8,'gpu_total_bytes':self.p['gpu_total_bytes'],'checkpoint_bytes':self.assets['checkpoint_bytes']})['text']
 def numeric(self,code,inputs=None):
  data={'fit':self.fit,'validation_features':features_only(self.validation),'event':self.event}
  return self.capsule('numeric',{'code':code,'data':data,'inputs':inputs or {},'artifacts':self.workspace})['value']
 def reference_call(self,event=None):
  if self.tools!='R' or self.reference is None:raise ContractError('reference capability absent for G')
  value=dict(event or self.event);value.pop('target',None);value['split']='query'
  # The sealed predictor runs in its own bounded non-GPU capsule. A slow or
  # failed pure prediction cannot bypass the event CPU/wall budget.
  result=self.capsule('reference',{'model':self.reference,'view':self.view,'event':value})
  self.events.append({'operation':'sealed_reference','view':self.view,'event_id':value['id'],'model_sha256':digest(self.reference),'result':result})
  return result
 def validate(self,key):
  if self.kind!='development':raise ContractError('query-time validation target access is denied')
  value=self.workspace[key];predictions=value.get('predictions') if isinstance(value,dict) else value
  # Only this trusted fixed operation can receive validation labels. It returns
  # the hierarchical aggregate; no numerical candidate script sees its request.
  score=self.capsule('validation',{'predictions':predictions,'validation':self.validation,'fit_scale':self.scale})
  self.events.append({'operation':'validation_selection_only','prediction_sha256':digest(predictions),'target_access':'trusted aggregate evaluator only; labels not released','value':score})
  return score
 def investigate(self,prompt,*,development=False):
  conversation=[SYSTEM,prompt]
  while True:
   text=self.model('\n'.join(conversation))
   action=decode(text.encode());self.events.append({'operation':'model_action','action':action})
   kind=action.get('action')
   if kind=='finish':
    if development:
     exact(action,{'action','program','explanation'},'development finish');program=action['program']
     # Artifacts are references to actual FIT-derived numerical results, not
     # mutable host paths. Freeze their complete values with the returned program.
     names=program.get('artifacts')
     if not isinstance(names,list) or len(names)!=len(set(names)) or any(n not in self.workspace for n in names):raise ContractError('sealed program artifacts must bind actual private workspace values')
     program=dict(program,artifacts={n:self.workspace_sources[n] for n in names})
     if self.mode=='F':fixed_graph(program,self.view,self.tools)
     else:
      exact(program,{'schema','mode','view','tools','system_prompt','artifacts'},'I library')
      if (program['schema'],program['mode'],program['view'],program['tools'])!=('neural063_investigation_library_v1','I',self.view,self.tools) or not isinstance(program['system_prompt'],str):raise ContractError('sealed I library identity required')
     return program,action['explanation']
    exact(action,{'action','prediction','explanation'},'query finish')
    return prediction(action['prediction'],self.event['id']),action['explanation']
   if kind=='numeric':
    exact(action,{'action','code','result_key'},'numeric action');key=action['result_key']
    if not isinstance(key,str) or not key or key in self.workspace:raise ContractError('fresh named private workspace result required')
    self.workspace[key]=self.numeric(action['code']);self.bind_workspace_source(key);result=summary(self.workspace[key])
   elif kind=='inspect':
    exact(action,{'action','key'},'inspect action');self.remaining();self.usage['tool_calls']+=1;result=inspect_value(self.workspace[action['key']]);self.remaining()
   elif kind=='validate':
    exact(action,{'action','key'},'validate action');result=self.validate(action['key'])
   elif kind=='reference':
    if development:
     exact(action,{'action','split','index'},'development reference action')
     if action['split'] not in {'fit','validation'} or type(action['index']) is not int or action['index']<0:raise ContractError('exact allowed development event selector required')
     result=self.reference_call((self.fit if action['split']=='fit' else self.validation)[action['index']])
    else:exact(action,{'action'},'reference action');result=self.reference_call()
   else:raise ContractError('unknown bounded investigator action')
   conversation.append('Action: '+json.dumps(action,separators=(',',':'))+'\nResult: '+json.dumps(result,separators=(',',':'),allow_nan=False))
 def fixed(self,program):
  audit=fixed_graph(program,self.view,self.tools);self.load_artifacts(program['artifacts']);values={'event':self.event,'fit':self.fit,'validation':features_only(self.validation),'artifacts':self.workspace};trace=[]
  for node in program['nodes']:
   inputs={k:values[k] for k in node['inputs']};op=node['op'];par=node['parameters']
   if op=='constant':value=par['value']
   elif op=='numeric':value=self.numeric(par['code'],inputs)
   elif op=='model':
    template=par['prompt_template']
    if template.count('{inputs_json}')!=1:raise ContractError('fixed prompt must have one fixed JSON substitution point')
    value=decode(self.model(template.replace('{inputs_json}',canonical(inputs).decode()),par['max_new_tokens']).encode())
    if par['parser']=='prediction':prediction(value,self.event['id'])
   else:value=self.reference_call()
   values[node['id']]=value;trace.append({'slot':node['id'],'op':op,'input_sha256':digest(inputs),'output_sha256':digest(value)})
  if [x['slot'] for x in trace]!=audit['fixed_slots']:raise ContractError('actual F trace differs from sealed call graph')
  self.events.append({'operation':'fixed_graph_trace','source_sha256':audit['source_sha256'],'trace':trace})
  return prediction(values[program['output']],self.event['id']),'fixed sealed graph'
 def bind_workspace_source(self,key):
  if self.last_receipt is None:raise ContractError('workspace value lacks actual numerical producer')
  record=decode(capture(self.last_receipt['path'],16_000_000,descriptor=Artifact.parse(self.last_receipt),meter=self.ctx.store.meter))
  self.workspace_sources[key]={'source':record['stdout'],'path':['result','value'],'value_sha256':digest(self.workspace[key])}
 def load_artifacts(self,artifacts):
  self.workspace={};self.workspace_sources=dict(artifacts)
  for key,record in artifacts.items():
   exact(record,{'source','path','value_sha256'},'sealed fitted artifact')
   if record['path']!=['result','value']:raise ContractError('fixed numerical result path required')
   ref=Artifact.parse(record['source'])
   if ref.role!='runtime_stdout':raise ContractError('sealed fit artifact must be actual numerical stdout')
   body=capture(ref.path,4*2**30,descriptor=ref,meter=self.ctx.store.meter);value=decode(body)['result']['value']
   if digest(value)!=record['value_sha256']:raise ContractError('sealed FIT-derived value changed')
   self.workspace[key]=value;self.usage['logical_read_bytes']+=len(body)
  self.remaining()
 def receipt(self,status,failure=None):
  unused={k:max(0,v-self.usage.get({'read_bytes':'logical_read_bytes','write_bytes':'logical_write_bytes'}.get(k,k),0)) for k,v in self.budget.items() if k in {'cpu_core_seconds','gpu_device_seconds','input_tokens','output_tokens','model_calls','tool_calls','read_bytes','write_bytes','retained_bytes'}}
  return {'schema':'neural063_controller_receipt_v1','controller':self.identity,'condition':self.condition,'kind':self.kind,'status':status,'failure':failure,'budget':self.budget,'usage':dict(self.usage,wall_seconds=time.monotonic()-self.started),'unused_allocations':{k:(None if self.failed_usage_unknown and k not in {'model_calls','tool_calls'} else v) for k,v in unused.items()},'usage_basis':'completed-job measurements plus exact attempted call counts; failed unavailable counters are explicitly named, never zero-imputed','failed_usage_unknown':self.failed_usage_unknown,'job_receipts':self.job_receipts,'profile_sha256':digest(self.p),'checkpoint_sha256':self.assets['checkpoint_sha256'],'event_id':self.event['id'] if self.event else None,'query_targets_accessed':False,'physical_os_io_bytes':None}
