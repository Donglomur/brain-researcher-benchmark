"""Concrete typed-lease model broker attachment; original stdio freeze unchanged."""
import os
from pathlib import Path
from ..core.custody import digest,canonical
from ..core.outcomes import valid_violation
from ..core.plan import ContextState
from ..core.resources import ResourceLedger,CandidateCaps,BudgetExceeded
from ..process_guard.aggregate_v3 import BrokerLease
from ..process_guard.contracts import GuardError
from .protocol import AdapterAdmission,TransportError,encode_frame,check_handshake
from .stdio import ModelAdapterSession


def provider_required_bindings(admission,state,ledger):
    if not isinstance(admission,AdapterAdmission) or not isinstance(state,ContextState) or not isinstance(ledger,ResourceLedger):
        raise TransportError('typed provider admission/state/ledger required')
    admission.validate()
    if state.context.context_id!=admission.context_id or ledger.context_id!=admission.context_id or admission.repetition!=state.context.repetition:
        raise TransportError('cross-context provider authority forbidden')
    return {'context_digest':state.context.binding_digest,'caps_digest':CandidateCaps().binding_digest,
        'provider_admission_digest':admission.binding_digest,'fixed_model_evidence_digest':admission.fixed_model_evidence_digest,
        'stateless_evidence_digest':admission.stateless_evidence_digest,'tokenizer_evidence_digest':admission.tokenizer_evidence_digest,
        'usage_evidence_digest':admission.usage_evidence_digest,'environment_evidence_digest':admission.environment_evidence_digest,
        'inference_policy_digest':admission.inference_policy.binding_digest,'inference_binding_digest':digest(admission.inference_binding)}


