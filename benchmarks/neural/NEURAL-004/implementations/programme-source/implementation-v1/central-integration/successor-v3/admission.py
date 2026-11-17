"""Actual shared campaign qualification and exact complete source admission."""
import os,sys,types,math
from pathlib import Path
from central_io import need,parse,encoded,pin,descriptor,ordinary
TASK='NEURAL-004'
REL='authoring/delivery-20261105/common/remaining-builds-wave27/neural004-complete-design/implementation-v1/central-integration/successor-v3'
TARGET='benchmarks/neuroscience/neural-004/manifest.json'
CONDITION='full26_retrospective_signal_and_reconstruction_v1'
SOURCE_CAP=16*1024**2
GATE_CAP=256*1024**2
PROFILE_FIELDS=('schema','worker_python','worker_environment','startup_seconds','worker_finish_ns','entry_finish_ns','worker_grace_seconds',
 'worker_memory_bytes','worker_live_bytes','worker_read_bytes','worker_write_bytes','worker_retained_bytes','worker_return_bytes','worker_log_bytes',
 'observer_read_bytes','observer_write_bytes','observer_retained_bytes','entry_read_bytes','entry_write_bytes','entry_retained_bytes',
 'entry_memory_bytes','receipt_bytes','max_output_files','artifact_validation_read_bytes','artifact_max_bytes','aggregate_retained_bytes','disk_floor_bytes','birth_and_descendant_custody_admission','physical_accounting_admission')
def module(name,path,raw):
 need(name not in sys.modules,'Fresh fixed captured source module');m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
 try:exec(compile(raw,str(path),'exec'),m.__dict__)
 except BaseException:sys.modules.pop(name,None);raise
 return m

