"""Closed original early-profile admission before any paired development launch.

Only bounded ordinary metadata is read here. Model/backend/source/runtime
qualifications remain independent prerequisites; no body is inferred from a
profile hash and no native child is launched by this module.
"""
from pathlib import PurePosixPath
from .common import Store, need, same, descriptor, integer, bounded_size
from .precommit_records import validate_type, DIMENSIONS
from .early_resources import EarlyResources
from . import dependencies

_CONTRACT = object()

class DevelopmentContract:
    __slots__=('owner','profile','profile_pin','policy','policy_pin','worker','whole','environment',
               'worker_pin','whole_pin','input_pins','_token','_identity_capture','_admitted_open',
               'backend','backend_pin','recipe','recipe_pin','artifacts','artifacts_pin','_source_closure_capture',
               'programme_abi','programme_abi_pin','programme_abi_raw','native_anchor','input_store')
    def __init__(self,token,**values):
        need(token is _CONTRACT,'actual fixed complete development profile admission')
        for key,value in values.items():setattr(self,key,value)
        self._token=token
        self._identity_capture=None;self._admitted_open=None
        self._source_closure_capture=None
        self.native_anchor=None
    @property
    def identity_capture(self): return self._identity_capture
    @property
    def identity_pin(self):
        need(self._identity_capture is not None,'actual original complete contract identity capture')
        return self._identity_capture.pin
    @property
    def admitted_open(self): return self._admitted_open
    @property
    def source_closure_capture(self): return self._source_closure_capture
    @property
    def source_closure_pin(self):
        need(self._source_closure_capture is not None,'actual complete earlier H source-list capture')
        return self._source_closure_capture.pin

def _read(owner,store,expected,kind):
    descriptor(expected)
    need(expected['bytes']<=owner.plan['maximum_input_bytes'],'same earlier complete metadata input cap')
    owner.host.charge('retained_bytes',16*expected['bytes']+4096)
    value=store.document(expected,owner.plan['maximum_input_bytes'])
    if kind in ('NativeDevelopmentProfileV3','NativeAgentPolicyV4'):
        from .backend_native_v3_codec import validate_native_type
        validate_native_type(kind,value)
    elif kind is not None:validate_type(kind,value)
    return value

