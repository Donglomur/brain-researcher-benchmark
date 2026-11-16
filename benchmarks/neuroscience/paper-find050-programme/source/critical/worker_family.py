"""Earlier worker-family custody, not a native allocator or qualification grant.

The source scope must be entered before any worker issuance. Every returned
worker stays in this original family until one explicit run transfer and one
retirement attempt. Engineering owners can exercise custody only; NativeProducer
still rejects them before any native issuer or source entry.
"""
from .core import Costs,need
from .lifecycle import Custody
_FAMILIES={}

class EngineeringFamilyOwner:
 def __init__(self):
  self.source_sha256='engineering-only';self.calls=[];self.reference_families=[]
 def require(self,phase,source):
  need(source==self.source_sha256 and phase.startswith('reference_'),'engineering owner cannot authorize native/data/scoring work')
  self.calls.append(phase)

class WorkerSlot:
 def __init__(self,family,operation):
  self.family=family;self.operation=operation;self.worker=None;self.returned=False
  self.producer=None;self.state='awaiting_issuance';self.issuer_called=False
  self.retirement_attempted=False;self.retirement_completed=False;self.alias_of=None
  self.custody=Custody('reference_worker:'+operation);self.cost_prefixes=[]

 def register_issued(self,worker):
  # Fixed live issuer handoff: retain an acquired owner before another fallible
  # issuer action. This slot supplies custody, never a native execution grant.
  self.family.require_open()
  need(self.issuer_called,'actual entered issuer, not prospective worker metadata')
  self.family.own_returned(self,worker)
  return worker

