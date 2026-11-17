"""Fixed private fourth creator and its distinct once-only open consumer.

Root producer qualification remains an explicit prerequisite. This module
implements the deterministic projections, captures and downstream live-owner
checks; no serialized record can manufacture the private issuer capability.
"""
import time
from .common import need, same, integer, Store, bounded_size
from .early_resources import ParentCustody, EarlyResources, _spent
from .early_construction import EarlyConstruction, CreationResult, _CAPTURE
from .early_failure import SelectionReadState
from .backend_capture import CanonicalPublisher, CapturedRecord
from .backend_json import canonical
from .precommit_records import validate_type, RECORDS
from . import issuer_prerequisites

_STATIC=object(); _CAPABILITY=object(); _ISSUANCE=object(); _OPENED=object()

class StaticInputChain:
    __slots__=('owner','subject','policy','profile','plan','_token')
    def __init__(self,token,owner,subject,policy,profile,plan):
        need(token is _STATIC,'actual fixed earlier static capture chain')
        self.owner=owner; self.subject=subject; self.policy=policy
        self.profile=profile; self.plan=plan; self._token=token

def prepare_static_issuer_inputs_v1(prior_root,selection,outputs):
    # No attempt to infer the prior-root owner/configuration from task JSON.
    try:
        admitted=issuer_prerequisites.require_prior_static_owner(prior_root,selection)
        return _capture_static_chain(admitted,outputs)
    except BaseException as error:
        from .operator_bootstrap_owner import PriorStaticAdmission
        if type(prior_root)is PriorStaticAdmission:
            prior_root.parent.retain(error,'source_capture','source_refusal','prepare_static_issuer_inputs_v1')
        raise

def _capture_static_chain(admitted,outputs):
    """Fixed call target after the separately implemented prior-root admission.

Its future concrete producer must return the actual prior parent, immutable
plan-values and policy-values. This is not exposed as an alternate admission.
"""
    from .operator_bootstrap_owner import PriorStaticAdmission
    need(type(admitted)is PriorStaticAdmission,'actual fixed earlier installed admission')
    admitted.require_original();admitted.root_admission.require_canonical_publisher_binding_v3()
    need(admitted.static_selection is not None and admitted.plan_values is not None and
         admitted.policy_values is not None,'actual C02 current native captures before static chain')
    parent=admitted.parent
    need(type(parent) is ParentCustody and parent.owner is None and parent.first_raw is None,
         'live actual earlier static owner before this H route')
    need(type(outputs) is Store and outputs.meter is parent.share,'original static owner Store')
    plan_values=admitted.plan_values; policy_values=admitted.policy_values
    subject_fields=set(RECORDS['EarlyConstructionSubject']['fields'])-{'schema'}
    need(type(plan_values) is dict and set(plan_values)==subject_fields,
         'all exact predeclared construction values, no include/exclude projection')
    subject={'schema':'ci_early_construction_subject_v1',**plan_values}
    publisher=CanonicalPublisher(parent,outputs,maximum_bytes=plan_values['maximum_output_bytes'],
        maximum_members=plan_values['maximum_members'],maximum_depth=plan_values['maximum_depth'])
    parent.static_chain_publisher=publisher
    s=publisher.capture('early_construction_subject.json','EarlyConstructionSubject',subject)
    policy={'schema':'ci_early_issuer_bootstrap_policy_v1','subject':s.pin,**policy_values}
    validate_type('EarlyIssuerBootstrapPolicy',policy)
    for key in ('maximum_depth','maximum_input_bytes','maximum_members','maximum_output_bytes'):
        need(policy[key]==plan_values[key],'same earlier static bounds')
    need(policy['capture_root']==plan_values['output_root'],'same fixed private capture root')
    b=publisher.capture('early_issuer_bootstrap_policy.json','EarlyIssuerBootstrapPolicy',policy)
    profile={key:policy[key] for key in RECORDS['EarlyIssuerProfile']['fields']
             if key not in ('schema','schema_produced','bootstrap_policy')}
    profile.update(schema='ci_early_issuer_profile_v1',schema_produced='ci_earlyselection_v2',bootstrap_policy=b.pin)
    r=publisher.capture('early_issuer_profile.json','EarlyIssuerProfile',profile)
    plan={'schema':'ci_constructionplan_v2',**plan_values,'private_issuer_profile':r.pin}
    c=publisher.capture('construction_plan.json','ConstructionPlan',plan)
    chain=StaticInputChain(_STATIC,parent,s,b,r,c)
    admitted.root_admission.bind_static_chain_once_v1(chain)
    return chain

