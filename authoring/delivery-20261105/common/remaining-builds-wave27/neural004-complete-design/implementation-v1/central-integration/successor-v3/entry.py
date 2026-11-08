"""Registered complete NEURAL-004 observer; source alone grants no execution."""
import time
ORIGIN_NS=time.monotonic_ns()
ORIGIN=ORIGIN_NS/1e9
import signal
INITIAL_HANDLERS={s:signal.getsignal(s)for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
CLOCK_OWNED=False
FINAL_END=ORIGIN+120

def expired(*_):raise TimeoutError('Original NEURAL-004 central clock')
def cleanup_clock(primary=None):
 first=primary
 actions=[lambda:signal.setitimer(signal.ITIMER_REAL,0)]+[lambda s=s,h=h:signal.signal(s,h)for s,h in INITIAL_HANDLERS.items()]
 for action in actions:
  try:action()
  except BaseException as extra:
   if first is None:first=extra
   else:first.add_note('Independent timer cleanup failure: '+type(extra).__name__)
 if primary is None and first is not None:raise first

def startup():
 global CLOCK_OWNED
 if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('Fresh inactive central timer')
 try:
  for s in INITIAL_HANDLERS:signal.signal(s,expired)
  remaining=ORIGIN+120-time.monotonic()
  if remaining<=0:raise TimeoutError('Original startup exhausted')
  signal.setitimer(signal.ITIMER_REAL,remaining);CLOCK_OWNED=True
 except BaseException as error:cleanup_clock(error);raise
if __name__=='__main__':startup()

import argparse,hashlib,os,resource,stat,sys,types
from pathlib import Path
HERE=Path(__file__).absolute().parent
REL='authoring/delivery-20261105/common/remaining-builds-wave27/neural004-complete-design/implementation-v1/central-integration/successor-v3'
IO_PIN={'bytes': 11967, 'sha256': '60751688732dcbc426e0b1290e17fe90c2af95ce027ce8a541df06c79efa04e7'}
ADMISSION_PIN={'bytes': 15484, 'sha256': '6af9561feafb77c19b6f8065a89a1a8e30acd975145011d9f70af51713166f25'}
LOADER_PIN={'bytes': 2007, 'sha256': 'a56fa8c33eddddc8d8a91b69a43b1f4632f8e7b407d32befe1ad82d426b03cd3'}
BINDINGS_PIN={'bytes': 29368, 'sha256': '4f16634647c0f4289778f723e4cc2dc8f0c12e387bf79dc3f27a436c0560e2d3'}
BOOT_READ=0

def boot(path,expected):
 global BOOT_READ
 if not(type(expected)is dict and type(expected['bytes'])is int and 0<expected['bytes']<=1048576):raise ValueError('Bounded exact source bootstrap')
 BOOT_READ+=expected['bytes']+1
 path=Path(path).absolute()
 if any(p.is_symlink()for p in (path,*path.parents)):raise ValueError('Ordinary bootstrap source')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);primary=None
 try:
  a=os.fstat(fd)
  if not(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==expected['bytes']):raise ValueError('Exact source bootstrap extent')
  with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(expected['bytes']+1)
  b=os.fstat(fd);named=path.lstat();keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
  if not(len(raw)==expected['bytes']and hashlib.sha256(raw).hexdigest()==expected['sha256']and all(getattr(a,k)==getattr(b,k)==getattr(named,k)for k in keys)):raise ValueError('Stable exact source bootstrap')
  if time.monotonic()>=ORIGIN+120:raise TimeoutError('Original source bootstrap cutoff')
  return raw
 except BaseException as error:primary=error;raise
 finally:
  try:os.close(fd)
  except BaseException as extra:
   if primary is None:raise
   primary.add_note('Bootstrap close failure: '+type(extra).__name__)

def module(name,path,raw):
 if name in sys.modules:raise ValueError('Fresh exact bootstrap namespace')
 m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
 try:exec(compile(raw,str(path),'exec'),m.__dict__)
 except BaseException:sys.modules.pop(name,None);raise
 return m

def failure(primary,io,stage,output=None,cap=8192,known=None):
 ci=sys.modules.get('central_io')
 if ci is None:
  primary.add_note('NEURAL004 bootstrap failure; original source charge='+str(BOOT_READ)+'; no worker launched');return
 record=ci.failure_record(primary,stage,{'bootstrap_source_reads':BOOT_READ}if io is None else io.snapshot(),known)
 if output is not None:
  try:
   raw=ci.encoded(record);ci.need(len(raw)<=cap,'Complete central failure receipt');io.save(output/'INCOMPLETE.json',raw);primary.neural004_failure_retained=True;return
  except BaseException as extra:ci.cleanup_note(primary,'central invalidation publication',extra)
 try:ci.stderr_failure(record,FINAL_END,cap)
 except BaseException as extra:ci.cleanup_note(primary,'central failure stream',extra)
 primary.neural004_failure_retained=True

