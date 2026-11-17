"""Source-owned native worker/capture join.

native_worker implements transport conditional on an original qualified lease.
Neither a copied record, plan nor engineering owner issues that qualification.
Local child captures and retired remote captures have distinct identity owners.
"""
from dataclasses import dataclass
import os
from .core import *
from .lifecycle import Custody
_PRODUCERS={};_CAPTURES={}

@dataclass(frozen=True)
class CapturedOperation:
 body:bytes
 producer:object
 worker:object

class EngineeringCaptureOwner:
 """Inert capture custody only. Never accepted as a NativeProducer/host."""
 pass

class CaptureCustody:
 """Actual source capture owner shared by native composition and inert checks."""
 def __init__(self,producer,context,worker,operation):
  need(type(producer) in (NativeProducer,EngineeringCaptureOwner),'typed capture owner')
  self.producer=producer;self.context=context;self.worker=worker;self.operation=operation;self.active=False;self.used=False;self.capture=None
 def enter(self,context,operation):
  need(context is self.context and operation==self.operation and not self.used,'one selected context/operation entry')
  self.used=True;self.active=True
 def seal(self,context,operation,row):
  need(self.active and context is self.context and operation==self.operation and self.capture is None,'same active capture path; no replay or substituted context')
  p=CapturedOperation(encode(row),self.producer,self.worker);_CAPTURES[id(p)]=(p,self.producer,self.worker);self.capture=p;return p
 def leave(self):self.active=False
 def admit(self,p):
  need(p is self.capture and _CAPTURES.get(id(p),(None,))[0] is p and p.producer is self.producer and p.worker is self.worker,'actual capture object and original producer/worker')
  return p