class EarlyIssuerCapability:
    __slots__=('parent','chain','attestation','root_admission','used','_token')
    def __init__(self,token,parent,chain,attestation,root_admission):
        need(token is _CAPABILITY,'fixed root bootstrap capability')
        self.parent=parent;self.chain=chain;self.attestation=attestation
        self.root_admission=root_admission;self.used=False;self._token=token

def bind_early_issuer_v1(parent,root_admission,chain,*,inputs,outputs):
    need(type(parent) is ParentCustody,'same independently admitted parent')
    need(not getattr(parent,'issuer_binding_attempted',False),'one original bootstrap issuer attempt')
    parent.issuer_binding_attempted=True
    try:
        need(type(chain) is StaticInputChain and chain._token is _STATIC,'actual earlier static creator return')
        admitted=issuer_prerequisites.require_root_bootstrap_admission(root_admission,parent,chain)
        parent.assert_live()
        need(parent.owner is None and parent.first_raw is None,'issuer admission precedes seed attachment')
        need(type(inputs) is Store and type(outputs) is Store and
             inputs.meter is parent.share and outputs.meter is parent.share,'original H parent source/output payers')
        # Reauthenticate every actual earlier capture, never follow embedded
        # source/model/data/qualification aliases.
        for capture in (chain.subject,chain.policy,chain.profile,chain.plan):
            parent.share.charge('retained_bytes',len(capture.raw)*16+4096)
            raw=inputs.read(capture.pin,capture.pin['bytes'],metadata=True)
            need(raw==capture.raw,'exact earlier static capture body')
        profile=chain.profile.body;policy=chain.policy.body;subject=chain.subject.body;plan=chain.plan.body
        need(plan['private_issuer_profile']==chain.profile.pin and profile['subject']==chain.subject.pin and
             profile['bootstrap_policy']==chain.policy.pin and policy['subject']==chain.subject.pin,
             'acyclic original static chain')
        need({k:v for k,v in plan.items() if k not in ('schema','private_issuer_profile')}==
             {k:v for k,v in subject.items() if k!='schema'},'exact full plan/subject projection')
        admitted.require_same_source_policy(parent,policy,profile)
        pub=CanonicalPublisher(parent,outputs,maximum_bytes=plan['maximum_output_bytes'],
            maximum_members=plan['maximum_members'],maximum_depth=plan['maximum_depth'])
        parent.issuer_attestation_publisher=pub
        body={'schema':'ci_early_issuer_bootstrap_attestation_v1','bootstrap_policy':chain.policy.pin,
              'profile':chain.profile.pin,'subject':chain.subject.pin,'clock':parent.clock,
              'host_identity':parent.identity,'parent_custody':parent.custody,'reservation':parent.share.row,
              'nonce':parent.nonce,**{k:profile[k] for k in
              ('bootstrap_source','issuer_source','native_qualification','source_qualification')}}
        captured=pub.capture('early_issuer_bootstrap_attestation.json','EarlyIssuerBootstrapAttestation',body)
        cap=EarlyIssuerCapability(_CAPABILITY,parent,chain,captured,admitted)
        parent.issuer_capability=cap
        return cap
    except BaseException as error:
        parent.retain(error,'seed_admission','source_refusal','bind_early_issuer_v1')
        raise

class IssuanceHandle:
    __slots__=('capability','construction','result','observation','raw_first','open_attempted','_token')
    def __init__(self,token,capability,construction):
        need(token is _ISSUANCE,'actual fixed private issuer call')
        self.capability=capability;self.construction=construction;self.result=None
        self.observation=None;self.raw_first=None;self.open_attempted=False;self._token=token

