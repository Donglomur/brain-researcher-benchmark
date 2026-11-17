"""Pure exact runtime schemas, matched budgets and fixed-program admission."""
from __future__ import annotations
import hashlib
import math
import re
from owner.io import Artifact, ContractError, canonical

CONDITIONS = tuple(f'{m}-{v}-{t}' for m in ('F','I') for v in ('T','N') for t in ('G','R'))
STAGES = ('D00','D01','Q00','Q01','Q02','Q03','N00')
CONTEXT = {'cre_line','targeted_structure','imaging_depth','image_set','passive','experience_level','session_number'}
BASE = {'cpu_cores':8,'ram_bytes':64*2**30,'gpu_devices':1,'gpu_vram_bytes':48*2**30}
BUDGETS = {
 'development':dict(BASE, wall_seconds=28800,cpu_core_seconds=230400,gpu_device_seconds=28800,input_tokens=2000000,output_tokens=200000,model_calls=512,tool_calls=2048,scratch_bytes=4*2**30,retained_bytes=4*2**30),
 'event':dict(BASE,wall_seconds=120,cpu_core_seconds=480,gpu_device_seconds=120,input_tokens=65536,output_tokens=8192,model_calls=16,tool_calls=32,scratch_bytes=256*2**20,retained_bytes=8*2**20),
 'report':dict(BASE,wall_seconds=300,cpu_core_seconds=1200,gpu_device_seconds=300,input_tokens=32768,output_tokens=4096,model_calls=8,tool_calls=16,scratch_bytes=256*2**20,retained_bytes=8*2**20,read_bytes=2**30,write_bytes=512*2**20),
}

def digest(obj): return hashlib.sha256(canonical(obj)).hexdigest()

def exact(value, fields, label):
 if not isinstance(value,dict) or set(value)!=set(fields): raise ContractError('exact '+label+' fields required')
 return value

def positive(value,label):
 if type(value) is not int or value<=0: raise ContractError('positive integer required: '+label)
 return value

def prediction(value,event_id):
 exact(value,{'id','values'},'prediction')
 if value['id']!=event_id or not isinstance(value['values'],list) or len(value['values'])!=3: raise ContractError('wrong prediction identity/shape')
 for x in value['values']:
  try: ok=type(x) in (int,float) and math.isfinite(float(x))
  except OverflowError: ok=False
  if not ok: raise ContractError('three finite prediction numbers required')
 return value

def row(value,view,split):
 fields={'id','mouse','session','experiment','split','previous','context'}
 if view=='N': fields.add('history')
 if split!='query': fields.add('target')
 exact(value,fields,'view row')
 if value['split']!=split or any(not isinstance(value[k],str) or not value[k] for k in ('id','mouse','session','experiment')): raise ContractError('opaque hierarchy/split required')
 if set(value['context'])!=CONTEXT or len(value['previous'])!=3: raise ContractError('original context/history timing required')
 if view=='N' and (len(value['history'])!=12 or value['history'][-1]!=0): raise ContractError('original12-bin baseline-adjusted history required')
 if split!='query': prediction({'id':value['id'],'values':value['target']},value['id'])
 return value

def rows(envelope,view,split):
 exact(envelope,{'schema','split','rows'},'row envelope')
 if envelope['schema']!='neural063_rows_v2' or envelope['split']!=split or not isinstance(envelope['rows'],list) or not envelope['rows']: raise ContractError('complete original row envelope required')
 output=[row(x,view,split) for x in envelope['rows']]
 ids=[x['id'] for x in output]
 if ids!=sorted(set(ids)): raise ContractError('strict complete sorted identity sequence required')
 expected={'fit':73,'validation':15,'query':19}[split]
 if len({x['mouse'] for x in output})!=expected: raise ContractError('full original mouse panel required')
 return output

def profile(value):
 fields={'schema','engine_socket','engine_api','engine_id','image_id','image_repo_digest','runtime_files','trusted_tool_files','seccomp','uid','gid','worker_uid','worker_gid','cpu_ids','gpu_uuid','gpu_total_bytes','gpu_partition_bytes','gpu_exclusive_lock','engine_response_bytes','engine_timeout_seconds','cleanup_read_bytes','cleanup_write_bytes','cleanup_wall_seconds','development_read_bytes','event_read_bytes','development_write_bytes','event_write_bytes','aggregate','host_storage'}
 exact(value,fields,'runtime profile')
 if value['schema']!='neural063_runtime_profile_v1' or not re.fullmatch(r'v1\.[0-9]+',value['engine_api']): raise ContractError('pinned local engine API required')
 for k in ('image_id',):
  if not re.fullmatch(r'sha256:[0-9a-f]{64}',value[k]): raise ContractError('exact OCI image digest required')
 if '@sha256:' not in value['image_repo_digest'] or not value['engine_id']: raise ContractError('pinned engine and image repository identity required')
 for k in ('uid','gid','worker_uid','worker_gid','gpu_total_bytes','gpu_partition_bytes','engine_response_bytes','engine_timeout_seconds','cleanup_read_bytes','cleanup_write_bytes','cleanup_wall_seconds','development_read_bytes','event_read_bytes','development_write_bytes','event_write_bytes'): positive(value[k],k)
 if value['uid']==value['worker_uid'] or value['gid']==value['worker_gid'] or value['gpu_partition_bytes']!=value['gpu_total_bytes'] or value['gpu_total_bytes']>48*2**30: raise ContractError('exclusive complete GPU <=48GiB and nonroot container identity required')
 if not isinstance(value['gpu_uuid'],str) or not value['gpu_uuid'].startswith('GPU-'): raise ContractError('exact physical GPU UUID required')
 if len(value['cpu_ids'])!=8 or len(set(value['cpu_ids']))!=8 or any(type(x) is not int or x<0 for x in value['cpu_ids']): raise ContractError('same eight concrete CPU IDs required')
 if set(value['runtime_files'])!={'capsule.py','safe_python.py'}: raise ContractError('exact minimal runtime source closure required')
 expected_tools={'owner/__init__.py','owner/io.py','owner/scoring.py','references/__init__.py','references/schema.py','references/features.py','references/primary.py','references/tool.py'}
 if set(value['trusted_tool_files'])!=expected_tools:raise ContractError('exact sealed reference/validation source closure required')
 for r in [*value['runtime_files'].values(),*value['trusted_tool_files'].values(),value['seccomp']]: Artifact.parse(r)
 for k in ('aggregate','host_storage'):
  if not isinstance(value[k],dict) or not value[k]: raise ContractError('concrete aggregate/storage allocation required')
 return value

