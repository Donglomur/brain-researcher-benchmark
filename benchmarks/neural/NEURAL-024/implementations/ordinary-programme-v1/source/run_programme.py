"""One operator-admitted programme against the existing original NEURAL-024 case.

Run only inside an operator-owned staged source workspace under the separately
selected external785sTERM+5sKILL watchdog and serialized resource reservation.
"""
import argparse,os,signal,sys,time,hashlib,stat,importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
HERE=ROOT/'authoring/rtt-neural-forecast-v1/causal-runtime-v1'
sys.path.insert(0,str(HERE))
ADMISSION_SOURCE_PIN={'bytes':7450,'sha256':'a381537a4cac8ed9f5c76cc3fe4d0c01e32586db1eb61e292346af30f7ac989c'}
def bootstrap_admission():
 path=HERE/'programme_admission.py'
 if any(p.is_symlink()for p in(path,*path.parents)):raise ValueError('unlinked admission bootstrap')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode)or before.st_nlink!=1 or before.st_size!=ADMISSION_SOURCE_PIN['bytes']:raise ValueError('fixed admission bootstrap extent')
  with os.fdopen(fd,'rb',closefd=False)as stream:body=stream.read(ADMISSION_SOURCE_PIN['bytes']+1)
  after=os.fstat(fd)
  stamp=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns,v.st_nlink)
  if stamp(before)!=stamp(after)or stamp(after)!=stamp(path.lstat())or len(body)!=ADMISSION_SOURCE_PIN['bytes']or hashlib.sha256(body).hexdigest()!=ADMISSION_SOURCE_PIN['sha256']:raise ValueError('exact unchanged admission bootstrap bytes')
 finally:os.close(fd)
 spec=importlib.util.spec_from_file_location('programme_admission',path);value=importlib.util.module_from_spec(spec)
 sys.modules['programme_admission']=value;exec(compile(body,str(path),'exec'),value.__dict__);return value
admission=bootstrap_admission()
from programme_admission import need,canonical,pin,strict,meta
STAGE='startup'
WHOLE=780
WORK=720
CLEANUP=60

def await_child(owner, process, folder, end, clock=time.monotonic, sleep=time.sleep):
    completion = Path(folder) / 'process_completion.json'
    while clock() < end:
        if completion.exists():
            value = owner.read(completion)
            saved = owner.read(Path(folder) / 'process_owner.json')
            need(value.get('token') == saved['token'] and type(value.get('returncode')) is int,
                 'exact completed trusted child token')
            return value
        if process.poll() is not None:
            return {'returncode': None, 'watchdog_ended_before_completion': True}
        sleep(min(.05, max(0, end - clock())))
    return {'returncode': None, 'native_deadline_reached': True}

def emit_failure(error,output=None):
    output=sys.stderr if output is None else output
    try:message=str(error)[:96]
    except BaseException:message='unprintable exception'
    kind=type(error).__name__[:48]
    body=canonical({'schema':'neural024-fixed-control-driver-failure/v1','stage':STAGE,
        'error_type':kind,'message':message,'qualified':False})
    if len(body)>2048:body=canonical({'schema':'neural024-fixed-control-driver-failure/v1','stage':'unknown','error_type':'unrepresentable','qualified':False})
    try:
        text=body.decode('ascii');need(output.write(text)==len(text),'complete diagnostic output');output.flush();return True
    except BaseException:return False

def setup_environment(chosen,path,sha):
 for key in tuple(os.environ):
  if key.startswith('DOCKER_')or key.startswith('NEURAL024_'):os.environ.pop(key,None)
 os.environ['NEURAL024_DOCKER_HOST']=chosen['docker_host']
 os.environ['NEURAL024_OPERATION_ADMISSION']=str(path)
 os.environ['NEURAL024_OPERATION_ADMISSION_SHA256']=sha
 for key in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','OMP_THREAD_LIMIT','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[key]='1'
 os.environ['PYTHONDONTWRITEBYTECODE']='1'

