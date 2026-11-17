"""Full accepted scope and explicit participant/operator manifests."""
from pathlib import Path
from .common import require,exact_keys,identity,keyed,token,relative,integer,finite,load

TASK='PAPER-ROOT-ADD-018';CONDITIONS=('I_A','I_B','R_A','R_B')
FAMILIES=('R_BEH','R_INF','R_MUS','R_CELL','R_TCA','R_HLDS','R_NAIVE','R_ATI','R_DPR','R_BLOCK','I_NEURAL','I_WAIT','I_REWARD','I_SIM_ATI','I_ASSOCIATION','I_REAL_ATI')
PHASES=('build','investigate','fit','predict','analyze')
def design(root):
 root=Path(root);m=load(root/'RUNTIME_DESIGN_PINS.json');documents={}
 for name,pin in m['files'].items():relative(name);documents[name]=load(root/name,pin=pin)
 scope=documents['design/SCOPE_POLICY_BINDINGS.json'];require(scope['total_obligations']==74 and scope['cohort_roles']==20 and scope['original_simulations']==200 and scope['author_sources']==59,'scope changed')
 return documents
def submission(value):
 exact_keys(value,('schema','task_id','method_id','source_root','files','entrypoints','dependency_lock','seed_policy','declared_obligations'))
 require(value['schema']=='ofc-submission-v1'and value['task_id']==TASK,'submission version/task');token(value['method_id'])
 require(isinstance(value['files'],list),'source files required');files={}
 for row in value['files']:
  require(isinstance(row,dict)and 'path'in row,'source row');relative(row['path']);require(row['path']not in files,'duplicate source path');files[row['path']]=row
 require(0<len(files)<=512,'source file count')
 for path,pin in files.items():
  relative(path);exact_keys(pin,('path','bytes','sha256'));integer(pin['bytes']);require(isinstance(pin['sha256'],str)and len(pin['sha256'])==64,'source pin')
 require(set(value['entrypoints'])==set(PHASES),'all participant phases required')
 for phase,argv in value['entrypoints'].items():
  require(isinstance(argv,list)and argv and all(isinstance(x,str)and '\0'not in x for x in argv),'argv required')
  require(argv[0]in('python3','matlab','Rscript','julia','/build/program'),'declared environment runtime required')
  require('{request}'in argv and '{output}'in argv,'request/output protocol required')
  require(all('{'not in x or x in('{request}','{output}','{source}','{build}','{model}','{inputs}','{scratch}','{state}','{investigation}')for x in argv),'unknown argv placeholder')
 require(isinstance(value['dependency_lock'],dict)and isinstance(value['seed_policy'],dict),'explicit dependency and seed policy required')
 require(isinstance(value['declared_obligations'],list)and len(set(value['declared_obligations']))==74,'all74 obligations declared')
 return value
def budget(x):
 exact_keys(x,('wall_seconds','phase_seconds','output_bytes','scratch_bytes','file_count','log_bytes','source_bytes','input_bytes','request_limit','cpus','memory_bytes','pids','tmp_bytes'))
 for k in x:integer(x[k],1)
 require(x['phase_seconds']<=x['wall_seconds'],'phase exceeds full budget');return x
def plan(value,documents):
 exact_keys(value,('schema','task_id','experiment_id','condition','scope','budget','public_inputs','public_universes','native_requests','protected_commitment','dependency_environment','seed_manifest','qualification_id','reference_definitions','policy_id'))
 require(value['schema']=='ofc-plan-v1'and value['task_id']==TASK,'plan version/task');token(value['experiment_id']);require(value['condition']in CONDITIONS,'condition');budget(value['budget'])
 s=documents['design/SCOPE_POLICY_BINDINGS.json'];expected={'obligation_ids':[x['obligation_id']for x in s['obligations']],'role_ids':s['cohort_role_ids'],'family_ids':list(FAMILIES),'simulation_cases':200,'open_gate_ids':s['open_gates']}
 require(value['scope']==expected,'incomplete or changed whole scope')
 require(set(value['public_universes'])==set(f for f in FAMILIES if f.startswith('I_')),'all6 prospective universes required')
 for family,rows in value['public_universes'].items():
  stream_identity={}
  indexed=keyed(rows,'query_id');require(len(indexed)==len(rows),'query duplicate')
  require(rows,'full prospective support cannot be an empty family')
  for r in rows:
   exact_keys(r,('query_id','family_id','stream_id','public','public_input_ids','cutoff','group_keys'))
   require(r['family_id']==family,'query family mismatch');token(r['stream_id']);require(isinstance(r['public'],dict),'public payload object')
   require(isinstance(r['cutoff'],dict)and set(r['cutoff'])=={'trial_ordinal','bin_ordinal'},'cutoff schema')
   for v in r['cutoff'].values():integer(v)
   require(isinstance(r['public_input_ids'],list)and len(set(r['public_input_ids']))==len(r['public_input_ids']),'input identities')
   if family!='I_SIM_ATI':
    semantic=(r['group_keys']['rat'],r['group_keys']['session'],r['public']['target_unit']if family=='I_NEURAL'else None)
    if family=='I_NEURAL':require(r['group_keys']['unit']==r['public']['target_unit'],'held-unit score identity')
    require(r['stream_id']not in stream_identity or stream_identity[r['stream_id']]==semantic,'cross-target or cross-session mutable stream')
    stream_identity[r['stream_id']]=semantic
  if family=='I_SIM_ATI':require(len({r['group_keys']['case']for r in rows})==200,'all200simulation case identities required')
 require(set(keyed(value['native_requests'],'obligation_id'))==set(expected['obligation_ids']),'all74 native requests required')
 obligation_map={r['obligation_id']:r for r in s['obligations']}
 for row in value['native_requests']:
  exact_keys(row,('obligation_id','family_id','role_ids','component_roster','input_ids'))
  original=obligation_map[row['obligation_id']]
  require(row['family_id']=='R_'+original['family'],'native family mapping changed');require(set(row['role_ids'])==set(original['cohort_roles']),'native role support changed')
  require(isinstance(row['component_roster'],list)and row['component_roster'],'nonempty exact component roster required')
  keyed(row['component_roster'],'component_id')
 require(isinstance(value['protected_commitment'],str)and len(value['protected_commitment'])==64,'private commitment binding')
 require(isinstance(value['reference_definitions'],list),'reference definitions')
 require(isinstance(value['dependency_environment'],dict),'environment identity required')
 return value
def expected_rows(plan):
 if plan['condition'].startswith('I'):return [(f,r['query_id'])for f,rs in plan['public_universes'].items()for r in rs]
 return [(r['family_id'],r['obligation_id'])for r in plan['native_requests']]
