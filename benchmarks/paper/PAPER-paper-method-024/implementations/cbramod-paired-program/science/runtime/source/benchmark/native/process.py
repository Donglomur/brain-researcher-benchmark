"""Finite subprocess lifecycle with explicit unknown closure on cleanup failure.

The same monotonic deadline bounds all waits, including cleanup. OS syscall
latency itself is not controlled here. No unbounded wait, and no child starts in
source-only controls. All partial Popen/selector states enter cleanup.
Known closure covers the direct child and owned handles only; descendant-tree
closure and OS/cgroup isolation remain explicitly unqualified.
"""
import math,os,selectors,signal,subprocess,time
from pathlib import Path

def need(ok,msg):
 if not ok:raise ValueError(msg)
def run_process(argv,cwd,timeout_seconds,maximum_log_bytes,log_path=None,env=None):
 need(not isinstance(timeout_seconds,bool)and isinstance(timeout_seconds,(int,float))and math.isfinite(timeout_seconds)and timeout_seconds>0,'positive finite timeout')
 need(type(maximum_log_bytes)is int and 1<=maximum_log_bytes<=64*1024*1024,'positive bounded log allocation')
 started=time.monotonic();deadline=started+timeout_seconds;proc=None;selector=None;sink=None;first=None;trace=None;data=bytearray();count=0
 cleanup={'closure_scope':'direct_child_and_owned_handles','descendant_tree_closure_verified':False,'child_started':False,'exit_observed':False,'closure_known':False,'errors':[]}
 try:
  if log_path is not None:sink=Path(log_path).open('xb')
  proc=subprocess.Popen(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True,env=env)
  cleanup['child_started']=True
  selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
  while selector.get_map():
   remaining=deadline-time.monotonic();need(remaining>0,'continuous native process deadline')
   for key,_ in selector.select(min(.1,remaining)):
    chunk=os.read(key.fileobj.fileno(),65536)
    if not chunk:selector.unregister(key.fileobj);continue
    need(count+len(chunk)<=maximum_log_bytes,'native log allocation exceeded')
    if sink is None:data.extend(chunk)
    else:sink.write(chunk)
    count+=len(chunk)
  code=proc.wait(timeout=max(0.,deadline-time.monotonic()));cleanup['exit_observed']=True
  need(time.monotonic()<=deadline,'native completion deadline');need(code==0,'native process nonzero exit')
  if sink is not None:sink.flush();os.fsync(sink.fileno())
 except BaseException as exc:
  first=exc;trace=exc.__traceback__
  if proc is not None:
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   except BaseException as error:cleanup['errors'].append('kill: '+repr(error))
   try:proc.wait(timeout=max(0.,deadline-time.monotonic()));cleanup['exit_observed']=True
   except BaseException as error:cleanup['errors'].append('bounded wait: '+repr(error))
 finally:
  for name,obj in [('selector',selector),('stdout',getattr(proc,'stdout',None)),('log',sink)]:
   if obj is not None:
    try:obj.close()
    except BaseException as error:cleanup['errors'].append(name+' close: '+repr(error))
  cleanup['closure_known']=(not cleanup['child_started']or cleanup['exit_observed'])and not cleanup['errors']
 if first is not None:
  first.native_process_cleanup=cleanup
  if hasattr(first,'add_note'):first.add_note('Native process cleanup: '+repr(cleanup))
  raise first.with_traceback(trace)
 if not cleanup['closure_known']:
  error=RuntimeError('native direct-child/owned-handle closure unknown');error.native_process_cleanup=cleanup;raise error
 return {'returncode':code,'log':bytes(data),'log_bytes':count,'elapsed_seconds':time.monotonic()-started,'cleanup':cleanup}