def finish_control(common,recovery,owner,process,run,work_end,whole_end,launch_error=None):
 completion=None;native_error=launch_error
 if process is not None:
  try:completion=await_child(owner,process,run/'controller',work_end)
  except BaseException as exc:native_error=type(exc).__name__
 try:stopped=owner.stop(run/'controller',whole_end-5,proc=process)
 except BaseException as exc:stopped={'absence_verified':False,'error_type':type(exc).__name__}
 rows=[];cleanup_error=None
 try:
  need(stopped.get('absence_verified')is True,'owned group absent before exact container recovery')
  budget=common.HostBudget(run,110000000,6000000)
  rows=recovery.recover_all(run,common.Engine(whole_end-3,run,budget),budget)
  need(all(x['absence_verified']for x in rows)and not any(x.get('evidence_retention_failed',False)for x in rows),'known container absence and complete retained evidence')
 except BaseException as exc:cleanup_error=type(exc).__name__
 return {'completion':completion,'native_error':native_error,'group_stop':stopped,'container_recovery':rows,'cleanup_error':cleanup_error}

def qualification(mode,outcome,child):
 need(mode in('ordinary','calibration_rate'),'selected operation mode')
 need(outcome['native_error']is None and outcome['cleanup_error']is None and(outcome['completion']or{}).get('returncode')==0
  and outcome['group_stop'].get('absence_verified')is True,'clean trusted controller and group closure')
 need(len(outcome['container_recovery'])==2 and all(x['absence_verified']for x in outcome['container_recovery']),'exact candidate/grade container closure')
 need(child.get('status')=='scored'and child.get('protocol_complete')is True and child.get('candidate_chronology_verified')is True
  and child.get('committed_prediction_count')==22100 and child.get('private_grader_dispatched')is True and child.get('new_reference_fits')==0
  and child.get('model_api_calls_by_controller')==0 and child.get('prepared_inputs_recomputed')is False and child.get('operation_mode')==mode,'complete unchanged causal evaluation path')
 if mode=='ordinary':
  need(child.get('control_checks')is None and child.get('ordinary_scored_without_accuracy_floor')is True
   and child.get('candidate_fit_count')is None and child.get('candidate_authorship')=='unknown'
   and child.get('candidate_training_policy_verified')is False,'ordinary scoring preserves unmeasured training/authorship and has no control accuracy floor')
 else:
  c=child.get('control_checks')or{}
  need(child.get('candidate_fit_count')==0 and child.get('candidate_authorship')=='disclosed_fixed_control'
   and c.get('passed')is True and c.get('label')=='calibration_rate'and c.get('calibration_rate_control',{}).get('exact_parity')is True
   and c.get('calibration_rate_control',{}).get('zero_primary_gain')is True,'exact fixed-control parity/zero gain')
 return True