def _admit_original_inputs(owner,store,*,profile_pin,policy_pin,selected_qualification,native_anchor=None):
    need(type(owner)is EarlyResources and owner.parent.owner is owner,'same actual live EarlyOwner')
    parent=owner.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        need(type(store)is Store and store.meter is owner.host,'same already selected ordinary metadata root/host share')
        need(parent.binding_pin is not None and parent.selection is not None,
             'actual earlier owner binding and independently authenticated EarlySelection')
        # Refuse before profile/backend reads when no independently selected
        # fixed source/native/backend binding exists. A wire Pin is insufficient.
        if native_anchor is None:
            dependencies.require('ci_development_profile_and_backend',selected_qualification)
        else:
            from .operator_native_static import require_native_contract_selection_v4
            require_native_contract_selection_v4(owner,native_anchor,profile_pin,policy_pin)
        need(same(profile_pin,owner.plan['development_profile'])and same(policy_pin,owner.plan['agent_policy']),
             'exact profile/policy selected before interface construction or outcome')
        profile=_read(owner,store,profile_pin,'NativeDevelopmentProfileV3' if native_anchor is not None else 'DevelopmentProfile')
        policy=_read(owner,store,policy_pin,'NativeAgentPolicyV4' if native_anchor is not None else 'AgentPolicy')
        if native_anchor is not None:
            from .operator_native_static import require_native_contract_selection_v4
            require_native_contract_selection_v4(owner,native_anchor,profile_pin,policy_pin,profile=profile,policy=policy)
        # Fixed static output ABI is selected before either arm runs. This is
        # ordinary metadata under the existing qualified profile/source gate;
        # reading it grants no native or scientific authority.
        from .backend_json import parse as canonical_parse, canonical
        abi_pin=policy['programme_capture_ABI'];descriptor(abi_pin)
        need(abi_pin['bytes']<=owner.plan['maximum_input_bytes'],'earlier complete ABI input cap')
        owner.host.charge('retained_bytes',16*abi_pin['bytes']+4096)
        abi_raw=store.read(abi_pin,owner.plan['maximum_input_bytes'],metadata=True)
        programme_abi=canonical_parse(abi_raw,owner.plan['maximum_input_bytes'],
            maximum_depth=owner.plan['maximum_depth'],maximum_members=owner.plan['maximum_members'],
            maximum_string_bytes=owner.plan['maximum_input_bytes'])
        validate_type('ProgrammeCaptureABI',programme_abi)
        need(canonical(programme_abi,owner.plan['maximum_input_bytes'],
                       maximum_depth=owner.plan['maximum_depth'])==abi_raw,'exact earlier canonical output ABI')
        need(all(row in policy['source_closure'] for row in
             [programme_abi['source_capture'],programme_abi['assembler_source']]+programme_abi['dispatcher_source']),
             'all fixed output producers and dispatcher belong to the same qualified original source closure')
        need(same(profile['agent_policy'],policy_pin)and same(profile['entry_argv'],policy['entry_argv'])and
             same(profile['environment'],policy['environment']),'same fixed local policy and immutable environment')
        need(PurePosixPath(profile['entry_argv'][0]).is_absolute(),'fixed absolute qualified local policy executable')
        need(profile['parent_launch']==parent.identity['parent_launch'],'unchanged actual early parent-launch identity')
        need(profile['clock_mapping']==parent.clock['mapping_source'],'same original clock mapping source')
        worker=_read(owner,store,profile['worker_envelope'],'DevelopmentWorkerEnvelope')
        whole=_read(owner,store,profile['whole_envelope'],'DevelopmentWholeEnvelope')
        need(same(worker['clock'],parent.clock)and same(whole['clock'],parent.clock),
             'both exact envelopes share the original complete clock; no renewed origin')
        need(same(worker['original_early_reservation'],parent.share.row)and
             same(worker['equal_arm_subshare'],owner.seed['arm_subshare']),
             'same protected complete early row and equal arm opportunity')
        need(whole['parent_owner_custody']==parent.custody and whole['parent_launch']==parent.identity['parent_launch'],
             'same earlier actual aggregate owner and parent-launch')
        for envelope in (worker,whole):
            need(envelope['native_qualification']==profile['native_qualification']and
                 envelope['source_qualification']==profile['source_qualification'],
                 'same earlier fixed source and native qualifications')
        hard=whole['hard_envelope'];limits=worker['limits']
        need(hard['origin_monotonic_ns']==parent.original_origin and hard['run_deadline_ns']==parent.clock['run_deadline_ns']and
             hard['evidence_deadline_ns']==parent.original_deadline,'whole envelope preserves earliest actual interval')
        need(profile['maximum_stream_bytes']==limits['stream_bytes'],'same exact complete stream cap')
        need(limits['whole_cpu_ns']==hard['cpu_ns']and limits['whole_memory_bytes']==hard['memory_bytes']and
             limits['whole_storage_bytes']==hard['retained_storage_bytes'],'worker observations refer to the same whole hard envelope')
        need(limits['cpu_ns']<=hard['cpu_ns']and limits['memory_bytes']<=hard['memory_bytes']and limits['pids']<=hard['pids'],
             'each worker physical ceiling fits original whole envelope')
        environment=_read(owner,store,profile['environment_values'],None)
        need(type(environment)is dict and len(environment)<=256,'finite exact selected environment, no inherited ambient entries')
        for key,value in environment.items():
            need(type(key)is str and 0<len(key)<=256 and '='not in key and '\0'not in key,
                 'literal bounded environment key')
            need(type(value)is str and len(value)<=16384 and '\0'not in value and
                 all(not 0xD800<=ord(c)<=0xDFFF for c in key+value),'literal scalar environment value')
        # This is not a model/weight open. Every backend and initial-state Pin
        # remains a descriptor until its separate qualified fresh-state producer.
        owner.host.charge('work_units',bounded_size(environment))
        backend=_read(owner,store,policy['local_backend'],'LocalBackendProfile')
        recipe=_read(owner,store,policy['initial_state'],'InitialStateRecipe')
        artifacts=_read(owner,store,backend['artifact_selection'],'LocalArtifactSelection')
        need(backend['initial_state_recipe']==policy['initial_state'] and
             backend['environment']==profile['environment'] and
             backend['environment_values']==profile['environment_values'] and
             backend['source_qualification']==profile['source_qualification'] and
             backend['native_qualification']==profile['native_qualification'],
             'same exact backend/state/environment/source/native selection')
        limits=backend['limits'];sampling=backend['sampling']
        need(0<limits['microbatch_tokens']<=limits['batch_tokens']<=limits['context_tokens'] and
             limits['maximum_generation_requests']<=8192 and limits['maximum_header_bytes']<=65536 and
             limits['maximum_response_bytes']<=1048576 and limits['maximum_request_bytes']<=1048576,
             'complete fixed backend byte/request/context bounds')
        need(sampling['seed']<=4294967294 and sampling['temperature_milli']<=2000 and
             sampling['top_p_milli']<=1000 and sampling['min_p_milli']<=1000 and
             sampling['top_k']<=limits['context_tokens'] and sampling['repeat_penalty_milli']<=4000,
             'fixed prospective sampler; no sentinel or per-request override')
        contract=DevelopmentContract(_CONTRACT,owner=owner,profile=profile,profile_pin=dict(profile_pin),
            policy=policy,policy_pin=dict(policy_pin),worker=worker,whole=whole,environment=environment,
            worker_pin=dict(profile['worker_envelope']),whole_pin=dict(profile['whole_envelope']),
            input_pins=[dict(profile_pin),dict(policy_pin),dict(profile['worker_envelope']),
                        dict(profile['whole_envelope']),dict(profile['environment_values'])],
            backend=backend,backend_pin=dict(policy['local_backend']),recipe=recipe,
            recipe_pin=dict(policy['initial_state']),artifacts=artifacts,
            artifacts_pin=dict(backend['artifact_selection']),programme_abi=programme_abi,
            programme_abi_pin=dict(abi_pin),programme_abi_raw=abi_raw,input_store=store)
        contract.native_anchor=native_anchor
        return contract
    except BaseException as error:
        from .early_resources import retain_source_failure
        raise retain_source_failure(parent,error,'admit_development_contract')

