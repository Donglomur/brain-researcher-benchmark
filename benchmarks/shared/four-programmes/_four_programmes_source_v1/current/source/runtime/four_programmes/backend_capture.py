"""Owned, once-only canonical captures for the adopted early/backend protocol.

The old scientific encoder is deliberately untouched. Captures are outputs of
the actual selected Store; parsing a descriptor cannot construct this handle.
"""
from .common import Store, need, pin, bounded_size
from .backend_json import canonical, parse
from .precommit_records import validate_type

_CAPTURE = object()

class CapturedRecord:
    __slots__ = ('_raw', '_descriptor', '_owner', '_kind', '_attempt')
    def __init__(self, token, raw, descriptor, owner, kind, attempt):
        need(token is _CAPTURE, 'fixed completed canonical capture')
        self._raw = raw
        self._descriptor = dict(descriptor)
        self._owner = owner
        self._kind = kind
        self._attempt = attempt
    @property
    def raw(self): return self._raw
    @property
    def pin(self): return dict(self._descriptor)
    @property
    def body(self): return parse(self._raw, len(self._raw), maximum_depth=64,
                                maximum_members=len(self._raw), maximum_string_bytes=len(self._raw))
    @property
    def owner(self): return self._owner
    @property
    def kind(self): return self._kind

class CaptureAttempt:
    __slots__ = ('name', 'kind', 'raw_first', 'raw_secondaries', 'raw',
                 'provisional', 'complete', 'write_entered', 'readback_entered')
    def __init__(self, name, kind):
        self.name=name; self.kind=kind; self.raw_first=None; self.raw_secondaries=[]
        self.raw=None; self.provisional=None; self.complete=None
        self.write_entered=False; self.readback_entered=False
    def retain(self, error):
        if self.raw_first is None: self.raw_first=error
        elif error is not self.raw_first: self.raw_secondaries.append(error)

class CanonicalPublisher:
    """Actual owner and original bounded output Store, never a wire authority."""
    def __init__(self, owner, outputs, *, maximum_bytes, maximum_members, maximum_depth, condition=None):
        from .early_resources import EarlyResources, ParentCustody
        need(type(owner) in (EarlyResources, ParentCustody), 'actual closed original canonical capture owner')
        from .early_resources import retain_source_failure
        parent=owner.parent if type(owner)is EarlyResources else owner
        if parent.first_raw is not None:raise parent.first_raw
        try:
            need(type(outputs) is Store, 'actual source-owned bounded Store')
            meter = outputs.meter
            if type(owner) is EarlyResources:
                if condition is None:
                    need(meter is owner.host or (owner.terminal and meter is owner.terminal_host),
                         'same original host or entered protected terminal share')
                else:
                    from .precommit_records import CONDITIONS
                    need(type(condition) is str and condition in CONDITIONS and meter is owner.arms[condition],
                         'same closed original arm partition, never a supplied meter')
            else:
                need(condition is None and meter is owner.share,'same original earlier parent share')
            self.condition=condition
            need(type(maximum_bytes) is int and 0 < maximum_bytes <= 9007199254740991,
                 'selected bounded canonical member')
            need(type(maximum_members) is int and 0 < maximum_members <= 9007199254740991 and
                 type(maximum_depth) is int and 0 < maximum_depth <= 64,
                 'selected finite original output count/depth')
            self.owner=owner; self.outputs=outputs; self.meter=meter
            self.maximum_bytes=maximum_bytes; self.maximum_members=maximum_members
            self.maximum_depth=maximum_depth; self.attempts={}; self.raw_first=None
            self.parent=owner.parent if type(owner) is EarlyResources else owner
            self.native_source_binding=None
            if getattr(self.parent,'operator_root_admission',None) is not None:
                self.native_source_binding=self.parent.operator_root_admission.require_canonical_publisher_binding_v3()
            if not hasattr(self.parent,'canonical_publications'):self.parent.canonical_publications={}
        except BaseException as error:
            raise retain_source_failure(parent,error,'CanonicalPublisher.__init__')
    def require_native_source_v3(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            from .operator_bootstrap_owner import RootBootstrapAdmission
            admission=getattr(self.parent,'operator_root_admission',None)
            need(type(admission)is RootBootstrapAdmission,'same actual earlier installed-root admission')
            binding=admission.require_canonical_publisher_binding_v3()
            need(binding is self.native_source_binding and binding.parent is self.parent and
                 binding.publisher_class is type(self),'same original actual publisher binding and source class')
            return binding
        except BaseException as error:
            raise retain_source_failure(parent,error,'CanonicalPublisher.require_native_source_v3')
    @property
    def source_pin(self):return self.require_native_source_v3().source_pin
    def capture(self, name, kind, body):
        if self.parent.first_raw is not None:raise self.parent.first_raw
        need(self.raw_first is None, 'no continuation after failed canonical publication')
        need(type(name) is str and name not in self.attempts and
             len(self.attempts) < self.maximum_members, 'one fixed publication slot within original count')
        key=(str(self.outputs.root),name)
        need(key not in self.parent.canonical_publications and
             len(self.parent.canonical_publications)<self.maximum_members,
             'whole original owner canonical publication slots, including failed attempts')
        attempt=CaptureAttempt(name,kind)
        self.attempts[name]=attempt  # Own before clock, budget, encoding or IO.
        self.parent.canonical_publications[key]=attempt
        try:
            bound=bounded_size(body)
            self.meter.charge('work_units', bound)
            self.meter.charge('retained_bytes', bound)
            from .backend_native_v3_records import NATIVE_RECORDS
            if kind in NATIVE_RECORDS:
                self.require_native_source_v3()
                from .backend_native_v3_codec import validate_native_type
                validate_native_type(kind,body)
            else:validate_type(kind, body)
            raw=canonical(body,self.maximum_bytes,maximum_depth=self.maximum_depth)
            attempt.raw=raw
            attempt.write_entered=True
            observed=self.outputs.write(name,raw)
            attempt.provisional=observed  # Not yet a completed capture.
            self.meter.charge('retained_bytes',len(raw)+1)
            attempt.readback_entered=True
            reread=self.outputs.read(observed,self.maximum_bytes,metadata=True)
            need(reread == raw and pin(reread) == pin(raw), 'exact complete original canonical readback')
            capture=CapturedRecord(_CAPTURE,raw,observed,self.owner,kind,attempt)
            attempt.complete=capture
            return capture
        except BaseException as error:
            attempt.retain(error); self.raw_first=error
            parent=getattr(self.owner,'parent',self.owner)
            try: parent.retain(error,'source_capture','publication_failure','CanonicalPublisher.capture')
            except BaseException as diagnostic: attempt.retain(diagnostic)
            raise