class CgroupModelAdapterSessionV2(ModelAdapterSession):
    def __init__(self,admission,*,authority,state,ledger,broker_lease):
        if not isinstance(broker_lease,BrokerLease):raise TransportError('real registered aggregate broker lease required')
        super().__init__(admission,authority=authority,state=state,ledger=ledger)
        self.broker_lease=broker_lease
        broker_lease.require(admission,state,ledger)
        self.broker_closure=None;self.exhaustion_original_failures=[];self.failed_exchange_kind=None;self.exhaustion_drained=False

    def _capture(self,kind,data):
        """Bound actual byte writes; short FileIO writes never imply durability."""
        limit=self.a.max_capture_bytes
        allowed=min(len(data),max(0,limit-self.captured));offset=0
        try:
            while offset<allowed:
                wrote=self.files[kind].write(data[offset:allowed])
                if type(wrote) is not int or not 0<wrote<=allowed-offset:
                    raise TransportError('capture write made invalid/no progress')
                offset+=wrote;self.captured+=wrote
            if allowed!=len(data):raise TransportError('qualified aggregate capture capacity exhausted; original prefix retained')
        except BaseException:
            self.capture_complete=False
            raise

    def _deadline(self):
        # Monitor is continuous even while no exchange is active. This additionally
        # checks its actual health/aggregate evidence on every selector iteration.
        self.broker_lease.observe()
        return super()._deadline()

    def start(self):
        self._authorize(self.authority,model=True)
        if self.lifecycle!='allocated':raise TransportError('broker launch is single-use/no retry')
        self.broker_lease.require(self.a,self.state,self.ledger)
        encode_frame(self.a.handshake(),self.a.max_frame_bytes)
        self.lifecycle='starting'
        try:
            self._deadline();self._verify_sources()
            path=Path(self.a.capture_directory)
            if str(path.parent.resolve(strict=True))!=str(path.parent):raise TransportError('private same-scratch capture parent changed')
            path.mkdir(mode=0o700)
            for name in ('requests','responses','stderr','receipts'):
                self.files[name]=open(path/(name+'.bin'),'xb',buffering=0)
            # Concrete registered lease opens the exact native leaf descriptor and
            # attaches before exec. No caller-supplied launcher/observer callback.
            self.proc=self.broker_lease._spawn();self.owned_pid=self.proc.pid
            for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):os.set_blocking(stream.fileno(),False)
            self._event('original_aggregate_broker_launch',{'argv':list(self.a.argv),'pid':self.owned_pid,
                'admission_digest':self.a.binding_digest,'actual_custody':self.broker_lease.require(self.a,self.state,self.ledger)})
            ack=self._exchange(self.a.handshake());self.handshake_digest=check_handshake(self.a,ack);self.lifecycle='open'
            self._event('handshake_verified',{'handshake_digest':self.handshake_digest,
                'qualification':'actual owned broker placement plus protocol agreement; endpoint contracts remain separate'})
            return {'handshake_digest':self.handshake_digest,'admission_digest':self.a.binding_digest}
        except BaseException as exc:self._fail(exc);raise

    def _terminate_owned(self):
        # Cgroup drain covers all descendants, including a detached process group.
        # Then the original stream drain sees a reaped leader, never needs PID kill.
        self.broker_lease.terminate_owned()
        if self.proc is not None:self.proc.wait(timeout=10)
        super()._terminate_owned()

    def _exchange(self,message):
        try:
            result=super()._exchange(message)
            self.failed_exchange_kind=None
            return result
        except BaseException:
            self.failed_exchange_kind=message.get('kind')
            raise

    def _drain_exhausted(self):
        """Capture original bytes after real cgroup drain; no goodbye/response."""
        self.broker_lease.terminate_owned()
        if self.proc is None:raise TransportError('exhaustion cannot qualify an unlaunched broker')
        self.proc.wait(timeout=10)
        for stream,kind in ((self.proc.stdout,'responses'),(self.proc.stderr,'stderr')):
            if stream is None or stream.closed:continue
            while True:
                try:data=os.read(stream.fileno(),65536)
                except BlockingIOError as exc:raise TransportError('exhausted broker stream not actually drained') from exc
                if not data:break
                self._capture(kind,data)
                # Only a currently interrupted tokenize request can have an
                # incomplete unmetered response. A generate remains reserved
                # until validated actual usage, and is never admitted here.
                if kind=='responses' and self.failed_exchange_kind!='tokenize':
                    self.capture_complete=False
                    raise TransportError('unsolicited exhausted broker stdout')
        for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):
            if stream is not None and not stream.closed:stream.close()
        self.exhaustion_drained=True

    def _fail(self,exc):
        if (isinstance(exc,BudgetExceeded) and valid_violation(self.ledger.violation)
            and not any(v['status']=='reserved' for v in self.ledger.provider_requests.values())
            and self.lifecycle in ('open','starting')):
            # Preserve actual exception and partial captures. This is not yet a
            # successful close: concrete monitor/drain custody is still required.
            body={'type':type(exc).__name__,'error':str(exc),'ledger_violation':self.ledger.violation,
                  'failed_exchange_kind':self.failed_exchange_kind}
            self.exhaustion_original_failures.append(body);self.lifecycle='exhausted'
            try:
                self._event('original_settled_exhaustion_failure',body)
                self._drain_exhausted()
                for file in self.files.values():
                    if not file.closed:os.fsync(file.fileno())
            except BaseException as cleanup:
                self.capture_complete=False;self.lifecycle='failed'
                self.events.append({'kind':'original_exhaustion_cleanup_failure',
                    'body':{'type':type(cleanup).__name__,'error':str(cleanup),'original_failure':body},
                    'event_digest':digest([str(cleanup),body])})
                try:self._flush_close()
                except BaseException as persistence:
                    self.events.append({'kind':'exhaustion_persistence_failure','error':str(persistence),
                        'event_digest':digest(str(persistence))})
            return
        return super()._fail(exc)

    def close_exhausted(self,*,authority):
        self._authorize(authority,closing=True)
        if self.lifecycle not in ('open','exhausted'):raise TransportError('only open/settled-exhaustion broker may close without goodbye')
        if not self.capture_complete:raise TransportError('capture/persistence incident blocks exhaustion closure')
        if any(v['status']=='reserved' for v in self.ledger.provider_requests.values()):raise TransportError('unresolved usage blocks exhaustion closure')
        try:
            evidence=self.broker_lease.exhaustion_evidence()
            if not self.exhaustion_drained:self._drain_exhausted()
            if not self.capture_complete:raise TransportError('exhaustion capture incomplete')
            original={'schema':'n073_model_transport_exhaustion_close_v2','context_id':self.a.context_id,
                'admission_digest':self.a.binding_digest,'events_digest':digest(self.events),
                'capture_bytes_before_closure_receipt':self.captured,'capture_complete':True,
                'original_returncode':self.proc.returncode,'closure_kind':'durable_exhaustion_actual_owned_drain_no_goodbye',
                'exhaustion_evidence':evidence.to_dict(),'original_failures':self.exhaustion_original_failures,
                'unresolved_usage':[],'inference_binding':self.a.inference_binding,
                'generation_inference_records':list(self.generation_inference_records),
                'partial_protocol_kind':self.failed_exchange_kind,
                'provider_statelessness':'independently admitted evidence; no invented goodbye acknowledgement'}
            original['receipt_digest']=digest(original)
            self._event('original_exhaustion_closure',original);self._flush_close()
            self.broker_closure=self.broker_lease._closed_receipt(original,exhaustion=evidence)
            self.lifecycle='closed';return self.broker_closure
        except BaseException as exc:
            # Generic failure handling is deliberately not recoverable as a
            # second exhaustion attempt. Original errors and streams survive.
            super()._fail(exc)
            raise

    def close(self,*,authority):
        try:original=super().close(authority=authority)
        except BudgetExceeded:
            if self.lifecycle!='exhausted':raise
            return self.close_exhausted(authority=authority)
        try:self.broker_closure=self.broker_lease._closed_receipt(original)
        except BudgetExceeded:
            evidence=self.broker_lease.exhaustion_evidence()
            self.broker_closure=self.broker_lease._closed_receipt(original,exhaustion=evidence)
        return self.broker_closure
