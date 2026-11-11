"""Concrete ordinary-metadata lifecycle, explicitly not a private native issuer."""
from types import MappingProxyType
from dataclasses import dataclass
from .metadata_io import encoded,TransferError
from contextlib import contextmanager

class MissingNativeProducer(RuntimeError):pass

def require_native_producers():
    raise MissingNativeProducer('BUILD ONLY: admitted catalogue/panel/data, protected target/reference, isolated process, capacity and scorer producers absent')

@dataclass(frozen=True)
class CapturedSubmission:
    owner:object
    receipt:object
    members:tuple

class MetadataInvestigation:
    def __init__(self,store,expected_products,query_binding):
        if not expected_products or len(expected_products)!=len(set(expected_products)):raise ValueError('product roster')
        self.store=store;self.expected=tuple(expected_products);self.query=query_binding
        self.state='open';self.capture=None;self.first_error=None
        self.failure_exception=None;self.cleanup_errors=[];self.failure_effects=None;self._failure_seen=set()
    def record_failure(self,error):
        """Retain the original exception objects; never replace first failure.
        TransferError separates its raw first OS error from cleanup errors and
        known/unknown transfer effects. Nothing is refunded or rolled back.
        """
        if self.first_error is None:
            self.first_error=error.first if isinstance(error,TransferError) else error
            self.failure_exception=error
        if id(error) not in self._failure_seen:
            self._failure_seen.add(id(error))
            if isinstance(error,TransferError):self.cleanup_errors.extend(error.cleanup)
        self.state='failed'
        budget=self.store.budget
        self.failure_effects=MappingProxyType({'known_read_bytes':budget.known_read_bytes,
            'known_write_bytes':budget.known_write_bytes,'reads_reserved':budget.reads_reserved,
            'writes_reserved':budget.writes_reserved,'unknown_effects':tuple(budget.unknown_effects),
            'physical_cost':'unknown','scope':'cumulative controlled Store IO; setup/runtime excluded'})
    @contextmanager
    def investigation(self):
        """Own the actual complete caller, including every post-open tail step."""
        if self.state!='open':raise ValueError('investigation requires fresh owner')
        try:yield self
        except BaseException as error:
            self.record_failure(error)
            raise
    def capture_submission(self,products):
        if self.state!='open':raise ValueError('terminal/capture state')
        self.state='capturing'
        try:
            if tuple(p['id'] for p in products)!=self.expected:raise ValueError('support and all prediction products required')
            pins=[]
            for i,p in enumerate(products):
                if p['query_binding']!=self.query:raise ValueError('query lineage')
                body=self.store.read(p['descriptor']);desc=self.store.publish('captured-'+str(i)+'.json',body)
                pins.append(MappingProxyType(dict(desc)))
            receipt=self.store.publish('CAPTURE.json',encoded({'query_binding':self.query,'ids':list(self.expected),'members':[dict(p) for p in pins]}))
            self.capture=CapturedSubmission(self,MappingProxyType(dict(receipt)),tuple(pins));self.state='captured';return self.capture
        except BaseException as e:self.record_failure(e);raise
    def open_target_metadata(self,token,descriptor):
        if self.state!='captured' or token is None or token is not self.capture or token.owner is not self:raise ValueError('same live capture owner')
        self.state='opening-target'
        try:
            self.store.read(token.receipt)
            for pin in token.members:self.store.read(pin)
            result=self.store.read(descriptor);self.state='target-opened';return result
        except BaseException as e:self.record_failure(e);raise
    def publish_report(self,token,result_descriptor):
        if token is not self.capture or self.state!='target-opened':raise ValueError('report lifecycle')
        self.state='publishing'
        try:
            self.store.read(result_descriptor)
            result=self.store.publish('REPORT.json',encoded({'capture':dict(token.receipt),'evidence_result':result_descriptor,'scope':'ordinary engineering only','scientific_success':False,'physical_cost':'unknown'}))
            self.state='complete';return result
        except BaseException as e:self.record_failure(e);raise

def stage_permitted_views(source,fit_validation_store,query_store,inputs):
    """Actual finite metadata copying; native roles must be issued separately."""
    destinations=set();rows=[]
    for item in inputs:
        if item['kind'] not in ('fit','validation','query_context','support_context'):raise ValueError('private targets/reference products forbidden')
        name=item['destination']
        if name in destinations:raise ValueError('duplicate destination')
        destinations.add(name);body=source.read(item['descriptor'])
        target=fit_validation_store if item['kind'] in ('fit','validation') else query_store
        rows.append({'kind':item['kind'],'descriptor':target.publish(name,body)})
    return rows