def _selection_body(cap,construction):
    owner=construction.owner;parent=owner.parent;plan=owner.plan;chain=cap.chain
    root=cap.root_admission
    body={'schema':'ci_earlyselection_v2',
        **{k:plan[k] for k in ('agent_policy','development_profile','scientific_template',
                              'source_admission','campaign_id','host_subshare','arm_subshare')},
        'clock':parent.clock,'host_identity':parent.identity,'host_source':parent.source,
        'early_reservation':parent.share.row,'early_owner_binding':parent.binding_pin,
        'construction_plan':chain.plan.pin,'qualification':chain.profile.body['source_qualification'],
        'hard_envelope':root.hard_envelope,'schedule':root.schedule,
        'creation_captures':[construction.attempts[k].capture_pin for k in
                             ('public_interface','public_ABI','paired_views_manifest')],
        'public_interface':construction.attempts['public_interface'].output_pin,
        'public_ABI':construction.attempts['public_ABI'].output_pin,
        'paired_views':construction.attempts['paired_views_manifest'].output_pin}
    validate_type('EarlySelection',body)
    return body

class RootPrecommitIssuer:
    @staticmethod
    def issue_v2(capability,construction):
        need(type(capability) is EarlyIssuerCapability and capability._token is _CAPABILITY,
             'actual fixed bootstrap capability, no wire substitute')
        parent=capability.parent
        need(not capability.used,'one issuance including a failed original attempt')
        capability.used=True
        handle=IssuanceHandle(_ISSUANCE,capability,construction)
        parent.issuance_handle=handle
        try:
            need(type(construction) is EarlyConstruction and construction.owner.parent is parent and
                 parent.issuer_capability is capability,'same live constructor/issuer owner')
            owner=construction.owner
            need(construction.completed==['public_interface','public_ABI','paired_views_manifest'] and
                 not construction.closed and parent.first_raw is None and parent.selection is None,
                 'three exact complete creators precede private fourth operation')
            need(owner.seed['construction_plan']==capability.chain.plan.pin and
                 same(owner.plan,capability.chain.plan.body),'same selected plan before first effect')
            publisher=CanonicalPublisher(owner,construction.outputs,maximum_bytes=owner.plan['maximum_output_bytes'],
                maximum_members=owner.plan['maximum_members'],maximum_depth=owner.plan['maximum_depth'])
            parent.issuance_publisher=publisher
            earlier=[]
            for name in construction.completed:
                result=construction.attempts[name]
                need(type(result) is CreationResult and result.owner is owner and result.complete,
                     'actual same original completed creation handle')
                for d in (result.output_pin,result.capture_pin):
                    owner.host.charge('retained_bytes',d['bytes']*16+4096)
                    construction.outputs.read(d,owner.plan['maximum_output_bytes'],metadata=True)
                    earlier.append(d)
            request={'schema':'ci_creationrequest_v2','operation':'early_selection',
                'owner_binding':parent.binding_pin,'construction_plan':owner.seed['construction_plan'],
                'creator_source':capability.chain.profile.body['issuer_source'],
                'capture_source':owner.plan['capture_source'],'ordered_inputs':earlier,
                'output_path':owner.seed['private_selection_path'],
                'maximum_output_bytes':owner.plan['maximum_output_bytes']}
            validate_type('CreationRequest',request)
            result=CreationResult(_CAPTURE,owner,request)
            handle.result=result;construction.attempts['early_selection']=result
            result.cost_before=owner.cost_prefix();result.started_ns=construction._clock()
            result.request_pin=publisher.capture('creation_early_selection_request.json','CreationRequest',request).pin
            body=_selection_body(capability,construction)
            result.product=body
            result.output_pin=publisher.capture(owner.seed['private_selection_path'],'EarlySelection',body).pin
            result.finished_ns=construction._clock()
            need(result.finished_ns>=result.started_ns,'original issuer interval')
            result.input_readbacks=list(earlier)
            result.capture={'schema':'ci_creationcapture_v2','operation':'early_selection',
                'owner_binding':parent.binding_pin,'request':result.request_pin,'source_readback':earlier,
                'output':result.output_pin,'started_ns':result.started_ns,'finished_ns':result.finished_ns,
                'cost_before':result.cost_before,'cost_after':owner.cost_prefix(),'complete':True,
                'first_error':None,'publication':'complete'}
            result.capture_pin=publisher.capture('creation_early_selection_capture.json','CreationCapture',result.capture).pin
            parent.creation_captures.append(result.capture_pin)
            parent.known_records.extend([result.request_pin,result.output_pin,result.capture_pin])
            construction.completed.append('early_selection')
            observation={'schema':'ci_early_issuance_observation_v1','bootstrap_attestation':capability.attestation.pin,
                'profile':capability.chain.profile.pin,'subject':capability.chain.subject.pin,
                'construction_plan':capability.chain.plan.pin,'owner_binding':parent.binding_pin,
                'creation_captures':body['creation_captures'],'selection':result.output_pin,
                'selection_creation_capture':result.capture_pin,'issuer_nonce':parent.nonce,'cost_prefix':owner.cost_prefix()}
            handle.observation=publisher.capture('early_issuance_observation.json','EarlyIssuanceObservation',observation)
            return handle
        except BaseException as error:
            handle.raw_first=error
            if handle.result is not None:handle.result.first_raw=error
            parent.retain(error,'selection_issue','publication_failure','RootPrecommitIssuer.issue_v2')
            if type(construction) is EarlyConstruction:construction.closed=True
            raise

