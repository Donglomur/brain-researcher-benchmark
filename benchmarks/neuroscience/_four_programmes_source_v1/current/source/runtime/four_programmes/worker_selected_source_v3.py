"""Concrete selected-artifact descriptor ownership, distinct from captures.

This proves an earlier source selection, not an artifact read or native result.
The combined agent input ABI/product producer remains explicitly unavailable.
"""
from .common import need,same,DependencyUnavailable

_SELECTED=object()
_ROLES={'template':'template_file','renderer_source':'template_renderer'}
_FIXED=('NativeContextPolicyV2','LocalBackendProfile','LocalArtifactSelection',
        'NativeArtifactRootSelectionV1','NativeArtifactRootBundleV1','NativeAgentPolicyV4','AgentInputSelectionV1')
_ALL_ROLES=('server_executable','model_gguf','template','tokenizer_source','renderer_source')

def _projection(records,roots,source_admission,role):
    """Full fixed selection inverse over already authenticated source bodies."""
    need(role in (*_ROLES,'input_ABI') and set(records)==set(_FIXED),'closed actual source role and complete fixed selection')
    policy=records['NativeContextPolicyV2'];profile=records['LocalBackendProfile']
    artifacts=records['LocalArtifactSelection'];selection=records['NativeArtifactRootSelectionV1']
    bundle=records['NativeArtifactRootBundleV1']
    p=policy.body;f=profile.body;a=artifacts.body;s=selection.body;b=bundle.body
    agent=records['NativeAgentPolicyV4'];inputs=records['AgentInputSelectionV1'];ag=agent.body;ai=inputs.body
    need(same(ag['native_context_policy'],policy.pin) and same(ag['local_backend'],profile.pin) and
         same(ag['agent_input_selection'],inputs.pin) and same(ai['template'],a['template_file']) and
         same(ai['renderer_source'],a['template_renderer']) and
         all(ai[k]in ag['source_closure']for k in
             ('input_ABI','producer_source','protocol_source','renderer_source','renderer_bound_source')),
         'complete actual selected V4 input/source/template/renderer policy inverse')
    need(same(p['original_source_admission'],source_admission) and
         same(p['artifact_roots'],selection.pin) and same(f['artifact_selection'],artifacts.pin) and
         same(s['artifact_selection'],artifacts.pin) and same(s['backend_profile'],profile.pin),
         'same original policy/backend/artifact/root selection chain')
    need(same(b['selection'],selection.pin) and same(b['source_admission'],source_admission) and
         same(b['roots'],[x.pin for x in roots]),'complete exact earlier root bundle and order')
    values=[x.body for x in roots];ids=[x['root_id'] for x in values]
    need(ids==sorted(set(ids)) and 1<=len(ids)<=5 and
         all(x['readonly'] is True and same(x['root_policy'],s['root_policy']) and
             same(x['source_admission'],source_admission) for x in values),
         'complete actual original readonly root selection provenance')
    expected=[f['server_executable'],a['model_gguf'],a['template_file'],a['tokenizer_source'],a['template_renderer']]
    need([x['role']for x in s['roles']]==list(_ALL_ROLES) and
         all(same(x['selected'],selected) and x['root_id'] in ids
             for x,selected in zip(s['roles'],expected)),
         'all five exact selected native artifact roles, never role relabelling')
    if role=='input_ABI':
        # The installed ordinary ABI definition is source-selected, not a
        # native artifact-root path or a newly captured input product.
        return dict(ai['input_ABI']),None,()
    row=s['roles'][_ALL_ROLES.index(role)]
    need(same(row['selected'],a[_ROLES[role]]),'same selected exact descriptor')
    return dict(row['selected']),row['root_id'],tuple(row['relative_components'])

def _worker_selection(context,role):
    from .worker_context_v3 import WorkerContextProxy
    from .worker_channel_v3 import require_capture
    need(type(context)is WorkerContextProxy,'actual original worker context')
    context.require_active()
    selected={kind:context.bootstrap(kind)for kind in _FIXED}
    roots=tuple(x for x in context.bootstrap_objects if x.kind=='NativeRootObservationV1')
    # Existing original prepaid installed-source check envelope, not a new
    # renderer grant, empirical resource observation or scientific allowance.
    context.channel.endpoint.reserve_source_check(sum(len(x.raw)for x in (*selected.values(),*roots)))
    for capture in (*selected.values(),*roots):
        require_capture(capture,context,capture.kind)
        need(capture.origin=='bootstrap_delivery' and any(x is capture for x in context.bootstrap_objects),
             'actual original bootstrap delivery, never new canonical capture')
    result=_projection(selected,roots,context.context_identity['source_admission'],role)
    return selected,roots,result

