"""Fixed staged C01/C02 projections and same-original completion consumer.

The prospective native issuer is separate from unavailable genuine native
qualification. Only its actual registered completed captures can bind a chain.
"""
from .operator_intake import require,canonical
from .operator_bootstrap_owner import RootBootstrapAdmission
from .backend_capture import CapturedRecord

SELECTIONS={'native_root_policy':'NativeRootPolicyV1','artifact_roots':'NativeArtifactRootSelectionV1',
            'bootstrap_entry':'BootstrapEntrySelectionV1'}
POLICIES={'native_context_policy':'NativeContextPolicyV2','agent_policy':'NativeAgentPolicyV4',
          'development_profile':'NativeDevelopmentProfileV3'}

def expected_native_static_body_v4(prior,captures,key):
    """Fixed projections only; the caller must possess actual original captures."""
    c=prior.configuration;root=prior.root_admission
    source=c['plan_constants']['source_admission'];publisher=root.require_canonical_publisher_binding_v3()
    tools=prior.tool_owner.binding;tools.require_original()
    root_body={'schema':'four_native_root_policy_v1','root_bootstrap_selection':prior.parent.custody,**c['native_root_configuration']}
    if key=='native_root_policy':return root_body
    artifact_body={'schema':'four_native_artifact_root_selection_v1','root_policy':captures['native_root_policy'].pin,**c['artifact_configuration']}
    if key=='artifact_roots':return artifact_body
    entry_body={'schema':'four_bootstrap_entry_selection_v1','source_root_policy':captures['native_root_policy'].pin,**c['entry_configuration']}
    if key=='bootstrap_entry':return entry_body
    context_body={'schema':'four_native_context_policy_v2','artifact_roots':captures['artifact_roots'].pin,
        'base_agent_policy':c['base_agent_policy']['descriptor'],'base_development_profile':c['base_development_profile']['descriptor'],
        'bootstrap_entry':captures['bootstrap_entry'].pin,'canonical_publisher_source':publisher.source_pin,
        'fixed_bootstrap_fd':199,'fixed_worker_fd':198,'packet_ceiling':65536,'raw_chunk_ceiling':16384,
        'sequence_ceiling':4096,'transport':'AF_UNIX_SOCK_SEQPACKET','original_source_admission':source,
        'source_qualification':c['native_root_configuration']['source_qualification'],
        'native_qualification':c['native_root_configuration']['native_qualification']}
    if key=='native_context_policy':return context_body
    selected_input=c['agent_input_selection']
    from .operator_qualification import same_body
    from .backend_native_v3_codec import validate_native_type
    same_body(selected_input['descriptor'],selected_input['body'])
    validate_native_type('AgentInputSelectionV1',selected_input['body'])
    agent_body={**c['base_agent_policy']['body'],'schema':'four_native_agent_policy_v4',
        'native_context_policy':captures['native_context_policy'].pin,'tool_commands':tools.table_capture.pin,
        'agent_input_selection':selected_input['descriptor']}
    if key=='agent_policy':return agent_body
    profile_body={**c['base_development_profile']['body'],'schema':'four_native_development_profile_v3',
        'native_context_policy':captures['native_context_policy'].pin,'agent_policy':captures['agent_policy'].pin}
    require(key=='development_profile','closed six-role native static projection')
    return profile_body

def expected_native_static_bodies_v1(prior,captures):
    return {key:expected_native_static_body_v4(prior,captures,key)for key in (*SELECTIONS,*POLICIES)}