class ContractAdmissionHandle:
    __slots__=('owner','admitted_open','inputs','outputs','contract','publisher','raw_first','raw_secondaries',
               'source_closure_attempted','source_closure_capture')
    def __init__(self,owner,admitted_open,inputs,outputs):
        self.owner=owner;self.admitted_open=admitted_open;self.inputs=inputs;self.outputs=outputs
        self.contract=None;self.publisher=None;self.raw_first=None;self.raw_secondaries=[]
        self.source_closure_attempted=False;self.source_closure_capture=None
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)

def contract_identity_body(contract,admitted_open):
    from .early_issuer import AuthenticatedEarlyOpen
    need(type(contract) is DevelopmentContract and contract._token is _CONTRACT and
         type(admitted_open) is AuthenticatedEarlyOpen and admitted_open.owner is contract.owner,
         'same original private contract and actual selection-open return')
    owner=contract.owner;parent=owner.parent
    need(getattr(parent,'admitted_open',None) is admitted_open and
         parent.selection==admitted_open.selection_pin and parent.first_raw is None,
         'same actual authenticated selection without an earlier failure')
    need(contract.input_pins==[contract.profile_pin,contract.policy_pin,contract.worker_pin,
         contract.whole_pin,contract.profile['environment_values']], 'original five exact input identities')
    return {'schema':'ci_admitted_development_contract_v1','owner_binding':parent.binding_pin,
            'selection':admitted_open.selection_pin,'development_profile':contract.profile_pin,
            'agent_policy':contract.policy_pin,'worker_envelope':contract.worker_pin,
            'whole_envelope':contract.whole_pin,'environment_values':contract.input_pins[4]}

