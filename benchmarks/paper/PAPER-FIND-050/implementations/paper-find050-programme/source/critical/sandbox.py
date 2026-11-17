"""Concrete process runner. Live deployment authority is an external qualification hold.

A matching record, PID, source pin, or JSON boolean cannot issue authority.
Only the live operator producer supplies a lease with revalidation/close methods.
The ordinary-source phase never creates such a lease or starts this runner.
"""
from dataclasses import dataclass
from pathlib import Path
import os,selectors,signal,subprocess,time
from .core import *
from .exposure import Exposure
from .lifecycle import Custody,observe_costs

_ISSUED={}
_CLOSED={}
def cleanup_process(process,poll,lifecycle,kill_group):
 """Actual independent process/selector/stream cleanup; inert OS leaves in tests."""
 if process is not None and lifecycle.first is not None:
  ok,state=lifecycle.attempt('cleanup_poll',process.poll)
  if not ok or state is None:
   def kill(sig):
    try:kill_group(process.pid,sig)
    except ProcessLookupError:pass
   lifecycle.attempt('terminate',lambda:kill(signal.SIGTERM))
   waited,_=lifecycle.attempt('wait_after_terminate',lambda:process.wait(timeout=5))
   if not waited:
    lifecycle.attempt('kill',lambda:kill(signal.SIGKILL))
    lifecycle.attempt('wait_after_kill',lambda:process.wait(timeout=5))
 if poll is not None:lifecycle.attempt('selector_close',poll.close)
 if process is not None:
  for label,stream in (('stdout',process.stdout),('stderr',process.stderr)):
   if stream is not None:lifecycle.attempt(label+'_close',stream.close)
@dataclass(frozen=True)
class ClosedRun:
 identifier:str
 exposure:Exposure
 returncode:int
 output_sha256:str
 output_bytes:int
 output_path:Path
 first_error:object
 costs:dict
 owner:object
 lifecycle:dict=None

class QualifiedHost:
 def __init__(self,*args,**kwargs):
  raise Refusal("Live operator issuance required; constructor cannot grant execution")
 @classmethod
 def from_live_operator(cls,issuer,request):
  # The issuer is a live, already reviewed object, never a candidate-provided import
  # or serialized declaration. Its source/lifecycle/native qualification is G21-24.
  need(not isinstance(issuer,(dict,str,bytes,Path)) and callable(getattr(issuer,"issue",None)),"live issuer object")
  lease=issuer.issue(request)
  custody=Custody('host_issuance')
  try:
   for name in ("require","terminal","close","native_plan"):
    need(callable(getattr(lease,name,None)),"complete live lease API")
   lease.require("admission",request["source_sha256"])
  except BaseException as exc:
   custody.capture(exc,'host_issuance')
   close=getattr(lease,'close',None)
   if callable(close):custody.attempt('unissued_lease_close',close)
   custody.raise_first()
  obj=object.__new__(cls);obj.lease=lease;obj.source_sha256=request["source_sha256"];obj.used=False;obj.closed=False;obj.reference_families=[]
  _ISSUED[id(obj)]=(obj,issuer,lease);return obj
 def require(self,phase,source_sha256):
  need(_ISSUED.get(id(self),(None,))[0] is self and not self.closed,"same live host owner")
  need(source_sha256==self.source_sha256,"source belongs to actual lease")
  self.lease.require(phase,source_sha256)
 def run(self,exposure,output,cost):
  self.output_cost=cost
  self.require("before_process",self.source_sha256);need(not self.used,"one-use launch authority");self.used=True
  need(type(exposure) is Exposure,"actual exposure producer")
  plan=self.lease.native_plan(exposure)
  exact(plan,("argv","cwd","env","timeout_seconds","stdout_cap","stderr_cap","result_cap","result_name","output_directory"),"qualified native launch plan")
  need(type(plan["argv"]) is list and all(type(x) is str and "\0" not in x for x in plan["argv"]),"literal no-shell launch")
  need(type(plan["timeout_seconds"]) in (int,float) and 0<plan["timeout_seconds"]<=604800,"finite wall bound")
  for k in ("stdout_cap","stderr_cap","result_cap"):need(type(plan[k]) is int and plan[k]>0,"finite stream/result bound")
  need(Path(plan["output_directory"]).absolute()==Path(output).absolute(),"same granted output root")
  relative(plan["result_name"]);out=ordinary(output);need(not out.exists(),"fresh output");out.mkdir(mode=0o700)
  process=None;poll=None;stdout=bytearray();stderr=bytearray();start=time.monotonic();rc=None;raw=None
  lifecycle=Custody('sandbox_run');self.run_custody=lifecycle
  try:
   self.require("immediately_before_spawn",self.source_sha256)
   process=subprocess.Popen(plan["argv"],cwd=plan["cwd"],env=plan["env"],stdin=subprocess.DEVNULL,
       stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,close_fds=True)
   self.lease.require("after_process_creation",self.source_sha256)
   poll=selectors.DefaultSelector()
   for stream,label in ((process.stdout,"stdout"),(process.stderr,"stderr")):
    os.set_blocking(stream.fileno(),False);poll.register(stream,selectors.EVENT_READ,label)
   while poll.get_map():
    need(time.monotonic()-start<plan["timeout_seconds"],"candidate wall limit")
    for key,_ in poll.select(timeout=min(.1,plan["timeout_seconds"])):
     block=os.read(key.fileobj.fileno(),65536)
     if not block:poll.unregister(key.fileobj);continue
     target=stdout if key.data=="stdout" else stderr;cap=plan[key.data+"_cap"]
     # Keep the exact known prefix and its length, including a bounded overflow.
     target.extend(block[:max(0,cap+1-len(target))]);need(len(target)<=cap,key.data+" limit")
   rc=process.wait(timeout=max(.1,plan["timeout_seconds"]-(time.monotonic()-start)))
   self.lease.require("after_process_exit",self.source_sha256)
   need(rc==0,"candidate nonzero exit")
   raw=read(out/plan["result_name"],plan["result_cap"],cost)
  except BaseException as exc:
   lifecycle.capture(exc,'sandbox_body')
  # Reap first; each independent cleanup is attempted even if a prior action
  # failed. A close is never retried; descriptor state after failure is unknown.
  cleanup_process(process,poll,lifecycle,os.killpg)
  return _finish_run(self,exposure,process,rc,raw,out/plan['result_name'],cost,lifecycle,stdout,stderr,start)
 def close(self):
  if not self.closed:
   self.closed=True
   lifecycle=Custody('host_close');self.close_custody=lifecycle
   for index,family in enumerate(self.reference_families):
    lifecycle.attempt('reference_family_retirement:'+str(index),family.retire_all)
    lifecycle.propagate(family.custody,'retained_reference_family:'+str(index))
   lifecycle.attempt('lease_close',self.lease.close);lifecycle.raise_first()