class NativeProducer:
 def __init__(self,*a,**k):raise Refusal('source-issued native producer required')
 @classmethod
 def issue(cls,host,context,operation,bindings,design,*,family):
  from .worker_family import WorkerFamily
  need(type(family) is WorkerFamily and family.authority is host and family.domain=='native_reference','actual earlier native worker family; engineering or preissued dictionary forbidden')
  slot=family.begin_issue(operation);custody=slot.custody
  try:
   from .sandbox import QualifiedHost
   from .native_context import NativeContext
   need(type(host) is QualifiedHost and type(context) is NativeContext and context.authority is host,'original actual host and selected native context')
   host.require('reference_worker_issuance:'+operation,host.source_sha256)
   plan=context.plan(operation,bindings);frozen=encode(plan);bb=encode(bindings)
   need(bindings['operation']==operation and pin(frozen)['sha256']==bindings['native_plan_sha256'],'operation and frozen complete native plan')
   selected={'operation':operation,'source_sha256':host.source_sha256,'design_sha256':design['design_sha256'],
    'programme_sha256':design['programme_sha256'],'plan':pin(frozen),'bindings':pin(bb),
    'source_entrypoint':'critical.native.original_call','capture_entrypoint':'critical.native_context.NativeContext.capture_original_result'}
   issuer=getattr(host.lease,'issue_reference_worker',None)
   need(callable(issuer),'missing qualified native worker issuer')
   slot.issuer_called=True
   worker=issuer(host,context,selected,slot)
   if not slot.returned:
    # Retain a legacy/malformed return for cleanup, then refuse its missing
    # earlier issuer registration instead of granting native authority.
    family.own_returned(slot,worker)
    need(False,'issuer must register acquired worker on the original slot before fallible continuation')
   if slot.worker is not worker:family.retain_unexpected_return(slot,worker)
   need(slot.worker is worker,'same earlier registered issued worker return')
   need(not isinstance(worker,(dict,str,bytes,Path)),'actual issued worker owner')
   for key in ('require','dispatch','close'):need(callable(getattr(worker,key,None)),'complete issued worker lifecycle')
   obj=object.__new__(cls);obj.host=host;obj.context=context;obj.operation=operation;obj.bindings=bb;obj.plan=frozen;obj.selected=encode(selected);obj.worker=worker
   obj.family=family;obj.slot=slot;obj.used=False;obj.active=False;obj.capture=None;obj.custody=custody
   obj.capture_owner=CaptureCustody(obj,context,worker,operation)
   worker.require('issuance',host,obj,selected)
   _PRODUCERS[id(obj)]=(obj,host,context,worker,obj.selected)
   family.bind(slot,obj)
  except BaseException as exc:
   try:custody.capture(exc,'native_worker_issuance')
   finally:family.retire(slot)
   family.custody.propagate(custody,'failed_worker_issuance:'+operation);custody.raise_first()
  return obj
 def check(self,host,operation,bindings,design):
  selected=_PRODUCERS.get(id(self))
  need(selected is not None and selected[0] is self and selected[1] is host and selected[2] is self.context and selected[3] is self.worker,'actual issued producer/host/context/worker identity')
  need(host is self.host and self.context.authority is host and operation==self.operation and encode(bindings)==self.bindings,'selected original host/operation/bindings')
  need(getattr(host,'native_context',None) is self.context,'original host still owns this exact selected context')
  need(encode(self.context.plans[operation])==self.plan,'native plan unchanged since issuance')
  doc=decode(selected[4]);need(doc['source_sha256']==host.source_sha256 and doc['design_sha256']==design['design_sha256'] and doc['programme_sha256']==design['programme_sha256'],'frozen source and design identity')
  self.worker.require('before_dispatch',host,self,doc)
 def execute_in_selected_worker(self):
  """The fixed source entry called by the live dispatch owner, never a callback."""
  self.family.require_open()
  need(self.slot.producer is self and self.slot.state=='run_owned' and not self.slot.retirement_attempted,'actual transferred worker still in live run; no post-retirement entry')
  need(self.used and not self.active and self.capture is None,'one actual native source entry')
  doc=decode(self.selected)
  self.worker.require('inside_selected_process:'+str(os.getpid()),self.host,self,doc)
  self.host.require('inside_native_reference_worker:'+self.operation,self.host.source_sha256)
  need(getattr(self.host,'native_context',None) is self.context,'same original host context at the source entry')
  need(getattr(self.context,'active_producer',None) is None,'no nested/native producer substitution')
  self.capture_owner.enter(self.context,self.operation)
  self.active=True;self.context.active_producer=self
  try:
   from .native import original_call
   returned=original_call(self.operation,decode(self.bindings),self.host,self.context.cost)
   need(returned is self.capture and _CAPTURES.get(id(returned),(None,))[0] is returned,'fixed source path returned its own capture')
   return returned
  finally:
   self.capture_owner.leave();self.context.active_producer=None;self.active=False
 def seal_capture(self,context,operation,row):
  self.family.require_open()
  need(self.slot.state=='run_owned' and not self.slot.retirement_attempted,'capture before original worker retirement')
  need(self.active and context is self.context and context.active_producer is self and operation==self.operation and self.capture is None,'capture belongs to active actual selected source invocation')
  self.worker.require('capture',self.host,self,decode(self.selected))
  p=self.capture_owner.seal(context,operation,row);self.capture=p;return p
 def run(self,host,operation,bindings,design):
  result=None
  try:
   self.family.transfer(self) # same earlier owner; failures still retire below
   need(not self.used,'native producer is one-use');self.used=True
   self.check(host,operation,bindings,design)
   result=self.worker.dispatch(self)
   need(result is self.capture,'same dispatched capture')
   from .native_worker import RemoteCapturedOperation
   if type(result) is RemoteCapturedOperation:self.worker.admit_capture(result)
   else:self.capture_owner.admit(result)
   self.worker.require('after_capture',host,self,decode(self.selected))
  except BaseException as exc:self.custody.capture(exc,'native_producer_body')
  finally:self.family.retire(self.slot)
  self.custody.raise_first()
  return result
 def row(self,capture):
  from .native_worker import RemoteCapturedOperation
  if type(capture) is RemoteCapturedOperation:self.worker.admit_capture(capture)
  else:need(capture is self.capture and _CAPTURES.get(id(capture),(None,))[0] is capture,'same sealed capture')
  return decode(capture.body)