class DevelopmentContractPublisher:
    @staticmethod
    def capture_v1(handle):
        from .backend_capture import CanonicalPublisher
        need(type(handle) is ContractAdmissionHandle and
             getattr(handle.owner.parent,'contract_admission',None) is handle,
             'registered actual original admission owner')
        contract=handle.contract
        need(type(contract) is DevelopmentContract and contract._identity_capture is None,
             'one actual contract identity capture before preparation')
        owner=handle.owner
        body=contract_identity_body(contract,handle.admitted_open)
        pub=CanonicalPublisher(owner,handle.outputs,maximum_bytes=owner.plan['maximum_output_bytes'],
            maximum_members=owner.plan['maximum_members'],maximum_depth=owner.plan['maximum_depth'])
        handle.publisher=pub
        capture=pub.capture('development_contract_identity.json','DevelopmentContractIdentity',body)
        need(same(capture.body,body),'completed exact contract projection')
        contract._identity_capture=capture
        owner.parent.known_records.append(capture.pin)
        DevelopmentContractPublisher.capture_source_closure_v1(handle)
        # Identity alone is not a fully admitted contract. Both actual captures
        # must exist before this private open return becomes visible.
        contract._admitted_open=handle.admitted_open
        return contract

    @staticmethod
    def capture_source_closure_v1(handle):
        from .backend_capture import CapturedRecord,CanonicalPublisher
        need(type(handle) is ContractAdmissionHandle and
             getattr(handle.owner.parent,'contract_admission',None) is handle,
             'same registered original admission owner')
        contract=handle.contract
        need(type(contract) is DevelopmentContract and contract._token is _CONTRACT and
             type(contract.identity_capture) is CapturedRecord and
             contract.identity_capture.owner is handle.owner and
             contract.identity_capture.kind=='DevelopmentContractIdentity' and
             type(handle.publisher) is CanonicalPublisher and handle.publisher.owner is handle.owner and
             not handle.source_closure_attempted and contract._source_closure_capture is None and
             contract.admitted_open is None,'one earlier identity then complete source-list attempt')
        handle.source_closure_attempted=True # Before allocation, cost or publication.
        try:
            original=contract.policy['source_closure']
            bound=bounded_size(original)
            handle.owner.host.charge('work_units',bound)
            handle.owner.host.charge('retained_bytes',bound)
            validate_type('PreparedSourceClosureArray',original)
            body=[dict(member) for member in original]
            capture=handle.publisher.capture('development_source_closure.json','PreparedSourceClosureArray',body)
            need(same(capture.body,original),'full ordered same-policy source list; duplicates preserved')
            handle.source_closure_capture=capture;contract._source_closure_capture=capture
            handle.owner.parent.known_records.append(capture.pin)
            return capture
        except BaseException as error:
            handle.retain(error)
            try:handle.owner.parent.retain(error,'development_prepare','publication_failure',
                                          'DevelopmentContractPublisher.capture_source_closure_v1')
            except BaseException as secondary:handle.retain(secondary)
            raise