def stable_source(io,repo,b):
 need(b['task']==TASK and b['central_root']==REL,'Exact complete task source binding')
 tools={n:io.capture(repo/d['path'],{k:d[k]for k in ('bytes','sha256')},1048576)for n,d in b['central_tools'].items()}
 campaign=module('_n004_campaign',repo/b['central_tools']['neurobench_campaign.py']['path'],tools['neurobench_campaign.py'])
 gate=module('_n004_gate',repo/b['central_tools']['neurobench_campaign_gate.py']['path'],tools['neurobench_campaign_gate.py'])
 doc=parse(io.capture(repo/TARGET,cap=262144));need(doc.get('id')==TASK and doc.get('program_conditions')=={CONDITION:'default'},'Complete selected default/named interface')
 io.reads+=GATE_CAP;need(io.reads<=io.read_cap,'Central qualification checks prospectively reserved')
 need(campaign.verified_program_runtime(repo/TARGET,doc,repo),'No actual complete runtime qualification')
 entry,wrapper=campaign._program_entry(doc['program_execution'],repo);need(wrapper==repo/REL/'entry.py','Exact complete registered entry')
 workraw=io.capture(repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json',cap=2097152)
 routes=[gate.preferred_route(repo,TASK,'run',cond,pin(workraw)['sha256'],(repo/TARGET,doc))for cond in (None,CONDITION)]
 need(all(r['status']=='preferred_source_bound'and r['wrapper_absolute']==str(wrapper)for r in routes),'Both current complete preferred routes')
 freeze_d=doc['program_execution']['source_freeze'];raw=io.capture(repo/freeze_d['path'],{k:freeze_d[k]for k in ('bytes','sha256')},524288);freeze=parse(raw)
 smraw=io.capture(repo/REL/'SOURCE_MANIFEST.json',freeze['files'][REL+'/SOURCE_MANIFEST.json'],262144);sm=parse(smraw)
 need(sm['schema']=='neural004_central_source_v1'and set(sm['files'])==set(b['own_members']),'Exact complete central member roster')
 own={}
 for name,d in sm['files'].items():
  need(freeze['files'].get(REL+'/'+name)==d,'Every central source in independent qualification');own[name]=io.capture(repo/REL/name,d,1048576)
 pm=b['parent_manifest'];pmraw=io.capture(repo/pm['path'],{k:pm[k]for k in ('bytes','sha256')},262144);parent_manifest=parse(pmraw)
 parent={}
 need(parent_manifest['files']==b['parent_members']and len(parent_manifest['files'])==46,'Complete46 effective parent, no helper substitution')
 for row in parent_manifest['files']:
  path=b['parent_root']+'/'+row['path'];d={k:row[k]for k in ('bytes','sha256')};need(freeze['files'].get(path)==d,'Full effective parent source qualified');parent[row['path']]=io.capture(repo/path,d,1048576)
 need(freeze['files'].get(pm['path'])==pin(pmraw),'Effective parent manifest qualified')
 for path,d in b['external_sources'].items():need(freeze['files'].get(path)==d,'All original/dependency sources in qualified closure')
 for d in b['central_tools'].values():need(freeze['files'].get(d['path'])=={k:d[k]for k in ('bytes','sha256')},'Same shared campaign implementation')
 verification=doc['program_execution']['verification'];qp=repo/verification['qualification_path']
 qraw=io.capture(qp,{'bytes':qp.stat().st_size,'sha256':verification['qualification_sha256']},2097152);qualification=parse(qraw)
 return {'bindings':b,'own':own,'parent':parent,'parent_manifest_pin':pin(pmraw),'source_manifest_pin':pin(smraw),'source_freeze_pin':pin(raw),
  'qualification_pin':pin(qraw),'profile':qualification.get('neural004_complete_central_profile'),'registered':doc,'work_pin':pin(workraw),'campaign':campaign,'gate':gate}

def current_routes(io,repo,q):
 raw=io.capture(repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json',q['work_pin'],2097152)
 io.reads+=32*1024**2;need(io.reads<=io.read_cap,'Current route reread charge')
 for condition in (None,CONDITION):
  r=q['gate'].preferred_route(repo,TASK,'run',condition,pin(raw)['sha256'],(repo/TARGET,q['registered']))
  need(r['status']=='preferred_source_bound'and r['wrapper_absolute']==str(repo/REL/'entry.py'),'Unchanged qualified preferred route')
 io.tick()

def bind(io,repo,program,review,output,other,q,entry_origin_ns):
 need(type(other)is int and other>=0,'Exact unrelated reservation')
 rraw=io.capture(review,cap=32768);r=parse(rraw)
 need(set(r)=={'schema','task','selected','bundle','work','output','other_future_bytes','source_manifest_pin','source_freeze_pin','qualification_pin','profile','private_operator_custody','actual_complete_work_authorized','higher_caller_natural_exit_required'},'Exact independent central review')
 need(r['schema']=='neural004_central_selection_v1'and r['task']==TASK and all(r[k]is True for k in ('selected','private_operator_custody','actual_complete_work_authorized','higher_caller_natural_exit_required')),'No scientific authority inferred from construction source')
 need(r['source_manifest_pin']==q['source_manifest_pin']and r['source_freeze_pin']==q['source_freeze_pin']and r['qualification_pin']==q['qualification_pin'],'Current exact source/runtime authority')
 out=ordinary(output);need(out==ordinary(r['output'])and not os.path.lexists(out)and out.parent.is_dir(),'Fresh private complete output')
 for key in ('bundle','work'):descriptor(r[key],2097152,True)
 need(ordinary(program)==ordinary(r['bundle']['path'])and ordinary(r['work']['path'])==repo/'authoring/delivery-20261105/WORK_ASSIGNMENTS.json','Exact selected bundle and current work')
 wraw=io.capture(r['work']['path'],{k:r['work'][k]for k in ('bytes','sha256')},2097152);w=parse(wraw)
 need(pin(wraw)==q['work_pin']and w['latest_construction_state']['global_future_bytes']==r['other_future_bytes']==other,'Current complete unrelated reservation')
 braw=io.capture(program,{k:r['bundle'][k]for k in ('bytes','sha256')},2097152);b=parse(braw)
 need(set(b)=={'schema','task','operation','config'}and b['schema']=='neural004_complete_central_bundle_v1'and b['task']==TASK,'Complete original operation/config bundle')
 docs={};raws={}
 for key in ('operation','config'):
  descriptor(b[key],16*1048576,True);need(not ordinary(b[key]['path']).is_relative_to(out),'Original inputs outside fresh results')
  raws[key]=io.capture(b[key]['path'],{k:b[key][k]for k in ('bytes','sha256')},16*1048576);docs[key]=parse(raws[key])
 op=docs['operation'];config=docs['config'];need(set(op)=={'schema','task','config_pin','channel','provider_deployments','original_root','source_roster','hmp_environment','hmp_limits','reference_budget','request_scientific_qualification'},'Exact complete operation fields')
 need(op['schema']=='neural004_complete_operation_v1'and op['task']==TASK and op['config_pin']==pin(raws['config']),'Exact original config identity')
 need(type(op['request_scientific_qualification'])is bool,'Explicit optional independent scientific review')
 # Parent expects canonical JSON identity, not pretty on-disk bytes.
 canonical_config_pin=pin(encoded(config));need(b['config']['sha256']==pin(raws['config'])['sha256'],'Config source body pinned')
 p=r['profile'];need(type(p)is dict and set(p)==set(PROFILE_FIELDS)and p==q['profile']and p['schema']=='neural004_complete_central_profile_v1','Same qualified finite complete profile')
 for key in PROFILE_FIELDS:
  if key not in ('schema','worker_python','worker_environment','birth_and_descendant_custody_admission','physical_accounting_admission'):need(type(p[key])is int and p[key]>=(0 if key=='disk_floor_bytes'else 1),'Finite profile extent '+key)
 for key in ('birth_and_descendant_custody_admission','physical_accounting_admission'):descriptor(p[key])
 descriptor(p['worker_python'],104857600,True);need(ordinary(p['worker_python']['path']).is_file(),'Qualified executable path')
 descriptor(p['worker_environment'],4*1048576,True);envraw=io.capture(p['worker_environment']['path'],{k:p['worker_environment'][k]for k in ('bytes','sha256')},4*1048576);environment=parse(envraw)
 need(set(environment)=={'schema','selected','python','import_roots','import_inventory','runtime_admission_pin'}and environment['schema']=='neural004_qualified_worker_environment_v1'and environment['selected']is True and environment['python']==p['worker_python'],'Separately qualified actual interpreter/import environment')
 descriptor(environment['runtime_admission_pin']);need(type(environment['import_roots'])is list and environment['import_roots'],'Exact qualified package roots')
 for root in environment['import_roots']:need(ordinary(root).is_dir(),'Admitted ordinary import root')
 need(type(environment['import_inventory'])is dict and environment['import_inventory'],'Complete separately reviewed library/source inventory')
 clock=config['clock'];need(set(clock)=={'origin_ns','scientific_ns','closeout_ns','outer_ns'}and all(type(x)is int for x in clock.values()),'Original complete nanosecond clock')
 need(0<=clock['origin_ns']<=entry_origin_ns<clock['scientific_ns']<clock['closeout_ns']<clock['outer_ns'],'Original operation predates entry and retains science/closeout windows')
 need(clock['closeout_ns']+p['worker_finish_ns']+p['worker_grace_seconds']*10**9+p['entry_finish_ns']<clock['outer_ns'],'Complete parent closeout plus observer and entry finish windows')
 need(p['startup_seconds']==120 and io.tick()*1e9<min(entry_origin_ns+120*10**9,clock['scientific_ns']),'Original startup admission window')
 need(config['source_root']==str(repo/q['bindings']['parent_root'])and config['runtime_sources']==q['bindings']['parent_members'],'Exact full fixed effective parent root/roster')
 source_pin=pin(encoded({r['path']:{k:r[k]for k in ('bytes','sha256')}for r in q['bindings']['parent_members']}))
 need(config['source_pin']==source_pin and op['channel']['source_pin']==source_pin and op['channel']['run_id']==config['run_id'],'Same exact runtime digest throughout independent channels')
 need(config['body_root']==str(out/'parent-bodies')and op['hmp_limits']['output_root']==str(out/'hmp-private'),'Private fresh source-owned output roots')
 need(config['body_cap']>=op['channel']['max_message_bytes']+8,'Complete authority framing/failure prefix retention')
 need(p['worker_read_bytes']>=p['worker_python']['bytes'],'Actual executable authentication allocation')
 need(op['reference_budget']['original_origin']==clock['origin_ns']/1e9 and op['reference_budget']['deadline']==clock['scientific_ns']/1e9,'Original reference scientific interval')
 # Source-derived full attempt maxima: no resource cap silently reduces folds.
 prediction_names=[m+'/'+v for m in ('P','I')for v in ('B','E','H','EH')]
 predicted_jobs=sum(26*config['policies'][name]['limits']['tools']for name in prediction_names)
 all_jobs=predicted_jobs+sum(26*config['policies']['reconstruction/'+m]['limits']['tools']for m in ('P','I'))
 need(op['channel']['max_requests']>=798+predicted_jobs,'Full original authority/credential/closure request programme')
 transport=config['transport'];traw=io.capture(transport['deployment_path'],transport['deployment_pin'],65536);td=parse(traw)
 need(type(td['max_message_bytes'])is int and td['max_message_bytes']>0,'Complete actual transport response cap')
 known_record_upper=2*td['max_message_bytes']+config['job_limits']['index_bytes']+32768
 complete_return_upper=p['max_output_files']*2048+all_jobs*known_record_upper+op['channel']['max_requests']*2048+2*1048576
 need(p['worker_return_bytes']>=max(config['body_cap'],complete_return_upper) and p['receipt_bytes']>=p['worker_return_bytes']+2*p['max_output_files']*2048+131072,'Full actual records/inventories/exchange history capacity before work')
 imported_bytes=sum(d['bytes']+1 for d in environment['import_inventory'].values())
 need(p['worker_read_bytes']>=2*imported_bytes+p['worker_python']['bytes'],'All qualified dependency before/after checks are reserved')
 minimum=sum(len(v)+1 for v in q['own'].values())+sum(len(v)+1 for v in q['parent'].values())+len(raws['operation'])+len(raws['config'])+len(envraw)+3
 bootstrap_reads=len(q['own']['central_io.py'])+len(q['own']['source_loader.py'])+2+65537
 need(p['worker_read_bytes']>=bootstrap_reads+2*minimum+2*imported_bytes+p['worker_python']['bytes'] and p['worker_write_bytes']>=3*p['worker_return_bytes']+128*1024 and p['worker_retained_bytes']>=2*p['worker_return_bytes']+128*1024,'Complete source recapture, journal and invalidation reserves')
 need(p['worker_log_bytes']>=16384 and p['observer_read_bytes']>=4162+(p['worker_log_bytes']+3)*min(65536,p['worker_log_bytes']+1),'Worst fragmented observer request extent')
 observer_retention=2*p['worker_log_bytes']+64*262144+p['worker_return_bytes']
 need(p['observer_write_bytes']>=observer_retention and p['observer_retained_bytes']>=observer_retention,'Full original observer events, streams and close retention')
 need(p['artifact_validation_read_bytes']>=config['logical_limits']['retained_bytes']+op['hmp_limits']['retained_bytes']and p['artifact_max_bytes']>=max(config['body_cap'],op['hmp_limits']['live_bytes']),'Complete actual parent/HMP artifact validation reserve')
 central_join_reads=2*p['worker_return_bytes']+2*p['worker_log_bytes']+64*262144+2*p['max_output_files']+128
 need(p['entry_read_bytes']>=central_join_reads+2*32*1024**2+2*minimum+8*p['receipt_bytes']+p['artifact_validation_read_bytes']+p['worker_python']['bytes'] and p['entry_write_bytes']>=3*p['receipt_bytes'] and p['entry_retained_bytes']>=2*p['receipt_bytes'],'Complete source/route/phase/observer/artifact joins and failure retention reserves')
 need(p['aggregate_retained_bytes']>=config['logical_limits']['retained_bytes']+p['worker_retained_bytes']+p['observer_retained_bytes']+p['entry_retained_bytes']+op['hmp_limits']['retained_bytes'],'Full original plus central retention reservation')
 return {'operation':op,'config':config,'operation_pin':pin(raws['operation']),'config_body_pin':pin(raws['config']),'canonical_config_pin':canonical_config_pin,
  'operation_path':b['operation']['path'],'config_path':b['config']['path'],'operation_raw':raws['operation'],'config_raw':raws['config'],
  'review_path':str(ordinary(review)),'review_pin':pin(rraw),'review_raw':rraw,'environment':environment,'environment_raw':envraw,
  'profile':p,'output':out,'other':other,'repository':repo,'parent_manifest_pin':q['parent_manifest_pin'],'original_clock':clock}