def bind_native_static_completion_v1(root,anchor):
    require(type(root)is RootBootstrapAdmission,'same actual installed original root')
    root.require_verified_root_v1();p=root.prior_static
    require(root.phase=='verified_root'and not p.native_selection_attempted,'one original native/static binding attempt')
    p.native_selection_attempted=True;p.native_selection_input=anchor
    try:
        # This precise source producer is deliberately not supplied by a dict,
        # callback, duck type or the physical-only worker import component.
        from .backend_native_v3_issuers import RootBootstrapAnchorV2
        require(type(anchor)is RootBootstrapAnchorV2 and
                root.native_context_anchor_attempts.get(anchor.registration_id)is anchor and
                anchor.original_admission is root and anchor.original_parent is p.parent and
                anchor.original_selection is p.configuration,'same actual registered native C00 origin')
        require(anchor.require_completed_policy_profile_v3()is anchor and
                anchor.raw_first is None and not anchor.unknowns,
                'actual completed C01/C01H/C02 source/native ownership, not metadata success')
        require(set(anchor.selection_captures)==set(SELECTIONS)and
                set(anchor.policy_profile_captures)==set(POLICIES),'all and only actual native static captures')
        captures={**anchor.selection_captures,**anchor.policy_profile_captures}
        for key,kind in {**SELECTIONS,**POLICIES}.items():
            capture=captures[key]
            require(type(capture)is CapturedRecord and capture.owner is p.parent and capture.kind==kind and
                    capture._attempt.complete is capture and capture._attempt.raw_first is None,
                    'actual original same-owner publication and complete readback')
        bound=sum(len(c.raw)for c in captures.values())+len(p.invocation.intake.raw)+4096
        p.parent.share.charge('work_units',bound*32);p.parent.share.charge('retained_bytes',bound*16)
        expected=expected_native_static_bodies_v1(p,captures)
        require(all(captures[k].body==body for k,body in expected.items()),'complete exact native/source/tool and unchanged scientific projections')
        plan={**p.configuration['plan_constants'],'agent_policy':captures['agent_policy'].pin,
              'development_profile':captures['development_profile'].pin}
        policy={**p.configuration['policy_constants'],'root_static_selection':captures['native_root_policy'].pin}
        p.native_static_captures=captures;p.native_static_anchor=anchor
        p.plan_values=plan;p.policy_values=policy;p.static_selection=anchor
        return p
    except BaseException as error:
        p.parent.retain(error,'source_capture','source_refusal','bind_native_static_completion_v1');raise


def require_native_contract_selection_v4(owner,anchor,profile_pin,policy_pin,*,profile=None,policy=None):
    """Actual C03 consumer, preserving the completed C00-C02 original owner.

    This is not an authority factory: absent concrete native issuer/qualification
    remains a source prerequisite. No qualified Pin or equal-body clone enters.
    """
    from .early_resources import EarlyResources,retain_source_failure
    require(type(owner)is EarlyResources and owner.parent.owner is owner,'same original early owner')
    parent=owner.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        root=getattr(parent,'operator_root_admission',None)
        require(type(root)is RootBootstrapAdmission and root.parent is parent,'same actual original installed root')
        root.require_verified_root_v1();prior=root.prior_static
        from .backend_native_v3_issuers import RootBootstrapAnchorV2
        require(type(anchor)is RootBootstrapAnchorV2 and prior.native_static_anchor is anchor and
                prior.static_selection is anchor and root.phase=='static_bound' and
                prior.native_selection_attempted and prior.native_selection_input is anchor and
                root.native_context_anchor_attempts.get(anchor.registration_id)is anchor and
                anchor.original_admission is root and anchor.original_parent is parent and
                anchor.original_selection is prior.configuration,'same registered completed native/static input')
        require(anchor.require_completed_policy_profile_v3()is anchor and
                anchor.raw_first is None and not anchor.unknowns,'actual completed native root and entry issuer')
        captures=prior.native_static_captures
        require(set(captures)==set(SELECTIONS)|set(POLICIES),'all six actual earlier captures')
        bound=sum(len(c.raw)for c in captures.values())+4096
        owner.host.charge('work_units',bound*32);owner.host.charge('retained_bytes',bound*16)
        for key,kind in {**SELECTIONS,**POLICIES}.items():
            c=captures[key]
            require(type(c)is CapturedRecord and c.owner is parent and c.kind==kind and
                    c._attempt.complete is c and c._attempt.raw_first is None and
                    (anchor.selection_captures if key in SELECTIONS else anchor.policy_profile_captures)[key]is c,
                    'same actual completed native publication; no reconstructed Pin')
        expected=expected_native_static_bodies_v1(prior,captures)
        require(all(captures[k].body==v for k,v in expected.items()),'unchanged complete source and scientific projections')
        require(profile_pin==captures['development_profile'].pin==owner.plan['development_profile'] and
                policy_pin==captures['agent_policy'].pin==owner.plan['agent_policy'],
                'exact earlier current profile and policy selections')
        require((profile is None)==(policy is None),'both readbacks or neither')
        if profile is not None:
            require(profile==captures['development_profile'].body and policy==captures['agent_policy'].body,
                    'whole current profile/policy actual readback equality')
            require(profile['native_context_policy']==policy['native_context_policy']==captures['native_context_policy'].pin and
                    profile['agent_policy']==policy_pin,'same original native branch, no policy loop or old-route mix')
            entry=captures['bootstrap_entry'].body
            require(profile['entry_argv']==policy['entry_argv']==[entry['interpreter_absolute'],'-I',entry['entry_absolute']],
                    'source-fixed selected entry; no shell, PATH, or inferred pin path')
        return anchor
    except BaseException as error:
        raise retain_source_failure(parent,error,'require_native_contract_selection_v4')