class WorkerSelectedSourceV3:
    __slots__=('context','role','records','roots','_pin','root_id','components')
    def __init__(self,token,context,role,records,roots,result):
        need(token is _SELECTED,'fixed complete earlier source selection issuer')
        self.context=context;self.role=role;self.records=records;self.roots=roots
        self._pin,self.root_id,self.components=result
    @property
    def pin(self):return dict(self._pin)
    def require_original(self):
        records,roots,result=_worker_selection(self.context,self.role)
        need(getattr(self.context,'selected_artifact_sources_v3',{}).get(self.role)is self and
             all(records[k]is self.records[k]for k in _FIXED) and
             len(roots)==len(self.roots) and all(a is b for a,b in zip(roots,self.roots)) and
             same(result,(self.pin,self.root_id,self.components)),
             'same retained original selected source owner and complete provenance')
        return self

def select_worker_artifact_source_v3(context,role):
    need(role in _ROLES,'fixed template or renderer artifact source role')
    return _select_worker_source_v3(context,role)

def select_worker_input_ABI_source_v3(context):
    return _select_worker_source_v3(context,'input_ABI')

def _select_worker_source_v3(context,role):
    records,roots,result=_worker_selection(context,role)
    registry=getattr(context,'selected_artifact_sources_v3',None)
    if registry is None:registry={};context.selected_artifact_sources_v3=registry
    need(type(registry)is dict,'fixed original source owner registry')
    if role in registry:return registry[role].require_original()
    value=WorkerSelectedSourceV3(_SELECTED,context,role,records,roots,result)
    registry[role]=value;return value.require_original()

def _host_selection(view,role):
    from .backend_host_view import HBackendView
    from .backend_h_bootstrap_v3 import HBootstrapObjectV3
    need(type(view)is HBackendView,'actual original H backend view')
    view.require_original();activation=view.receiver.activation;activation.require_original()
    selected={};roots=[]
    objects=activation.objects
    extent=sum(len(x.raw)for x in objects)
    view.receiver.host_meter.charge('work_units',extent*128+4096)
    view.receiver.host_meter.charge('retained_bytes',extent*16+4096)
    for kind in _FIXED:
        found=[x for x in objects if x.kind==kind]
        need(len(found)==1,'one original H selected source delivery')
        selected[kind]=found[0]
    roots=tuple(x for x in objects if x.kind=='NativeRootObservationV1')
    for capture in (*selected.values(),*roots):
        need(type(capture)is HBootstrapObjectV3 and capture.owner is activation.bootstrap_owner,
             'same actual H bootstrap owner and transport view')
        capture.require_original()
    result=_projection(selected,roots,activation.context['source_admission'],role)
    return selected,roots,result

class HostSelectedSourceV3:
    __slots__=('view','role','records','roots','_pin','root_id','components')
    def __init__(self,token,view,role,records,roots,result):
        need(token is _SELECTED,'fixed earlier actual H source selection issuer')
        self.view=view;self.role=role;self.records=records;self.roots=roots
        self._pin,self.root_id,self.components=result
    @property
    def pin(self):return dict(self._pin)
    def require_original(self):
        records,roots,result=_host_selection(self.view,self.role)
        need(self.view.selected_artifact_sources_v3.get(self.role)is self and
             all(records[k]is self.records[k]for k in _FIXED) and
             len(roots)==len(self.roots) and all(a is b for a,b in zip(roots,self.roots)) and
             same(result,(self.pin,self.root_id,self.components)),
             'same actual H descriptor owner and complete selected provenance')
        return self

def resolve_host_artifact_source_v3(view,role,descriptor):
    need(role in _ROLES,'fixed template or renderer artifact source role')
    return _resolve_host_source_v3(view,role,descriptor)

def resolve_host_input_ABI_source_v3(view,descriptor):
    return _resolve_host_source_v3(view,'input_ABI',descriptor)

def _resolve_host_source_v3(view,role,descriptor):
    records,roots,result=_host_selection(view,role)
    registry=view.selected_artifact_sources_v3
    need(type(registry)is dict,'fixed actual H descriptor owner registry')
    if role not in registry:registry[role]=HostSelectedSourceV3(_SELECTED,view,role,records,roots,result)
    owner=registry[role];need(type(owner)is HostSelectedSourceV3,'actual private H source descriptor owner')
    owner.require_original();need(same(descriptor,owner.pin),'exact selected descriptor in its fixed render position')
    return owner