class WorkerFamily:
 def __init__(self,authority,design,cost):
  self.authority=authority;self.design=design;self.cost=cost
  self.custody=Custody('reference_worker_family');self.slots=[];self.cost_prefixes=[]
  self.entered=False;self.exited=False;self.retired=False;self.assembly=None;self.result=None
  from .sandbox import QualifiedHost
  need(type(authority) in (QualifiedHost,EngineeringFamilyOwner) and type(cost) is Costs,'original typed family and cost owners')
  self.domain='engineering_only' if type(authority) is EngineeringFamilyOwner else 'native_reference'
  # QualifiedHost creates this registry at original issuance, not from JSON.
  need(type(authority.reference_families) is list,'original host family registry')
  authority.reference_families.append(self);_FAMILIES[id(self)]=(self,authority,cost)
 def __enter__(self):
  need(not self.entered and not self.exited,'family scope cannot be retried')
  self.entered=True
  try:
   self.authority.require('reference_family',self.authority.source_sha256)
   self.record_cost('before_issuance');self.custody.raise_first()
  except BaseException as exc:
   try:self.custody.capture(exc,'family_entry')
   finally:
    try:self.retire_all()
    finally:self.exited=True
   self.custody.raise_first()
  return self
 def __exit__(self,typ,exc,tb):
  try:
   if exc is not None:self.custody.capture(exc,'family_body')
  finally:
   try:self.retire_all()
   finally:self.exited=True
  self.custody.raise_first()
  return False
 def require_open(self):
  r=_FAMILIES.get(id(self))
  need(r is not None and r[0] is self and r[1] is self.authority and r[2] is self.cost and any(x is self for x in self.authority.reference_families),'same original family registry')
  need(self.entered and not self.exited and not self.retired,'entered original family lifetime')
 def record_cost(self,phase,slot=None):
  owner=self.custody if slot is None else slot.custody
  target=self.cost_prefixes if slot is None else slot.cost_prefixes
  ok,prefix=owner.attempt('cost:'+phase,self.cost.report)
  target.append({'phase':phase,'known_prefix':prefix if ok else None,'observation_succeeded':ok,'native_effects':'UNKNOWN'})
 def begin_issue(self,operation):
  self.require_open();need(self.custody.first is None,'failed family cannot issue more workers')
  need(type(operation) is str and operation and not any(s.operation==operation for s in self.slots),'one issuance attempt per operation')
  slot=WorkerSlot(self,operation);self.slots.append(slot)
  self.record_cost('before_issue',slot);slot.custody.raise_first();return slot
 def require_slot(self,slot):
  need(type(slot) is WorkerSlot and slot.family is self and any(s is slot for s in self.slots),'actual same-family issuance slot')
 def own_returned(self,slot,worker):
  self.require_slot(slot);need(not slot.returned and not slot.retirement_attempted,'one original issuer return')
  slot.worker=worker;slot.returned=True;slot.state='family_owned'
  prior=next((s for s in self.slots if s is not slot and s.returned and s.worker is worker),None)
  if prior is not None:slot.alias_of=prior
  need(prior is None,'distinct worker per original issuance; repeated worker is retained as an alias and never closed twice')
 def retain_unexpected_return(self,slot,worker):
  # A malformed issuer can return a different owner after registering one.
  # Retain both under the original family; this is cleanup custody only,
  # never a new scientific operation or another permission to issue work.
  self.require_slot(slot)
  extra=WorkerSlot(self,slot.operation+':unexpected_issuer_return')
  extra.parent_slot=slot;extra.issuer_called=True;self.slots.append(extra)
  self.own_returned(extra,worker)
  return extra
 def bind(self,slot,producer):
  self.require_open();self.require_slot(slot)
  need(slot.returned and slot.state=='family_owned' and slot.producer is None,'returned worker remains owned before source binding')
  need(producer.family is self and producer.slot is slot and producer.worker is slot.worker,'original producer/slot/worker join')
  slot.producer=producer
 def transfer(self,producer):
  self.require_open();slot=producer.slot;self.require_slot(slot)
  need(slot.producer is producer and producer.family is self and slot.state=='family_owned' and not slot.retirement_attempted,'one identity-bound transfer into original run')
  slot.state='run_owned';return slot
 def retire(self,slot):
  self.require_slot(slot)
  if slot.retirement_attempted:return
  slot.retirement_attempted=True;slot.state='retirement_attempted'
  # Failed issuance before a returned owner has unknown native effects; no
  # fabricated worker, assumed success or uncertain retry is introduced.
  if slot.alias_of is not None:
   self.retire(slot.alias_of)
   slot.state='alias_retired_once';slot.retirement_completed=slot.alias_of.retirement_completed
  elif slot.returned:
   def close_original():
    close=getattr(slot.worker,'close',None)
    need(callable(close),'returned worker lacks required independent close')
    return close()
   ok,_=slot.custody.attempt('worker_close',close_original)
   slot.retirement_completed=ok;slot.state='retired' if ok else 'retirement_failed_unknown'
  else:slot.state='no_returned_owner_unknown' if slot.issuer_called else 'not_issued'
  self.record_cost('after_retirement',slot)
  self.custody.propagate(slot.custody,'worker_retirement:'+slot.operation)
 def retire_all(self):
  if self.retired:return
  self.retired=True
  for slot in self.slots:
   # Each distinct slot is attempted even if a previous close or cost tail fails.
   try:self.retire(slot)
   except BaseException as exc:self.custody.capture(exc,'family_retirement_guard:'+slot.operation)
  self.record_cost('after_family_retirement')
 def snapshot(self):
  workers=[]
  for s in self.slots:
   observed=s.custody.snapshot()
   self.custody.propagate(s.custody,'worker_snapshot:'+s.operation)
   workers.append({'operation':s.operation,'state':s.state,'issuer_called':s.issuer_called,'worker_returned':s.returned,
    'retirement_attempted':s.retirement_attempted,'retirement_completed':s.retirement_completed,
    'cost_prefixes':list(s.cost_prefixes),'failure_custody':observed})
  return {'domain':self.domain,'entered':self.entered,'exited':self.exited,'retired':self.retired,
   'failure_custody':self.custody.snapshot(),'cost_prefixes':list(self.cost_prefixes),'workers':workers,
   'native_consumption':'UNKNOWN; this custody does not qualify or refund the original native owner'}
