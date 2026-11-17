"""Actual fixed public creator → complete file capture → next creator chain.

The earlier live owner precedes every operation. This source does not invent a
private root issuer or authenticate EarlySelection merely because bytes exist.
"""
import time
from .common import Store,need,same,descriptor,encode,parse,pin,bounded_size,integer,DependencyUnavailable
from .early_resources import EarlyResources
from .source_session import SourceSession
from .precommit_records import validate_type

_CAPTURE=object()
OPERATIONS=('public_interface','public_ABI','paired_views_manifest')
OUTPUTS={'public_interface':'public_interface.json','public_ABI':'public_ABI.json',
         'paired_views_manifest':'paired_views_manifest.json'}

class CreationResult:
    def __init__(self,token,owner,request):
        need(token is _CAPTURE,'fixed actual creator caller result')
        self.owner=owner;self.request=request;self.request_pin=None;self.product=None
        self.output_pin=None;self.capture=None;self.capture_pin=None
        self.first_raw=None;self.started_ns=None;self.finished_ns=None
        self.input_readbacks=[];self.cost_before=None
    @property
    def complete(self):
        return (self.first_raw is None and self.capture_pin is not None and
                self.output_pin is not None and self.capture is not None and self.capture['complete']is True)

class EarlyConstruction:
    @classmethod
    def from_bootstrap(cls,bootstrap,*,source_session,scope):
        from .early_bootstrap import EarlyBootstrapResult
        need(type(bootstrap)is EarlyBootstrapResult,'actual completed seed/binding bootstrap, not a supplied wire record')
        parent=bootstrap.parent
        try:
            need(parent.owner is bootstrap.owner and parent.seed_pin==bootstrap.seed_pin and
                 parent.binding_pin==bootstrap.binding_pin,'same actual completed bootstrap ancestry and live owner')
            return cls(bootstrap.owner,source_session=source_session,scope=scope,
                       inputs=bootstrap.inputs,outputs=bootstrap.outputs)
        except BaseException as error:
            parent.retain(error,'source_capture','identity_refusal','EarlyConstruction.from_bootstrap');raise
    def __init__(self,owner,*,source_session,scope,inputs,outputs):
        need(type(owner)is EarlyResources and owner.parent.owner is owner,'same actual earlier resource owner')
        self.owner=owner;self.attempts={};self.completed=[];self.template=None;self.closed=False
        try:
            need(owner.parent.binding_pin is not None and owner.parent.seed_pin is not None,
                 'actual earlier seed and owner-binding captures precede every creator')
            need(owner.parent.selection is None and owner.parent.first_raw is None,
                 'public creators run only in a failure-free earlier owner')
            need(type(source_session)is SourceSession and source_session.programme=='PAPER-FIND-050'and
                 not source_session.closed,'actual fixed complete original CI source session')
            need(type(inputs)is Store and type(outputs)is Store and inputs.meter is owner.host and outputs.meter is owner.host,
                 'same already selected ordinary roots and earlier host share')
            need(str(outputs.root)==owner.plan['output_root'],'fixed earlier construction output root')
            need(1<=owner.plan['maximum_depth']<=64,'fixed finite metadata nesting ceiling')
            # This import belongs to the same admitted source session. It is
            # never an external factory or caller-provided creator callback.
            self.public=source_session.module('precommit_public')
            need(type(scope)is self.public.Scope,'actual original Scope from that same complete namespace')
            self.scope=scope;self.session=source_session;self.inputs=inputs;self.outputs=outputs
        except BaseException as error:
            owner.parent.retain(error,'source_capture','source_refusal','EarlyConstruction.__init__');raise
    def _clock(self):
        self.owner.check();now=time.monotonic_ns();integer(now)
        need(now<self.owner.parent.original_deadline,'unchanged original creation evidence cutoff')
        return now
    def _publish(self,name,value,*,kind=None):
        cap=self.owner.plan['maximum_output_bytes']
        bound=bounded_size(value)
        self.owner.host.charge('work_units',bound)
        self.owner.host.charge('retained_bytes',bound)
        self._depth(value)
        if kind is not None:validate_type(kind,value)
        raw=encode(value)
        need(len(raw)<=cap,'complete output inside selected earlier byte cap')
        expected=self.outputs.write(name,raw)
        self.owner.host.charge('retained_bytes',len(raw)+1)
        observed=self.outputs.read(expected,cap,metadata=True)
        need(observed==raw,'actual whole file write/sync/close/readback completed')
        return expected
    def _depth(self,value,depth=0):
        need(depth<=self.owner.plan['maximum_depth'],'earlier selected complete metadata depth')
        if type(value)is dict:
            for member in value.values():self._depth(member,depth+1)
        elif type(value)is list:
            for member in value:self._depth(member,depth+1)
    def _read(self,expected,result,*,created=False):
        descriptor(expected);cap=self.owner.plan['maximum_input_bytes']
        need(expected['bytes']<=cap,'earlier exact complete input cap')
        self.owner.host.charge('retained_bytes',expected['bytes']*16+4096)
        store=self.outputs if created else self.inputs
        raw=store.read(expected,cap,metadata=True)
        result.input_readbacks.append(dict(expected))
        value=parse(raw,cap);self._depth(value)
        return value
    def _expected_inputs(self,operation):
        plan=self.owner.plan
        if operation=='public_interface':return [plan['scientific_template'],plan['public_ABI_grammar']]
        if operation=='public_ABI':return [self.attempts['public_interface'].output_pin,plan['public_ABI_grammar']]
        return [self.attempts['public_ABI'].output_pin,plan['view_rules'],plan['scientific_template']]
    def request_v2(self,operation):
        need(operation in OPERATIONS,'fixed three public creators')
        need(len(self.completed)<3 and operation==OPERATIONS[len(self.completed)],'original creator order')
        owner=self.owner
        return {'schema':'ci_creationrequest_v2','operation':operation,
                'owner_binding':owner.parent.binding_pin,'construction_plan':owner.seed['construction_plan'],
                'creator_source':owner.plan['constructor_source'],'capture_source':owner.plan['capture_source'],
                'ordered_inputs':self._expected_inputs(operation),'output_path':OUTPUTS[operation],
                'maximum_output_bytes':owner.plan['maximum_output_bytes']}
    def create_capture_v2(self,request):
        owner=self.owner;result=None
        try:
            need(not self.closed and owner.parent.first_raw is None and owner.parent.selection is None,
                 'no continuation after an earlier failure or later selection')
            owner.host.charge('work_units',bounded_size(request))
            validate_type('CreationRequest',request)
            operation=request['operation']
            if operation=='early_selection':
                raise DependencyUnavailable('ci_private_precommit_issuer','exact independent fixed issuer must own the fourth capture; never supplied selection JSON')
            need(operation in OPERATIONS and operation not in self.attempts,'one original closed creator attempt')
            result=CreationResult(_CAPTURE,owner,request)
            self.attempts[operation]=result
            # Latch before further validation, clock, file or creator effects.
            need(same(request,self.request_v2(operation)),'all exact source-owned request paths/inputs/caps/owner/source')
            result.cost_before=owner.cost_prefix();result.started_ns=self._clock()
            result.request_pin=self._publish('creation_'+operation+'_request.json',request,kind='CreationRequest')
            if operation=='public_interface':
                template=self._read(owner.plan['scientific_template'],result)
                # Read/authenticate the grammar before projection; no body is
                # followed through the template or paired member descriptors.
                grammar=self._read(owner.plan['public_ABI_grammar'],result)
                from .public_abi_grammar import validate_jobs
                validate_jobs(grammar)
                self.template=self.public.admit_template(self.scope,template,owner.plan['scientific_template'],meter=owner.host)
                product=self.public.PublicInterfaceCreator.create_v2(self.template,meter=owner.host)
                value=product.body;kind='PublicTaskInterface'
            elif operation=='public_ABI':
                previous=self.attempts['public_interface']
                need(previous.complete,'actual complete interface capture before ABI creation')
                observed=self._read(previous.output_pin,result,created=True)
                need(same(observed,previous.product.body),'same actual source-owned public interface after capture')
                grammar=self._read(owner.plan['public_ABI_grammar'],result)
                product=self.public.PublicABICreator.create_v2(previous.product,previous.output_pin,grammar,
                    owner.plan['public_ABI_grammar'],meter=owner.host)
                value=product.body;kind='PublicABI'
            else:
                previous=self.attempts['public_ABI']
                need(previous.complete,'actual complete ABI capture before paired manifest creation')
                observed=self._read(previous.output_pin,result,created=True)
                need(same(observed,previous.product.body),'same actual complete public ABI after capture')
                rules=self._read(owner.plan['view_rules'],result)
                template=self._read(owner.plan['scientific_template'],result)
                need(same(template,self.template.body),'same full earlier scientific template')
                need(len(rules['common'])+len(rules['author_code'])+1<=owner.plan['maximum_members'],
                     'complete manifest plus new common ABI within earlier finite member count')
                product=self.public.PairedViewManifestCreator.create_v2(previous.product,previous.output_pin,rules,
                    owner.plan['view_rules'],meter=owner.host)
                value=product;kind=None
            result.product=product
            result.output_pin=self._publish(OUTPUTS[operation],value,kind=kind)
            result.finished_ns=self._clock()
            need(result.finished_ns>=result.started_ns,'nondecreasing original capture interval')
            result.capture={'schema':'ci_creationcapture_v2','operation':operation,'owner_binding':owner.parent.binding_pin,
                'request':result.request_pin,'source_readback':list(result.input_readbacks),'output':result.output_pin,
                'started_ns':result.started_ns,'finished_ns':result.finished_ns,'cost_before':result.cost_before,
                'cost_after':owner.cost_prefix(),'complete':True,'first_error':None,'publication':'complete'}
            # publication describes the already finished output publication.
            # This capture's own Pin is only granted by the actual outer return.
            result.capture_pin=self._publish('creation_'+operation+'_capture.json',result.capture,kind='CreationCapture')
            owner.parent.creation_captures.append(dict(result.capture_pin))
            owner.parent.known_records.extend([result.request_pin,result.output_pin,result.capture_pin])
            self.completed.append(operation)
            return result
        except BaseException as error:
            owner.parent.retain(error,'source_capture','publication_failure','EarlyConstruction.create_capture_v2')
            self.closed=True
            if result is not None:result.first_raw=error
            # Keep any actually captured output even if the later capture file
            # failed. No complete result or replacement failure Pin is invented.
            raise
    def construct_public_v2(self):
        """The actual fixed source caller; no caller chooses a narrower subset."""
        results=[]
        for operation in OPERATIONS:
            result=self.create_capture_v2(self.request_v2(operation))
            need(result.complete,'actual whole capture before next original creator')
            results.append(result)
        need(len(self.completed)==3 and len(results)==3,'all three original public preparation products')
        return tuple(results)