def require_worker_render_operands_v3(context,stage,ordinal,prior):
    """Existing concrete operands are checked; missing input authority stays held."""
    from .worker_channel_v3 import require_capture
    need(stage=='generation' and type(ordinal)is int and ordinal>=0 and type(prior)is tuple and len(prior)==6,
         'exact six source-typed render operands at original generation stage')
    base=require_capture(prior[0],context,'BackendAttemptBase')
    admission=require_capture(prior[5],context,'BackendAdmissionAck')
    need(base.origin=='publication_ack' and admission.origin=='admission_delivery' and
         same(admission.body['backend_attempt'],base.pin),'actual same original base and admitted backend')
    for index,role in ((2,'input_ABI'),(3,'template'),(4,'renderer_source')):
        source=prior[index]
        need(type(source)is WorkerSelectedSourceV3 and source.context is context and source.role==role,
             'actual private selected source in exact render position')
        source.require_original()
    # Schema and actual source selection now exist. They do not supply the
    # missing original public-exposure/transcript/step producer and H inverse.
    # Do not treat DevelopmentRequest or a selected descriptor as that product.
    raise DependencyUnavailable('agent_input_product_v1_original_producer')

def require_host_render_operands_v3(view,intent):
    prior=intent['prior_captures'];ordinal=intent['ordinal']
    need(intent['site']=='render_template' and intent['stage']=='generation' and
         type(ordinal)is int and ordinal==len(view.semantic_requests) and len(prior)==6 and
         view.base is not None and view.admission is not None and
         same(prior[0],view.base.pin) and same(prior[5],view.admission.pin),
         'exact current six-position admitted render intent, never old step or another backend')
    view._prior(prior[0],'BackendAttemptBase');view._prior(prior[5],'BackendAdmissionAck')
    resolve_host_input_ABI_source_v3(view,prior[2])
    resolve_host_artifact_source_v3(view,'template',prior[3])
    resolve_host_artifact_source_v3(view,'renderer_source',prior[4])
    raise DependencyUnavailable('agent_input_product_v1_original_producer')

def require_completed_render_ack_v3(view,ordinal):
    """Actual H effect/intent/observation custody, not an equal wire receipt."""
    from .backend_host_receiver import HEffectReceive,HReceiverPending
    from .backend_capture import CapturedRecord
    receiver=view.receiver
    matches=[x for x in receiver.effects if x.intent['site']=='render_template' and x.intent['ordinal']==ordinal]
    need(len(matches)==1,'one original render effect for this exact step')
    effect=matches[0]
    need(type(effect)is HEffectReceive and effect.receiver is receiver and effect.complete and
         effect.grant is not None and effect.observation is not None,'actual complete original render effect owner')
    need(type(effect.grant)is CapturedRecord and effect.grant.owner is view.owner and
         effect.grant.kind=='EffectGrantV1' and effect.grant._attempt.complete is effect.grant and
         effect.grant._attempt.raw_first is None,'actual original H completed grant publication')
    for pending,kind in ((effect.intent_pending,'EffectIntentV1'),(effect.observation_pending,'EffectObservationV1')):
        need(type(pending)is HReceiverPending and pending.receiver is receiver and
             any(x is pending for x in receiver.history) and pending.kind==kind and pending.complete and
             pending.raw_first is None and not pending.uncertain and pending.send_entered and
             type(pending.encoded_reply)is bytes and pending.sent_count==len(pending.encoded_reply),
             'actual registered fully sent original render grant/observation reply')
    original=effect.intent_pending;observed=effect.observation_pending
    need(original.packet['payload']is effect.intent and original.sequence==effect.sequence and
         original.reply['schema']=='four_effect_grant_delivery_v2' and
         same(original.reply['grant'],effect.grant.pin) and
         same(original.reply['grant_body'],effect.grant.body) and
         observed.packet['payload']is effect.observation and observed.sequence>original.sequence and
         observed.reply['schema']=='four_effect_observation_ack_v1' and
         observed.reply['continued_effects_allowed']is True and
         observed.reply['observation_sequence']==observed.sequence and
         same(observed.reply['grant'],effect.grant.pin) and
         same(effect.observation['grant'],effect.grant.pin) and
         effect.observation['request_sequence']==effect.sequence and
         effect.observation['state']=='complete' and effect.observation['failure']is None and
         not effect.observation['unknown_dimensions'],
         'same actual known-complete render observation and positive acknowledged grant')
    return effect