def admit_development_contract_v3(owner,store,*,admitted_open,outputs,profile_pin,policy_pin,selected_qualification):
    need(type(owner) is EarlyResources and owner.parent.owner is owner,'actual original owner before admission')
    parent=owner.parent
    need(not hasattr(parent,'contract_admission'),'one contract admission, including failed original capture')
    handle=ContractAdmissionHandle(owner,admitted_open,store,outputs)
    parent.contract_admission=handle  # Before every new read/clock/encode/capture.
    try:
        from .early_issuer import AuthenticatedEarlyOpen
        need(type(admitted_open) is AuthenticatedEarlyOpen and admitted_open.owner is owner and
             getattr(parent,'admitted_open',None) is admitted_open,'actual original authenticated open')
        need(type(outputs) is Store and outputs.meter is owner.host and
             str(outputs.root)==owner.plan['output_root'],'same actual fixed H publication root')
        handle.contract=_admit_original_inputs(owner,store,profile_pin=profile_pin,
            policy_pin=policy_pin,selected_qualification=selected_qualification)
        return DevelopmentContractPublisher.capture_v1(handle)
    except BaseException as error:
        handle.retain(error)
        try:parent.retain(error,'development_prepare','publication_failure','admit_development_contract_v3')
        except BaseException as later:handle.retain(later)
        raise

def admit_development_contract(owner,store,*,admitted_open,outputs,profile_pin,policy_pin,selected_qualification):
    """The existing entry now requires the complete V3 caller; no old fallback."""
    return admit_development_contract_v3(owner,store,admitted_open=admitted_open,outputs=outputs,
        profile_pin=profile_pin,policy_pin=policy_pin,selected_qualification=selected_qualification)

def require_original_schedule(contract,schedule):
    need(type(contract)is DevelopmentContract,'actual complete original profile')
    owner=contract.owner
    try:
        owner.host.charge('work_units',bounded_size(schedule))
        validate_type('MatchedSchedule',schedule)
        need(schedule['common_cutoff_ns']<=owner.parent.clock['run_deadline_ns'],
             'no development deadline beyond earliest whole run cutoff')
        # The source-closed UInt already bounds the selected skew. A selected
        # bound wider than the launch window is redundant, not invalid; the
        # actual two start observations must later satisfy both constraints.
        need(schedule['duration_ns']<=owner.seed['arm_subshare']['wall_ns'],
             'equal actual offered duration fits each protected arm wall ceiling')
        limits=contract.backend['limits']
        need(limits['initialization_duration_ns']+limits['shutdown_duration_ns']<schedule['duration_ns'],
             'initialization and protected shutdown fit each unchanged original offered interval')
        owner.check()
        return schedule
    except BaseException as error:
        owner.parent.retain(error,'development_prepare','identity_refusal','require_original_schedule')
        raise


def admit_native_development_contract_v4(owner,store,*,admitted_open,outputs,profile_pin,policy_pin,native_anchor):
    """Current native route: original six captures, same original H and readback.

    No selected_qualification Pin, supplied mapping, or legacy dependency gate
    can authorize this branch. The actual C00-C02 owner remains mandatory.
    """
    need(type(owner)is EarlyResources and owner.parent.owner is owner,'actual original early owner')
    parent=owner.parent
    if parent.first_raw is not None:raise parent.first_raw
    from .early_resources import retain_source_failure
    try:
        need(not hasattr(parent,'contract_admission'),'one original admission including failed attempt')
        handle=ContractAdmissionHandle(owner,admitted_open,store,outputs)
        parent.contract_admission=handle
        from .early_issuer import AuthenticatedEarlyOpen
        need(type(admitted_open)is AuthenticatedEarlyOpen and admitted_open.owner is owner and
             parent.admitted_open is admitted_open,'same actual original authenticated open')
        need(type(outputs)is Store and outputs.meter is owner.host and
             str(outputs.root)==owner.plan['output_root'],'same original H output owner and root')
        handle.contract=_admit_original_inputs(owner,store,profile_pin=profile_pin,
            policy_pin=policy_pin,selected_qualification=None,native_anchor=native_anchor)
        return DevelopmentContractPublisher.capture_v1(handle)
    except BaseException as error:
        handle=getattr(parent,'contract_admission',None)
        if type(handle)is ContractAdmissionHandle:
            handle.retain(error)
        raise retain_source_failure(parent,error,'admit_native_development_contract_v4')