def _finish_run(host,exposure,process,rc,raw,result_path,cost,lifecycle,stdout,stderr,start):
 """Fixed post-cleanup tail of QualifiedHost.run; never a host issuer."""
 observation=observe_costs(cost,lifecycle,'terminal_cost_observation')
 receipt={'lifecycle':lifecycle.snapshot(),'costs':observation.document(),
  'stdout_bytes':len(stdout),'stderr_bytes':len(stderr),'returncode_known':rc,
  'process_created':process is not None,'unknown_descendant_effects':lifecycle.first is not None,
  'cutoff':'after process/selector/stream cleanup, before one terminal-publication attempt'}
 lifecycle.publish('terminal_publication',lambda:host.lease.terminal(receipt,bytes(stdout),bytes(stderr)))
 # Failure is propagated before any success-only construction. The same run
 # custody carries the cost observation and the terminal-publication tail.
 lifecycle.raise_first()
 final=observe_costs(cost,lifecycle,'closed_run_cost_observation')
 lifecycle.raise_first()
 def construct():
  return ClosedRun(str(process.pid)+":"+str(time.monotonic_ns()),exposure,rc,pin(raw)['sha256'],len(raw),result_path,None,
   {**final.document(),'stdout_bytes':len(stdout),'stderr_bytes':len(stderr),'process_wall_seconds':time.monotonic()-start},host,lifecycle.snapshot())
 ok,run=lifecycle.attempt('closed_run_construction',construct)
 lifecycle.raise_first()
 _CLOSED[id(run)]=(run,host)
 return run,raw

def actual_closed(run):
 actual=_CLOSED.get(id(run))
 need(type(run) is ClosedRun and actual is not None and actual[0] is run and actual[1] is run.owner,"same actual closed process object")
 return run
class TargetVault:
 def __init__(self,host,design_sha256,reference_path,reference_pin,cap,cost):
  need(type(host) is QualifiedHost,"operator host");self.host=host;self.design=design_sha256
  self.path=Path(reference_path);self.pin=reference_pin;self.cap=cap;self.cost=cost;self.used=set()
 def open_for(self,run,design):
  actual_closed(run);need(run.owner is self.host and run.identifier not in self.used,"same run target owner, one use")
  need(design["design_sha256"]==self.design,"same protected design")
  self.host.require("target_release_after_candidate_admission",self.host.source_sha256)
  self.used.add(run.identifier)
  return read(self.path,self.cap,self.cost,self.pin)