class AuthenticatedEarlyOpen:
    __slots__=('owner','issuance','capture','selection_pin','_token')
    def __init__(self,token,owner,issuance,capture):
        need(token is _OPENED,'actual completed fixed selection admission')
        self.owner=owner;self.issuance=issuance;self.capture=capture
        self.selection_pin=dict(issuance.result.output_pin);self._token=token

class EarlySelectionAdmission:
    @staticmethod
    def authenticate_open_v1(issuance,state):
        need(type(issuance) is IssuanceHandle and issuance._token is _ISSUANCE,'actual issuer return')
        parent=issuance.capability.parent;owner=issuance.construction.owner
        need(not issuance.open_attempted,'one original selection open including failed admission')
        issuance.open_attempted=True
        try:
            need(issuance.raw_first is None and issuance.result.complete and
                 type(issuance.observation) is CapturedRecord and parent.issuance_handle is issuance,
                 'actual completed fourth capture and issuer observation')
            need(type(state) is SelectionReadState and state.owner is owner and parent.selection is None,
                 'same original unread selection state')
            body=state.read_parse(issuance.construction.outputs,issuance.result.output_pin)
            owner.host.charge('work_units',bounded_size(body))
            validate_type('EarlySelection',body)
            need(same(body,_selection_body(issuance.capability,issuance.construction)) and
                 state.raw==canonical(body,owner.seed['maximum_selection_bytes'],maximum_depth=owner.plan['maximum_depth']),
                 'complete current canonical projection and live original issuer ancestry')
            parent.selection=dict(issuance.result.output_pin)
            state.capture['authenticated']=True
            owner.check();now=time.monotonic_ns();integer(now)
            prefix=owner.cost_prefix()
            need(not prefix['unknown_dimensions'],
                 'actual complete original cost-observation producer required; reservations are not observations')
            opened={'schema':'ci_earlyowneropened_v2','selection':parent.selection,
                'selection_creation_capture':issuance.result.capture_pin,'seed':parent.seed_pin,
                'early_owner_binding':parent.binding_pin,'actual_source_owner':parent.source,
                'host_identity':parent.identity,'owner_nonce':parent.nonce,
                'initial_observed':prefix['observed'],'opened_ns':now}
            pub=CanonicalPublisher(owner,issuance.construction.outputs,maximum_bytes=owner.plan['maximum_output_bytes'],
                maximum_members=owner.plan['maximum_members'],maximum_depth=owner.plan['maximum_depth'])
            parent.selection_open_publisher=pub
            capture=pub.capture('early_owner_opened.json','EarlyOwnerOpened',opened)
            result=AuthenticatedEarlyOpen(_OPENED,owner,issuance,capture)
            parent.admitted_open=result
            return result
        except BaseException as error:
            parent.retain(error,'selection_authenticate','identity_refusal','EarlySelectionAdmission.authenticate_open_v1')
            raise
