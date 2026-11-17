"""Actual observed lifecycle and streamed exact original artifact joins."""
import hashlib,os,stat
from pathlib import Path
from central_io import need,pin,parse,encoded,ordinary,cleanup_note

def hash_file(io,path,expected,cap,*,unindexed=False):
 path=ordinary(path);need(not unindexed or expected['sha256']is None,'Only explicitly unindexed incomplete artifacts omit prior hash');need(type(expected['bytes'])is int and 0<=expected['bytes']<=cap,'Artifact extent before allocation')
 io.tick();io.reads+=expected['bytes']+1;need(io.reads<=io.read_cap,'Complete streamed artifact charge before read')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
 try:
  a=os.fstat(fd);need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==expected['bytes'],'Ordinary exact artifact extent')
  h=hashlib.sha256();total=0
  while total<=expected['bytes']:
   io.tick();block=os.read(fd,min(65536,expected['bytes']+1-total))
   if not block:break
   total+=len(block);h.update(block)
  b=os.fstat(fd);named=path.lstat();keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
  need(total==expected['bytes']and (unindexed or h.hexdigest()==expected['sha256'])and all(getattr(a,k)==getattr(b,k)==getattr(named,k)for k in keys),'Complete stable exact artifact identity')
 except BaseException as error:primary=error;raise
 finally:
  try:os.close(fd)
  except BaseException as extra:
   if primary is None:raise
   cleanup_note(primary,'artifact close',extra)
 io.tick();return {'bytes':total,'sha256':h.hexdigest()}

def inventory(io,root,expected,cap):
 need(len(expected)<=cap,'Declared complete file count');seen=set()
 stream=os.scandir(root);primary=None
 try:
  for entry in stream:
   io.tick();need(len(seen)<cap and entry.name in expected and not entry.is_symlink()and entry.is_file(follow_symlinks=False),'Only complete source-owned ordinary artifacts')
   seen.add(entry.name)
 except BaseException as error:primary=error;raise
 finally:
  try:stream.close()
  except BaseException as extra:
   if primary is None:raise
   cleanup_note(primary,'artifact inventory close',extra)
 need(seen==set(expected),'Exact retained artifact inventory')

def root_inventory(io,root,files,directories):
 """Exact bounded original root; final entry receipt is not published yet."""
 need(len(files)+len(directories)<=40,'Fixed central root artifact bound');seen=set();stream=os.scandir(root);primary=None
 try:
  for item in stream:
   io.tick();need(len(seen)<40 and item.name not in seen and not item.is_symlink(),'Ordinary bounded root artifact')
   need((item.name in files and item.is_file(follow_symlinks=False))or(item.name in directories and item.is_dir(follow_symlinks=False)),'Only exact source-owned root files/directories')
   seen.add(item.name)
 except BaseException as error:primary=error;raise
 finally:
  try:stream.close()
  except BaseException as extra:
   if primary is None:raise
   cleanup_note(primary,'root inventory close',extra)
 need(seen==set(files)|set(directories),'Complete exact original root roster');io.tick()

def unindexed_hmp(io,root,p):
 """Preserve failed partial output identity, never infer a completed HMP index."""
 result={};stream=os.scandir(root);primary=None
 try:
  for item in stream:
   io.tick();need(len(result)<p['max_output_files'] and not item.is_symlink()and item.is_file(follow_symlinks=False),'Bounded flat ordinary incomplete HMP outputs')
   st=item.stat(follow_symlinks=False);need(st.st_nlink==1,'Single-link incomplete HMP output')
   result[item.name]=hash_file(io,root/item.name,{'bytes':st.st_size,'sha256':None},p['artifact_max_bytes'],unindexed=True)
 except BaseException as error:primary=error;raise
 finally:
  try:stream.close()
  except BaseException as extra:
   if primary is None:raise
   cleanup_note(primary,'incomplete HMP inventory close',extra)
 return result

def central_artifacts(io,bound,observed,rows,hmp_present):
 """Join actual phase files, original return/close/streams and observer journal."""
 p=bound['profile'];root=bound['output'];files={}
 def capture(name,expected,cap):
  raw=io.capture(root/name,expected,cap);files[name]=expected;return raw
 for row in rows:
  start={'phase':row['phase'],'status':'blocked'if row['blocked_by']else'attempted','blocked_by':row['blocked_by'],'started_ns':row['started_ns']}
  for suffix,value in (('start',start),('end',row)):
   raw=encoded(value);need(len(raw)<=p['worker_return_bytes'],'Bounded complete phase record')
   name='phase-'+row['phase']+'-'+suffix+'.json';need(capture(name,pin(raw),p['worker_return_bytes'])==raw,'Exact original phase journal joins returned outcome')
 for name,value,expected in (('WORKER_RETURN.json',observed['worker_return'],observed['worker_return_pin']),('WORKER_CLOSE.json',observed['close'],observed['close_pin'])):
  raw=capture(name,expected,p['worker_return_bytes']);need(parse(raw)==value,'Original observed body equals retained bytes')
 for stream in ('stdout','stderr'):
  expected=observed['logs'][stream];need(expected==observed['close']['logs'][stream],'Original observer log identity')
  name='worker.'+stream+'.log';files[name]=hash_file(io,root/name,expected,p['worker_log_bytes'])
 events=observed['observer_events'];need(type(events)is list and len(events)<=64,'Complete bounded independent observer journal')
 journal={}
 for i,expected in enumerate(events):journal[str(i)+'.json']=hash_file(io,root/'observer-journal'/(str(i)+'.json'),expected,262144)
 inventory(io,root/'observer-journal',journal,64)
 directories={'parent-bodies','observer-journal'}
 if hmp_present:directories.add('hmp-private')
 root_inventory(io,root,files,directories)
 return {'root_files':files,'observer_journal':journal,'actual_phase_records_joined':30,'root_directories':sorted(directories)}

