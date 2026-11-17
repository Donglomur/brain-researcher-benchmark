"""Original failure custody independent of exception-defined attribute hooks.

Only actual local owners can transport occurrences. The identity registry holds
strong references for this control-plane lifetime; it is not a native capability
or a memory qualification. Exception attributes are never used as a channel.
"""
from dataclasses import dataclass
from .core import need
_RAISED_OWNERS={}

def describe(exc,owner):
 need(type(owner) is Custody,'actual diagnostic owner')
 event=next((x for x in owner.events if x.error is exc),None)
 need(event is not None,'raw error must already be owned before description')
 return dict(owner._describe(event))

@dataclass(frozen=True)
class Occurrence:
 owner:object
 index:int
 phase:str
 error:BaseException
 traceback:object
 effects:str
 diagnostic:bool=False

class Custody:
 """The actual owner survives publication; snapshots explicitly have cutoffs."""
 def __init__(self,name):
  self.name=name;self.events=[];self.owned=[];self.attempted=[];self.boundaries=[];self.publications=[];self._descriptions={};self.cost_observations=[]
 @property
 def first(self):return self.events[0].error if self.events else None
 def propagate(self,owner,phase):
  """Transport exact existing source occurrences; this is not a fresh catch."""
  need(type(owner) is Custody,'actual original custody owner')
  known={(id(x.owner),x.index):x for x in self.events}
  for x in tuple(owner.events):
   need(type(x) is Occurrence and type(x.owner) is Custody and 0<=x.index<len(x.owner.owned) and x.owner.owned[x.index] is x,'original owner/index occurrence, not matching fields')
   key=(id(x.owner),x.index)
   if key in known:need(known[key] is x,'no occurrence identity substitution')
   else:self.events.append(x);known[key]=x
   if key in owner._descriptions and key not in self._descriptions:self._descriptions[key]=dict(owner._descriptions[key])
  self.boundaries.append(phase)
  return owner.first
 def _append(self,exc,phase,effects,diagnostic=False):
  # Retain the actual raw object before even a traceback observation. No str,
  # getattr, setattr, equality, hash or user traceback method is invoked here.
  event=Occurrence(self,len(self.owned),phase,exc,None,effects,diagnostic)
  self.owned.append(event);self.events.append(event);self.boundaries.append(phase)
  return event
 def _diagnostic(self,exc,phase):
  event=self._append(exc,phase,'unknown',True)
  # Diagnostics are not recursively rendered or observed: one finite failure
  # cannot generate an unbounded sequence of new diagnostic operations.
  self._descriptions[(id(self),event.index)]={'type':'BaseException','message':'diagnostic failed; original raw object retained'}
  try:
   tb=BaseException.__traceback__.__get__(exc,BaseException)
   object.__setattr__(event,'traceback',tb)
  except BaseException as fallback:
   # One final raw fallback only: no recursive traceback or text observation.
   tail=self._append(fallback,phase+':diagnostic_traceback','unknown',True)
   self._descriptions[(id(self),tail.index)]={'type':'BaseException','message':'diagnostic traceback unavailable; raw fallback retained'}
  return event
 def capture(self,exc,phase,effects='unknown'):
  """Fresh catches always get new indexes, even when raw identity is reused.

  Source-owned earlier raised custody is causal ancestry, imported once. Use
  propagate for transport of an existing occurrence without a fresh catch.
  """
  need(isinstance(exc,BaseException),'actual exception object')
  prior=_RAISED_OWNERS.get(id(exc))
  if prior is not None and prior[0] is exc and prior[1] is not self:
   self.propagate(prior[1],phase+':prior_custody')
  event=self._append(exc,phase,effects)
  try:
   tb=BaseException.__traceback__.__get__(exc,BaseException)
   object.__setattr__(event,'traceback',tb)
  except BaseException as diagnostic:self._diagnostic(diagnostic,phase+':traceback_observation')
  return exc
 def attempt(self,name,call,*,effects='unknown'):
  need(name not in self.attempted,'cleanup/publication is one-shot: '+name)
  self.attempted.append(name)
  try:return True,call()
  except BaseException as exc:self.capture(exc,name,effects);return False,None
 def publish(self,name,call):
  self.publications.append({'phase':name,'event_cutoff':len(self.events)})
  return self.attempt(name,call)
 def _describe(self,event):
  key=(id(event.owner),event.index)
  if event.diagnostic and key not in self._descriptions:
   self._descriptions[key]={'type':'BaseException','message':'diagnostic failed; original raw object retained'}
  if key not in self._descriptions:
   # Install a finite fallback before rendering. A rendering failure is owned
   # by this actual observing custody, after the original, and never retried.
   result={'type':'BaseException','message':'exception message unavailable'}
   self._descriptions[key]=result
   try:result['type']=type.__getattribute__(type(event.error),'__name__')
   except BaseException as diagnostic:self._diagnostic(diagnostic,'diagnostic_type:'+event.phase)
   try:result['message']=str(event.error)
   except BaseException as diagnostic:self._diagnostic(diagnostic,'diagnostic_message:'+event.phase)
  return self._descriptions[key]
 def snapshot(self):
  # Iterate the fixed incoming cutoff; diagnostics appended during this pass
  # already have nonrecursive source-owned fallback descriptions.
  for event in tuple(self.events):self._describe(event)
  rows=[{'ordinal':i,'phase':x.phase,**self._descriptions[(id(x.owner),x.index)],'effects':x.effects} for i,x in enumerate(self.events)]
  return {'owner':self.name,'first_error':dict(self._descriptions[(id(self.events[0].owner),self.events[0].index)]) if self.events else None,
   'errors':rows,'attempted':list(self.attempted),'boundaries':list(self.boundaries),
   'publication_cutoffs':[dict(x) for x in self.publications],
   'post_publication_tail':[{'after':x['phase'],'errors_since':len(self.events)-x['event_cutoff']} for x in self.publications],
   'unknown_effects':any(x.effects=='unknown' for x in self.events)}
 def raise_first(self):
  if self.events:
   first=self.events[0]
   self.attach()
   # Fixed base descriptor bypasses an exception subclass's with_traceback
   # and __setattr__. The fallback still raises the original if restoration
   # itself cannot complete; that observed failure is retained separately.
   try:BaseException.with_traceback(first.error,first.traceback)
   except BaseException as diagnostic:self._diagnostic(diagnostic,'traceback_restore')
   raise first.error
 def attach(self):
  # Historical method name retained for CompletionSlot API compatibility.
  # No attribute is read from or written to the raw exception.
  if self.first is not None:_RAISED_OWNERS[id(self.first)]=(self.first,self)
  return self

