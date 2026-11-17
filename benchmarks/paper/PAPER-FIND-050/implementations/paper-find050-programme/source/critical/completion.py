"""Actual post-close service outcome in the existing operator control plane.

This is a return channel, not native execution authority. A JSON reply or copied
receipt cannot stand in for it. The CLI alone has no issued slot. Deployments
must join the existing live operator's same-control-plane slot (or separately
qualify a custody-preserving transport); no such deployment is supplied here.
"""
from dataclasses import dataclass
import threading
from .core import *
from .lifecycle import Custody
_TRANSACTIONS={};_OUTCOMES={}

@dataclass(frozen=True)
class ServiceOutcome:
 transaction:object
 reply:bytes
 custody:Custody

class CompletionSlot:
 def __init__(self,hosts,dispatch):
  from .sandbox import QualifiedHost
  need(type(hosts) is tuple and hosts and all(type(h) is QualifiedHost for h in hosts),'existing actual hosts for completion custody')
  need(len({id(h) for h in hosts})==len(hosts),'distinct original hosts')
  for h in hosts:h.require('completion_slot',dispatch['source_sha256'])
  self.hosts=hosts;self.dispatch=encode(dispatch);self.transaction=None;self.outcome=None;self.taken=False;self.ready=threading.Event()
 def begin(self,hosts,dispatch,custody):
  need(self.transaction is None and tuple(hosts)==self.hosts and all(a is b for a,b in zip(hosts,self.hosts)) and encode(dispatch)==self.dispatch,'same original host family and one selected dispatch')
  need(type(custody) is Custody,'actual service custody')
  transaction=object();self.transaction=transaction
  _TRANSACTIONS[id(transaction)]=(transaction,self,custody)
  return transaction
 def finish(self,transaction,reply):
  row=_TRANSACTIONS.get(id(transaction))
  need(self.outcome is None and row is not None and row[0] is transaction and row[1] is self,'actual one-use service transaction')
  custody=row[2]
  # No additional I/O/publication is attempted here. The actual service return
  # carries failures occurring after its sole wire-publication attempt.
  ok,body=custody.attempt('final_outcome_encoding',lambda:encode(reply))
  if not ok:
   dispatch=decode(self.dispatch)
   body=encode({'status':'failed',**{k:dispatch[k] for k in ('nonce','request_sha256','source_sha256')},'failure_custody':custody.snapshot(),'qualification_granted':False})
  outcome=ServiceOutcome(transaction,body,custody.attach())
  _OUTCOMES[id(outcome)]=(outcome,self);self.outcome=outcome;self.ready.set();return outcome
 def take(self,dispatch,timeout):
  need(not self.taken and encode(dispatch)==self.dispatch,'one selected completion consumer')
  need(type(timeout) in (int,float) and 0<timeout<=604800,'finite completion deadline')
  need(self.ready.wait(timeout),'post-close service completion deadline; no wire success inferred')
  outcome=self.outcome;row=_OUTCOMES.get(id(outcome))
  need(type(outcome) is ServiceOutcome and row is not None and row[0] is outcome and row[1] is self,'post-close actual service completion unavailable; wire reply is provisional')
  self.taken=True;return outcome