def main():
 global STAGE
 parser=argparse.ArgumentParser();parser.add_argument('--admission',type=Path,required=True);parser.add_argument('--admission-sha256',required=True);args=parser.parse_args()
 start=time.monotonic();work_end=start+WORK;whole_end=start+WHOLE
 def interrupted(signum,frame):raise TimeoutError('original whole-operation deadline/interruption')
 for sig in(signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,interrupted)
 need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'no inherited timer');signal.setitimer(signal.ITIMER_REAL,WHOLE)
 STAGE='admission_and_source_closure'
 chosen=admission.read_admission(args.admission,args.admission_sha256)
 closure=admission.source_closure(chosen);admission.runtime_identity(chosen)
 programme=admission.selected_programme(chosen)
 run=Path(chosen['run']);need(not run.exists()and all(not p.is_symlink()for p in(run,*run.parents)),'one fresh owned run')
 config=ROOT/'.cache-build/docker-config';need(not config.parent.exists(),'fresh independent staged source workspace')
 setup_environment(chosen,args.admission,args.admission_sha256)
 # Scientific, runtime and custody dependencies import only after closure authentication.
 import common
 import rtt_recovery as recovery
 from prepared_binding import packet
 packet() # Metadata only; authentic body reads remain after durable source commitment.
 STAGE='source_commitment'
 run.mkdir(parents=True,mode=0o700);(run/'controller').mkdir(mode=0o700)
 config.mkdir(parents=True,mode=0o700)
 with(config/'config.json').open('xb')as f:f.write(b'{}\n');f.flush();os.fsync(f.fileno())
 budget=common.HostBudget(run,110000000,6000000)
 for name,body in programme.items():
  budget.write(run/name,body,mode=0o444)
  fd=os.open(run/name,os.O_RDONLY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
 common.sync(run)
 commitment={'mode':chosen['mode'],'programme':pin(programme['program.py']),'method':pin(programme['method.json']),
  'before_candidate_activation':True,'before_first_request':True,'historical_preparation_preceded_commitment':True}
 common.save(run/'source_commit.json',commitment,budget,32768)
 control=HERE/'prepared_control.py';relative=str(control.relative_to(ROOT));descriptor={'path':relative,**closure['files'][relative]}
 need(work_end-time.monotonic()>=680,'full original candidate and grader time windows')
 STAGE='owned_activation_and_cleanup';process=None;launch_error=None;outcome=None
 try:process=common.owner.launch([sys.executable,str(control),'--run',str(run),'--deadline',str(work_end)],run/'controller',min(720.,work_end-time.monotonic()+.1),descriptor)
 except BaseException as exc:launch_error=type(exc).__name__
 finally:outcome=finish_control(common,recovery,common.owner,process,run,work_end,whole_end,launch_error)
 STAGE='stopped_result_validation';child=None;child_pin=None;error=None;qualified=False;score_summary=None
 try:
  b=meta(run/'result.json',131072);child=strict(b);child_pin=pin(b);qualified=qualification(chosen['mode'],outcome,child)
  score_raw=meta(run/'grade/output/score.json',131072,child['score']);receipt_raw=meta(run/'grade/output/grade_receipt.json',65536,child['grade_receipt'])
  score=strict(score_raw);need(score['status']=='scored'and score['complete_scored_panel']is True and score['support']['cells']==2120640
    and score['support']['rows']==22090 and score['support']['channels']==96 and score['support']['reference_arms_verified']==6,'complete original score support')
  score_summary={'score_pin':pin(score_raw),'grade_receipt_pin':pin(receipt_raw),'primary_bits_per_spike_gain':score['bits_per_spike_vs_calibration_rate'],
    'primary_comparison':score['comparisons']['calibration_rate'],'support':score['support'],'signed_gain_preserved':True}
 except BaseException as exc:error=type(exc).__name__;qualified=False
 result={'schema':'neural024-programme-operation-result/v1','status':('ordinary_programme_scored_pending_outer_exit'if chosen['mode']=='ordinary'else'fixed_calibration_control_verified_pending_outer_exit')if qualified else'failed_or_incomplete',
  'mode':chosen['mode'],'admission_sha256':args.admission_sha256,'source_manifest_pin':chosen['source_manifest_pin'],
  'programme_pin':commitment['programme'],'method_pin':commitment['method'],'outcome':outcome,'error_type':error,
  'child_result':{'path':str(run/'result.json'),'pin':child_pin,'status':child.get('status')if child else None},'score':score_summary,
  'candidate_fit_count':0 if chosen['mode']=='calibration_rate'else None,'candidate_authorship':'disclosed_fixed_control'if chosen['mode']=='calibration_rate'else'unknown',
  'method_training_policy_is_declaration_only':chosen['mode']=='ordinary','host_controller_model_api_calls':0,'new_reference_fits':0,
  'whole_benchmark_ready':False,'native_neural_understanding_claim':False,'outer_group_absence_still_requires_operator':True,'wall_seconds':time.monotonic()-start}
 need(time.monotonic()<whole_end,'result inside780second operation limit');common.save(run/'operation_result.json',result,budget,131072)
 signal.setitimer(signal.ITIMER_REAL,0);return 0 if qualified else 2

if __name__=='__main__':
 try:raise SystemExit(main())
 except BaseException as exc:
  if isinstance(exc,SystemExit):raise
  emit_failure(exc);raise SystemExit(2)
