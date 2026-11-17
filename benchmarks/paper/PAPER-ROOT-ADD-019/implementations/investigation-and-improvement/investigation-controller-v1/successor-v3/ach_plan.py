"""Complete original native/improvement controller plan, no support shortcuts."""
from ach_util import need,pin,require_pin,exact_fields

def compile_programme(libraries,study,null_policies,policies,admission):
    exact_fields(admission,('study_pin','feature_manifest_pin','field_mapping_pin','original_members_pin',
        'native_policy_pin','null_selection_pin','ED_dispositions_pin','source_environment_pin',
        'complete_resource_profile_pin','authoring_commitment_pin','authentic_evidence_qualified'),
        'complete independently authenticated study admission')
    for k,v in admission.items():
        if k!='authentic_evidence_qualified':require_pin(v)
    need(admission['study_pin']==pin(study),'same exact independently admitted study')
    # The actual authority/issuer check precedes this compiler in the concrete
    # controller. A Boolean in this structure is not its own authorization.
    need(admission['authentic_evidence_qualified'] is True,'actual fields/clocks/cohorts/support remain admission facts')
    need(type(null_policies) is list and null_policies,'mandatory actual null policy cannot be absent')
    nulls={}
    for policy in null_policies:
        mapping=libraries.get('core','nulls').validate_and_map(study,policy)
        need(mapping['id'] not in nulls,'unique actual selected null realization')
        nulls[mapping['id']]=mapping
    need(admission['null_selection_pin']==pin(null_policies),'same independently selected complete null work')
    core=libraries.get('core','study').compile_plan(study,sorted(nulls))
    native_contract=libraries.native_contract()
    native_jobs=libraries.get('native','dispatch').plans(native_contract)
    need(len(native_jobs)==111,'unchanged full nativeV3 dispatch graph')
    counts=dict(core['counts'])
    counts['candidate_investigator_contexts']=counts['candidate_final_bundles']
    counts['candidate_provider_and_search_actions']='actual policy-bounded ledger; additional to final bundle count'
    counts['original_member_dispositions']=394
    counts['ED_dispositions']=10
    return {'schema':'ach_complete_investigation_controller_plan_v1','core':core,'native_jobs':native_jobs,
        'null_mappings':nulls,'null_policies':null_policies,'study_pin':pin(study),'policy_pin':pin(policies),
        'admission_pin':pin(admission),'counts':counts,'new_task_count':0,
        'runtime_qualified':False,'scientific_qualified':False}

def fitting_schedule(plan):
    """Lazily enumerate every complete bundle; inner reference work is executed
    by accepted nested_panel, never replaced by this symbolic count generator.
    """
    for key,spec in plan['core']['panels'].items():
        yield {'panel_key':key,'phase':'reference_nested_fit' if spec['actor']=='operator' else 'candidate_investigation',
               'spec':spec,'four_heads':list(spec['heads']),'final_model_id':spec['bundle_fit_id']}

def context_schedule(plan,study):
    """Every separate access/reference, cohort, animal and realization realm.

    A context has four independently fitted variants and one shared-target
    obligation barrier. No state/feedback crosses these context keys.
    """
    panels=plan['core']['panels'];groups={}
    for key,spec in panels.items():
        group=(spec['realization'],spec['actor'],spec['cohort'],spec['animal'])
        groups.setdefault(group,{})[spec['variant']]=key
    for group,variants in groups.items():
        need(set(variants)=={'B','D','ACh','F'},'all original variants before query realm')
        yield {'realization':group[0],'actor':group[1],'cohort':group[2],'animal':group[3],
               'variant_panels':variants,'session_order':study['sessions'][group[3]]}