def validate(io,bound,q,observed):
 need(not observed['errors']and observed['worker_failure']is None,'Original worker/observer errors retained and cannot qualify')
 close=observed['close'];ret=observed['worker_return'];p=bound['profile'];clock=bound['original_clock']
 from .observer import argv_for
 expected_binding,expected_argv=argv_for(bound,q)
 need(observed['binding']==expected_binding and observed['argv']==expected_argv,'Reconstructed exact original qualified worker binding/argv')
 need(type(close)is dict and close['schema']=='neural065_independent_controller_close_v1','Exact reused independently owned observer record')
 need(type(close['exit_code'])is int and close['exit_code']==0 and close['natural_exit']is True and close['forced']is False and close['reaped']is True and close['process_group_absent']is True and not close['cleanup_errors']and close['error']is None,'Original natural worker exit/EOF/group closure')
 need(close['argv']==observed['argv']and close['caller_custody_claim']is False,'Same originally launched captured worker; no self-exit claim')
 need(close['origin']==observed['binding']['origin']and close['work_deadline']==observed['binding']['cutoff']and close['global_deadline']==observed['binding']['deadline']and close['finished']<close['work_deadline'],'Same original strict observer clocks')
 need(ret['schema']=='neural004_complete_worker_return_v1'and ret['task']=='NEURAL-004'and ret['operation_pin']==bound['operation_pin']and ret['config_pin']==bound['canonical_config_pin']and ret['parent_manifest_pin']==q['parent_manifest_pin']and ret['source_pin']==bound['config']['source_pin'],'Actual fixed original worker source/config/operation return')
 need(ret['original_clock']==clock and ret['actual_outer_exit_known']is False and ret['provisional_until_original_outer_observation']is True,'No circular worker exit promise')
 from .driver import PHASES
 need(ret['full_phase_roster']==list(PHASES)and [r['phase']for r in ret['phases']]==list(PHASES),'Complete original scientific/closure phase roster')
 for row in ret['phases']:need(row['status']in ('completed','failed','blocked')and type(row['started_ns'])is int and type(row['finished_ns'])is int and clock['origin_ns']<=row['started_ns']<=row['finished_ns']<clock['outer_ns'],'Honest original phase outcome/time')
 need(ret['all_phases_completed']==all(r['status']=='completed'for r in ret['phases']),'No suppressed failed phase')
 members=ret['parent_body_inventory'];need(type(members)is dict and len(members)<=p['max_output_files'],'Complete parent body inventory')
 root=bound['output']/'parent-bodies';validated={}
 for name,d in members.items():
  need(type(name)is str and Path(name).name==name and set(d)=={'path','bytes','sha256'}and d['path']==name,'Exact parent body descriptor')
  validated[name]=hash_file(io,root/name,{k:d[k]for k in ('bytes','sha256')},p['artifact_max_bytes'])
 inventory(io,root,members,p['max_output_files'])
 hmp_validated={};hmp_partial={};hroot=bound['output']/'hmp-private';hmp_present=os.path.lexists(hroot)
 if hmp_present:need(ordinary(hroot).is_dir(),'Ordinary private HMP output directory')
 if 'HMP_RESULT_INDEX.json'in members:
  result=parse(io.capture(root/'HMP_RESULT_INDEX.json',validated['HMP_RESULT_INDEX.json'],bound['config']['body_cap']))
  need(result['output_root']==str(bound['output']/'hmp-private'),'Same private HMP output realm');hd=result['index'];hroot=bound['output']/'hmp-private'
  need(Path(hd['name']).name==hd['name'],'Flat original HMP index')
  raw=io.capture(hroot/hd['name'],{k:hd[k]for k in ('bytes','sha256')},bound['operation']['hmp_limits']['metadata_bytes']);index=parse(raw)
  for d in index['artifacts_before_index']:
   name=d['name'];need(Path(name).name==name and name not in hmp_validated,'Unique flat original HMP artifact')
   hmp_validated[name]=hash_file(io,hroot/name,{k:d[k]for k in ('bytes','sha256')},p['artifact_max_bytes'])
  hmp_validated[hd['name']]={k:hd[k]for k in ('bytes','sha256')};inventory(io,hroot,hmp_validated,p['max_output_files'])
 elif hmp_present:hmp_partial=unindexed_hmp(io,hroot,p)
 complete=ret['all_phases_completed']
 if complete:need(all(n in members for n in ('HMP_RESULT_INDEX.json','REFERENCE_INDEX.json','PREDICTION_GRADE.json','RECONSTRUCTION_GRADE.json','SPATIAL_INDEX.json','REASONING_GRADE.json','STUDY_CLOSEOUT.json')),'Complete protected original grade/evidence artifacts')
 status=None
 if 'STUDY_CLOSEOUT.json'in members:status=parse(io.capture(root/'STUDY_CLOSEOUT.json',validated['STUDY_CLOSEOUT.json'],bound['config']['body_cap']))
 need(not complete or status is not None,'Original parent closeout retained')
 central=central_artifacts(io,bound,observed,ret['phases'],hmp_present);io.tick()
 return {'all_phases_completed':complete,'phase_outcomes':ret['phases'],'parent_artifacts':validated,'HMP_artifacts':hmp_validated,
  'incomplete_unindexed_HMP_artifacts':hmp_partial,'unindexed_artifacts_are_scientific_completion':False,'central_artifacts':central,
  'original_parent_closeout':status,'new_metric_computed':False,'original_grade_sources_unchanged':True,'actual_entry_exit_known':False,
  'higher_caller_natural_exit_still_required':True,'independent_transitive_custody_still_required':True}