def job_budget(kind,p):
 b=dict(BUDGETS[kind])
 if kind!='report':
  b['read_bytes']=p[kind+'_read_bytes']; b['write_bytes']=p[kind+'_write_bytes']
 return b

def full_allocation(p,query_events):
 positive(query_events,'complete query count')
 expected={
  'query_events':query_events,'query_controllers':8*query_events,'event_capture_capsules':8*query_events,'runtime_capsules_max':20672+392*query_events,'development_controllers':8,'report_controllers':8,
  'cpu_core_seconds':1852800+3840*query_events,'gpu_device_seconds':232800+960*query_events,
  'input_tokens':16262144+524288*query_events,'output_tokens':1632768+65536*query_events,
  'model_calls':4160+128*query_events,'tool_calls':16512+256*query_events,
  'retained_bytes':34426847232+67108864*query_events,
  'read_bytes':8*p['development_read_bytes']+8*query_events*p['event_read_bytes']+8*2**30,
  'write_bytes':8*p['development_write_bytes']+8*query_events*p['event_write_bytes']+8*512*2**20,
 }
 if p['aggregate']!=expected: raise ContractError('complete original-program aggregate must equal exact prospective roster sum')
 storage=p['host_storage']
 exact(storage,{'selected_root','total_capacity_bytes','existing_bytes','additional_retained_bytes','scratch_peak_bytes','observation'},'host storage allocation')
 for k in ('total_capacity_bytes','existing_bytes','additional_retained_bytes','scratch_peak_bytes'):
  if type(storage[k]) is not int or storage[k]<0: raise ContractError('finite storage quantities required')
 if storage['additional_retained_bytes']<max(expected['retained_bytes'],expected['write_bytes']) or storage['existing_bytes']+storage['additional_retained_bytes']+storage['scratch_peak_bytes']>storage['total_capacity_bytes']: raise ContractError('original complete runtime does not fit admitted storage')
 Artifact.parse(storage['observation'])
 return expected

def fixed_graph(value,view,tools):
 exact(value,{'schema','mode','view','tools','nodes','output','artifacts'},'fixed program')
 if (value['schema'],value['mode'],value['view'],value['tools'])!=('neural063_fixed_graph_v1','F',view,tools): raise ContractError('frozen F graph identity required')
 if not isinstance(value['nodes'],list) or not value['nodes']: raise ContractError('finite nonempty fixed graph required')
 seen=set(); model_slots=[]
 for n in value['nodes']:
  exact(n,{'id','op','inputs','parameters'},'fixed node')
  if not isinstance(n['id'],str) or n['id'] in seen or n['op'] not in {'constant','numeric','model','reference'}: raise ContractError('only static fixed graph operations allowed')
  if not isinstance(n['inputs'],list) or any(x not in seen and x not in {'event','fit','validation','artifacts'} for x in n['inputs']): raise ContractError('fixed graph inputs must point backward to exact fixed slots')
  if n['op']=='reference' and tools!='R': raise ContractError('G cannot invoke reference')
  if n['op']=='model':
   exact(n['parameters'],{'prompt_template','max_new_tokens','parser'},'fixed model slot')
   if n['parameters']['parser'] not in {'json','prediction'} or not isinstance(n['parameters']['prompt_template'],str): raise ContractError('fixed prompt/parser required')
   positive(n['parameters']['max_new_tokens'],'fixed token count');model_slots.append(n['id'])
  elif n['op']=='numeric':
   exact(n['parameters'],{'code'},'fixed numeric slot')
   from .safe_python import validate_code
   validate_code(n['parameters']['code'])
  elif n['op']=='constant': exact(n['parameters'],{'value'},'constant')
  else: exact(n['parameters'],set(),'reference')
  seen.add(n['id'])
 if value['output'] not in seen: raise ContractError('fixed output must be a fixed node')
 if len(model_slots)>16: raise ContractError('F model graph exceeds event model call cap')
 return {'fixed_slots':[n['id'] for n in value['nodes']],'fixed_model_slots':model_slots,'source_sha256':digest(value)}