def invoke(io,bound,q,ad,loader):
 global FINAL_END
 ci=sys.modules['central_io'];p=bound['profile'];clock=bound['original_clock'];repo=bound['repository'];out=bound['output'];captured=None;observed=None;result=None;primary=None
 FINAL_END=clock['outer_ns']/1e9
 try:
  io.end=FINAL_END;io.read_cap=ad.SOURCE_CAP+ad.GATE_CAP+p['entry_read_bytes'];io.write_cap=p['entry_write_bytes'];io.retained_cap=p['entry_retained_bytes']
  ci.need(time.monotonic_ns()<clock['scientific_ns'],'No science-start deadline extension');signal.setitimer(signal.ITIMER_REAL,FINAL_END-time.monotonic())
  soft,hard=resource.getrlimit(resource.RLIMIT_AS);ci.need(hard==resource.RLIM_INFINITY or hard>=max(p['entry_memory_bytes'],p['worker_memory_bytes']),'Whole inherited host memory hierarchy')
  resource.setrlimit(resource.RLIMIT_AS,(p['entry_memory_bytes'],hard))
  fs=os.statvfs(out.parent);ci.need(fs.f_bavail*fs.f_frsize>=p['aggregate_retained_bytes']+bound['other']+p['disk_floor_bytes'],'Full selected programme and unrelated retention before publication')
  captured=loader.Captured('_n004_central_entry',HERE,q['own']).install();checker=captured.module('receipt_check')
  checker.hash_file(io,p['worker_python']['path'],{k:p['worker_python'][k]for k in ('bytes','sha256')},p['worker_python']['bytes'])
  io.directories(out);ad.current_routes(io,repo,q)
  observed=captured.module('observer').observe(io,bound,q)
  original=checker.validate(io,bound,q,observed)
  for n,raw in q['own'].items():ci.need(io.capture(HERE/n,ci.pin(raw),1048576)==raw,'Unchanged complete captured central source')
  for n,raw in q['parent'].items():ci.need(io.capture(repo/q['bindings']['parent_root']/n,ci.pin(raw),1048576)==raw,'Unchanged complete fixed parent')
  for path,d in q['bindings']['external_sources'].items():checker.hash_file(io,repo/path,d,max(d['bytes'],1))
  for path,raw in ((bound['operation_path'],bound['operation_raw']),(bound['config_path'],bound['config_raw']),(bound['review_path'],bound['review_raw'])):ci.need(io.capture(path,ci.pin(raw),max(len(raw),1))==raw,'Unchanged original operation/config/selection')
  ad.current_routes(io,repo,q)
  result={'schema':'neural004_central_observed_v1','task':'NEURAL-004','status':'complete_original_programme_observed'if original['all_phases_completed']else'original_programme_incomplete_observed',
   'source_manifest_pin':q['source_manifest_pin'],'source_freeze_pin':q['source_freeze_pin'],'parent_manifest_pin':q['parent_manifest_pin'],
   'operation_pin':bound['operation_pin'],'config_body_pin':bound['config_body_pin'],'central_selection_pin':bound['review_pin'],
   'original_clock':clock,'worker_close_pin':observed['close_pin'],'worker_return_pin':observed['worker_return_pin'],'original_stream_pins':observed['logs'],
   'original':original,'observer_costs':observed['observer_costs'],'entry_costs_before_final_publication':io.snapshot(),
   'new_metric_computed':False,'actual_entry_exit_known':False,'provisional_until_original_natural_entry_exit':True,
   'independent_transitive_custody_still_required':True,'automatic_retry':False,'runtime_or_scientific_qualification_inferred':False}
  raw=ci.encoded(result);ci.need(len(raw)<=p['receipt_bytes'],'Complete original central receipt');io.save(out/'OBSERVED.json',raw);io.tick()
 except BaseException as error:
  primary=error;failure(error,io,'complete_original_invoke',out,p['receipt_bytes'],{'worker_close_pin':None if observed is None else observed['close_pin'],'worker_return_pin':None if observed is None else observed['worker_return_pin'],'original_stream_pins':None if observed is None else observed['logs'],'observer_errors':None if observed is None else observed['errors'],'worker_failure':None if observed is None else observed['worker_failure'],'result_status_before_failure':None if result is None else result['status']});raise
 finally:
  if captured is not None:
   try:captured.close()
   except BaseException as extra:
    if primary is not None:ci.cleanup_note(primary,'captured central close',extra)
    else:
     failure(extra,io,'entry_source_cleanup',out,p['receipt_bytes']);raise
 io.tick();return result

def main(argv=None):
 primary=None;io=None;bound=None
 try:
  if not CLOCK_OWNED:raise RuntimeError('Only original registered entry owns this clock')
  ci=module('central_io',HERE/'central_io.py',boot(HERE/'central_io.py',IO_PIN))
  ad=module('_n004_admission',HERE/'admission.py',boot(HERE/'admission.py',ADMISSION_PIN))
  loader=module('_n004_loader',HERE/'source_loader.py',boot(HERE/'source_loader.py',LOADER_PIN));bindings=ci.parse(boot(HERE/'BINDINGS.json',BINDINGS_PIN))
  io=ci.IO(ad.SOURCE_CAP+ad.GATE_CAP,8*1048576,8*1048576,ORIGIN,ORIGIN+120);io.reads=BOOT_READ
  repo=Path.cwd().absolute();ci.need(HERE==repo/REL,'Actual fixed central source address')
  q=ad.stable_source(io,repo,bindings)
  parser=argparse.ArgumentParser(allow_abbrev=False)
  for name in ('program','review','output'):parser.add_argument('--'+name,required=True)
  parser.add_argument('--other-reserve-bytes',type=int,required=True);args=parser.parse_args(argv)
  bound=ad.bind(io,repo,args.program,args.review,args.output,args.other_reserve_bytes,q,ORIGIN_NS)
  invoke(io,bound,q,ad,loader);return 0
 except BaseException as error:
  primary=error
  if not getattr(error,'neural004_failure_retained',False):failure(error,io,'entry_admission',None if bound is None else bound['output'],8192 if bound is None else bound['profile']['receipt_bytes'])
  raise
 finally:
  if CLOCK_OWNED:
   try:cleanup_clock(primary)
   except BaseException as extra:
    failure(extra,io,'entry_timer_cleanup',None if bound is None else bound['output'],8192 if bound is None else bound['profile']['receipt_bytes']);raise
if __name__=='__main__':
 code=main()
 if time.monotonic()>=FINAL_END:raise TimeoutError('Original final entry return after all cleanup')
 raise SystemExit(code)
