"""Actual owned operation closure -> complete reference envelope.

This composes a live operator's selected producers; it does not supply missing
native workers, scientific bindings, simulator seeds or competent targets.
"""
from dataclasses import dataclass
from .core import *
from .programme import planned_jobs,require_complete_statuses
from .lifecycle import Custody,describe
_CLOSED={}
def source_row(operation,bindings,outputs):
 return {'operation':operation,'status':'complete','reason':None,'outputs':outputs,
  'method_lineage':{'source_revision':'2c15edf4e770165fc3962dcc3920c8bcaf555bed',
   'source_method_label':bindings['source_method_label'],'native_plan_sha256':bindings['native_plan_sha256'],
   'adaptations':bindings.get('explicit_adaptations',[]),'domain':'unclosed_source_product'}}
from .worker_family import WorkerFamily,EngineeringFamilyOwner
EngineeringOwner=EngineeringFamilyOwner
@dataclass(frozen=True)
class ClosedOperation:
 operation:str
 body:bytes
 owner:object
class ReferenceAssembly:
 def __init__(self,authority,design,cost,*,family=None):
  from .sandbox import QualifiedHost
  need(type(authority) in (QualifiedHost,EngineeringOwner) and type(cost) is Costs,'actual typed assembly and cost owners')
  self.domain='engineering_only' if type(authority) is EngineeringOwner else 'native_reference'
  self.authority=authority;self.design=design;self.cost=cost;self.closed=[];self.finalized=False;self.family=family;self.attempts=[]
  if self.domain=='native_reference':
   need(type(family) is WorkerFamily and family.authority is authority and family.cost is cost,'earlier original family required before assembly')
   family.require_open();family.assembly=self
  self.operations=[r['id'] for r in planned_jobs(design['profile'])]
  authority.require('reference_assembly:'+design['design_sha256'],authority.source_sha256)
 def run(self,operation,bindings,producer):
  lifecycle=Custody('reference_assembly_operation');self.attempts.append(lifecycle);phase='ordered_validation';raw_method=None;valid=False
  try:
   need(not self.finalized and len(self.closed)<len(self.operations) and operation==self.operations[len(self.closed)],'one ordered actual producer per planned operation')
   from .native_producer import NativeProducer
   if self.domain=='native_reference':
    need(type(producer) is NativeProducer and producer.family is self.family,'native reference requires same-family source-issued producer')
    self.family.require_slot(producer.slot)
   else:need(callable(producer),'inert engineering callback only')
   valid=True;phase='before_producer'
   self.authority.require('reference_operation:'+operation,self.authority.source_sha256)
   phase='producer'
   if self.domain=='native_reference':
    captured_owner=producer.run(self.authority,operation,bindings,self.design)
    row=producer.row(captured_owner)
   else:row=producer()
   phase='capture_validation';exact(row,('operation','status','reason','outputs','method_lineage'),'captured native row')
   need(row['operation']==operation and row['status']=='complete' and row['reason'] is None and type(row['outputs']) is dict,'same completed operation')
   raw_method=row['method_lineage'];need(type(raw_method) is dict,'retained source lineage')
   need(raw_method['native_plan_sha256']==bindings['native_plan_sha256'] and raw_method['source_method_label']==bindings['source_method_label'],'capture/plan/source-method join')
   captured=pin(encode(row))
   self.authority.require('reference_after_producer:'+operation,self.authority.source_sha256)
  except BaseException as first:
   if self.domain=='native_reference' and getattr(producer,'custody',None) is not None and producer.custody.first is first and phase=='producer':
    lifecycle.propagate(producer.custody,phase)
   else:lifecycle.capture(first,phase)
   captured=None;row=None
  finally:
   if self.domain=='native_reference' and self.family is not None:
    for slot in self.family.slots:
     if slot.producer is producer:
      self.family.retire(slot);lifecycle.propagate(slot.custody,'original_worker_retirement')
  if lifecycle.first is not None:
   if self.family is not None:self.family.custody.propagate(lifecycle,'assembly_operation')
   if not valid:lifecycle.raise_first()
   first=lifecycle.first
   try:
    row={'operation':operation,'status':'operational_failure','reason':encode({**describe(first,lifecycle),'phase':phase}).decode().strip(),'outputs':{}}
    raw_method={'source_method_label':bindings.get('source_method_label'),'native_plan_sha256':bindings.get('native_plan_sha256'),'captured_method_before_failure':raw_method,'failure_custody':lifecycle.snapshot(),'failure_phase':phase,'known_ordinary_costs':self.cost.report(),'native_consumption':'UNKNOWN unless the live producer supplies its terminal accounting'}
   except BaseException as secondary:
    lifecycle.capture(secondary,'failure_row_encoding_or_cost')
    if self.family is not None:self.family.custody.propagate(lifecycle,'failed_failure_row')
    lifecycle.raise_first()
   finally:
    if self.family is not None:self.family.custody.propagate(lifecycle,'assembly_failure_observation_tail')
  if self.domain=='native_reference':
   from .native_worker import NativeWorker
   if type(getattr(producer,'worker',None)) is NativeWorker:
    raw_method={**raw_method,'source_owned_worker_transport':producer.worker.observation()}
  row['method_lineage']={'domain':self.domain,'source_sha256':self.authority.source_sha256,'captured_method':raw_method,
   'captured_row_before_closure':captured,'operation_index':len(self.closed),'closure':'same original family independently attempts worker retirement before assembly closure; native effects remain unqualified'}
  product=ClosedOperation(operation,encode(row),self);_CLOSED[id(product)]=(product,self);self.closed.append(product)
  return product
 def envelope(self):
  need(not self.finalized and len(self.closed)==len(self.operations),'all planned operations, including failures, before envelope')
  rows=[]
  for operation,p in zip(self.operations,self.closed):
   selected=_CLOSED.get(id(p));need(type(p) is ClosedOperation and selected is not None and selected[0] is p and selected[1] is self and p.owner is self and p.operation==operation,'same actual owned closed product')
   rows.append(decode(p.body))
  require_complete_statuses(rows,self.design['profile'])
  self.authority.require('reference_envelope_close',self.authority.source_sha256);self.finalized=True
  return encode({'schema':'critical_init_full_result_v1','programme_sha256':self.design['programme_sha256'],'design_sha256':self.design['design_sha256'],
   'condition':'common_protected_reference' if self.domain=='native_reference' else 'engineering_reference_only','records':rows})
def run_programme(authority,design,cost,plans,producers=None):
 # Enter the actual retained family before assembly validation or issuance.
 # The native path cannot consume an unowned preissued producer dictionary.
 with WorkerFamily(authority,design,cost) as family:
  assembly=ReferenceAssembly(authority,design,cost,family=family);family.assembly=assembly
  need(type(plans) is dict and set(plans)==set(assembly.operations),'complete preselected binding family')
  if family.domain=='native_reference':
   need(producers is None,'native workers must be issued by this earlier family')
   from .native_producer import NativeProducer
   producers={}
   for op in assembly.operations:
    producers[op]=NativeProducer.issue(authority,authority.native_context,op,plans[op],design,family=family)
  else:need(type(producers) is dict and set(producers)==set(assembly.operations),'complete inert engineering producer family')
  for op in assembly.operations:assembly.run(op,plans[op],producers[op])
  family.result=assembly.envelope()
 return family.result