def failure_snapshot(exc,phase='consumer',owner=None):
 view=Custody(phase)
 if owner is None:view.capture(exc,phase)
 else:
  need(type(owner) is Custody and any(x.error is exc for x in owner.events),'actual failure owner for a documentary projection')
  view.propagate(owner,phase)
 result=view.snapshot()
 if owner is not None:owner.propagate(view,phase+':diagnostic_tail')
 return result

@dataclass
class CostObservation:
 """Documentary observation owned by the actual Costs and Custody, not authority.

 The prefix precedes the one report call. Failure leaves the wall/operation
 observation unavailable; none of the known counters is reset or recharged.
 """
 cost:object
 owner:Custody
 phase:str
 prefix:object=None
 value:object=None
 returned:bool=False
 def document(self):
  if self.returned:return dict(self.value)
  return {**(self.prefix or {}),'wall_seconds':None,'operations':None,
   'physical_io_cpu_rss':'UNKNOWN','observation_status':'unavailable',
   'observation_phase':self.phase,'unknown_suffix':True,
   'known_prefix_cutoff':'before the sole failed report attempt',
   'prefix_available':self.prefix is not None}

def observe_costs(cost,owner,phase):
 """One original-owner report attempt; retain its record before observation."""
 from .core import Costs
 need(type(cost) is Costs and type(owner) is Custody,'actual cost and custody owners')
 observation=CostObservation(cost,owner,phase)
 owner.cost_observations.append(observation)
 def capture():
  observation.prefix={'logical_read_bytes':cost.read,'logical_write_bytes':cost.write,
   'unreleased_read_reservation':cost.reserved_read,'unreleased_write_reservation':cost.reserved_write}
  return cost.report()
 observation.returned,observation.value=owner.attempt(phase,capture)
 return observation
