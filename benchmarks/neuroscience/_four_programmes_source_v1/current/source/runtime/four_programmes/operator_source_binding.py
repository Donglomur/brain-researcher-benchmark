"""Actual earlier loaded-source binding; no source Pin or callback constructor."""
from .operator_intake import require
from .operator_entry import _code_identity

_BINDING=object()

class CanonicalPublisherSourceBindingV3:
    __slots__=('admission','parent','module','publisher_class','capture_method','row','_source_pin','_token')
    def __init__(self,token,admission,module,row):
        require(token is _BINDING,'fixed installed source continuation')
        self._token=token;self.admission=admission;self.parent=admission.parent
        self.module=module;self.publisher_class=module.CanonicalPublisher
        self.capture_method=module.CanonicalPublisher.capture;self.row=row
        self._source_pin=dict(row['descriptor'])
    @property
    def source_pin(self):self.require_original();return dict(self._source_pin)
    def require_original(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.admission.require_verified_root_v1();p=self.admission.prior_static
            # Each repeated code-identity observation is charged before encoding.
            # Physical interpreter allocation is not a measured memory claim.
            self.parent.share.charge('work_units',self.row['descriptor']['bytes']*128+4096)
            self.parent.share.charge('retained_bytes',self.row['descriptor']['bytes']*16+4096)
            require(self._token is _BINDING and p.canonical_publisher_binding is self and
                    self.parent is p.parent and self.module.CanonicalPublisher is self.publisher_class and
                    self.publisher_class.capture is self.capture_method and
                    p.invocation.loaded_source_map[self.row['loaded_module']][0] is self.module and
                    _code_identity(self.module)==self.row['loaded_code_sha256'],
                    'same actual earlier loaded canonical publisher, source class and completed admission')
            return self
        except BaseException as error:
            raise retain_source_failure(parent,error,'CanonicalPublisherSourceBindingV3.require_original')

def bind_canonical_publisher_source_v3(admission):
    from .operator_bootstrap_owner import RootBootstrapAdmission
    from . import backend_capture
    require(type(admission)is RootBootstrapAdmission,'actual fixed root admission')
    from .early_resources import retain_source_failure
    parent=admission.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        admission.require_verified_root_v1();p=admission.prior_static;parent=p.parent
        require(p.canonical_publisher_binding is None and not getattr(p,'publisher_binding_attempted',False),
                'one prior source binding before every publisher')
        p.publisher_binding_attempted=True
        try:
            require(not getattr(parent,'canonical_publications',{}),'no source binding after a publication')
            rows=[x for x in p.invocation.intake.body['installed_closure']['members']if x['role']=='canonical_publisher']
            require(len(rows)==1,'one fixed canonical_publisher source role')
            row=rows[0];parent.share.charge('work_units',row['descriptor']['bytes']*128+4096)
            parent.share.charge('retained_bytes',row['descriptor']['bytes']*16+4096)
            observed=p.invocation.loaded_source_map.get(row['loaded_module'])
            require(observed is not None and observed[0] is backend_capture and observed[1]==row and
                    _code_identity(backend_capture)==row['loaded_code_sha256'],
                    'actual integrated loaded publisher source, no storage/capture-source alias')
            binding=CanonicalPublisherSourceBindingV3(_BINDING,admission,backend_capture,row)
            p.canonical_publisher_binding=binding
            binding.require_original();return binding
        except BaseException as e:parent.retain(e,'source_capture','source_refusal','bind_canonical_publisher_source_v3');raise
    except BaseException as error:
        raise retain_source_failure(parent,error,'bind_canonical_publisher_source_v3')

