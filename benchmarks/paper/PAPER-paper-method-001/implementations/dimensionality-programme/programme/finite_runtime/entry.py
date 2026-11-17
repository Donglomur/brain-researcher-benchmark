"""Ordinary manifest-file entry for complete paired and named finite programmes.

The frozen policy is BUILD_ONLY. A future operator must qualify/version that policy
and all 24 gates; a caller-supplied flag or inert control never enables science.
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from .common import require,decode,encode,error_record,identity,FRAME_LIMIT,Refusal
from .authority import Authority
from .resources import Meter,Limits,Journal
from .filesystem import Store
from .planner import Contracts,Plan,shared_scientific_identity,paired_input_target_identity
from .process import QualifiedMonitor,ProcessHost
from .participant import Participant
from .science import Science
from .references import References
from .preparation import Preparation
from .truth import validate_truth_graph
from .campaign import Campaign,execute_campaigns
from .objects import get_object

PACKAGE=Path(__file__).resolve().parent.parent
CONDITIONS={'complete_finite_programme_v1':('full-A','full-B'),
            'complete_reproduce':('reproduce-A','reproduce-B'),
            'complete_improve':('improve-A','improve-B'),
            'complete_source_diagnostic':('source-diagnostic-A','source-diagnostic-B')}
for _route in ('full','reproduce','improve','source-diagnostic'):
    for _arm in ('A','B'):CONDITIONS[_route+'-'+_arm]=(_route+'-'+_arm,)


def bounded_control(path,cap=FRAME_LIMIT):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        import stat
        st=os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_size<=cap,'INVALID_BOOTSTRAP_CONTROL')
        body=os.read(fd,cap+1)
        require(len(body)==st.st_size and len(body)<=cap,'BOOTSTRAP_CONTROL_CHANGED')
        return decode(body),len(body)
    finally:os.close(fd)


def source_policy():
    # This path is fixed by the installed source package, never supplied in a request.
    policy,n=bounded_control(PACKAGE/'TRUSTED_POLICY.json')
    require(policy['status']=='QUALIFIED_EXECUTION_POLICY','BUILD_ONLY_SCIENTIFIC_EXECUTION_DISABLED')
    return policy,n


def manifest_data(store,descriptor,max_bytes):
    """A full plan/data object is exact chunked ordinary planning metadata only."""
    if descriptor.get('schema')=='finite_object_ref_v1':
        return get_object(store,descriptor,allowed_roles={'qualified_plan_chunk'},max_bytes=max_bytes)
    return store.json(descriptor,{'qualified_plan_index'})


def assemble_arm(spec,route,output_dir,policy,bootstrap_reads):
    require(spec['arm']==route[-1],'ARM_SPEC_SUBSTITUTION')
    workspace=Path(spec['workspace_root']).absolute()
    require(workspace==Path(output_dir).absolute()/('arm-'+spec['arm']),
            'WORKSPACE_OUTSIDE_SELECTED_OUTPUT_ROOT')
    authority=Authority(policy,spec['signed_permit'],now=time.time)
    permit=authority.permit
    require(str(workspace)==permit['workspace_root'],'WORKSPACE_NOT_BOUND_BY_ORIGINAL_AUTHORITY')
    require(spec['limits']==permit['limits'] and spec['original_deadline']==permit['original_deadline'],
            'ORIGINAL_CAPS_OR_DEADLINE_CHANGED')
    require(spec['clock_domain']==permit['clock_domain']==policy['clock_domain'],
            'ORIGINAL_MONOTONIC_CLOCK_DOMAIN_CHANGED')
    prior=spec.get('resume_resources')
    if prior is not None:require(identity(prior)==permit['resume_resource_sha256'],'UNSIGNED_RESUME_HISTORY')
    meter=Meter(Limits(**spec['limits']),spec['original_deadline'],prior=prior)
    meter.reserve('read_bytes',bootstrap_reads,'original_bootstrap_control_reads')
    meter.observe('read_bytes',bootstrap_reads)
    meter.checkpoint('before_arm_journal')
    journal=Journal(workspace/'ORIGINAL_EVENTS.jsonl',meter,prior_head=spec.get('resume_journal_head'))
    store=None
    try:
        denial=policy['body_policy']
        store=Store(workspace,meter,journal,denied_paths=denial['paths'],
            denied_hashes=denial['hashes'],denied_prefixes=denial['prefixes'],
            paper_admitter=lambda desc:authority.permit_paper(desc,spec['arm']))
        ceiling=permit['max_metadata_object_bytes']
        require(identity(spec['programme_manifest'])==permit['programme_manifest_descriptor_sha256'],
                'UNSIGNED_BOOTSTRAP_MANIFEST_DESCRIPTOR')
        raw=manifest_data(store,spec['programme_manifest'],ceiling)
        require(identity(raw)==permit['programme_manifest_sha256'],'PROGRAMME_MANIFEST_SUBSTITUTION')
        contracts=Contracts(raw['accepted_contracts'])
        require(contracts.hash==policy['accepted_contracts_sha256'],'REPLACED_ACCEPTED_SCIENTIFIC_CONTRACT')
        plan=Plan({**raw['plan'],'route':route},contracts)
        authority.admit(plan=plan.hash,source_manifest=plan.value['source_manifest_sha256'],route=route,
                        input_registry=plan.value['input_registry_sha256'],effect='arm_assembly')
        data=manifest_data(store,raw['data_manifest'],ceiling)
        require(identity(data)==plan.value['data_manifest_sha256'],'UNSEALED_PROGRAMME_DATA_GRAPH')
        require(identity(data['initial_registry'])==plan.value['input_registry_sha256'],
                'INPUT_REGISTRY_SUBSTITUTION')
        require(identity(data['case_manifest_identity'])==plan.value['case_manifest_sha256'],
                'CASE_MANIFEST_SUBSTITUTION')
        require(plan.value['resource_preflight']['limits_sha256']==identity(spec['limits']),
                'PREFLIGHT_CAPS_CHANGED')
        preflight_whole_graph(plan,data,spec['limits'])
        backend=QualifiedMonitor(raw['isolation_monitor'],authority,store)
        host=ProcessHost(meter,journal,store,backend)
        require(raw['participant_source']['source_manifest_sha256']==plan.value['source_manifest_sha256'],
                'PARTICIPANT_SOURCE_DIFFERS_FROM_SIGNED_PLAN')
        actor=Participant(raw['participant_source'],run_id=spec['run_id'],
            participant_id=raw['participant_source']['participant_identity'],arm=spec['arm'],
            plan_hash=plan.hash,host=host,inputs=store,output_store=store,
            work_root=workspace/'jobs',journal=journal,meter=meter,tools=raw['participant_tools'])
        science=Science(host,authority,store,journal,meter,raw['scientific_source'],workspace/'jobs',
                        raw['scientific_environment'])
        preparation=Preparation(plan,science,journal,meter,dict(data['initial_registry']))
        # The callback is this concrete source-owned case resolver. It is never loaded
        # from the manifest and cannot be supplied by participant code.
        refs=References(contracts,science,meter,journal,science.source['source_manifest_sha256'],
                        data['reference_qualification'],lambda case:campaign.case_arrays(case),
                         lambda case,stage:preparation.truth.materialize(case,stage)['truth'])
        campaign=Campaign(plan,data,actor,science,refs,preparation,store,journal,meter,authority)
        campaign.bootstrap={'control_bytes_charged':bootstrap_reads,'prior':prior}
        return campaign
    except BaseException as primary:
        secondary=[]
        if store is not None:
            try:store.close()
            except BaseException as exc:secondary.append(exc)
        try:journal.close(primary,secondary)
        except BaseException as exc:secondary.append(exc)
        # The original exception survives even if cleanup also failed.
        if secondary:primary.add_note('Secondary closure failures: '+repr([error_record(x) for x in secondary]))
        raise


def preflight_whole_graph(plan,data,limits):
    """Admit complete source-selected work and all outcomes before the first child."""
    require(plan.value['scientific_plan_sha256']==shared_scientific_identity(plan,data),
            'SCIENTIFIC_PLAN_IDENTITY_NOT_DERIVED_FROM_ORIGINAL_SCOPE')
    require(plan.value['same_inputs_A_B_sha256']==paired_input_target_identity(plan,data),
            'PAIRED_INPUT_TARGET_CONTRACT_NOT_CONTENT_BOUND')
    require(data['case_by_id']=={x['case_id']:x for x in data['R_cases']+data['I_cases']},
            'CASE_LOOKUP_SUBSTITUTION')
    validate_pairwise_manifest(plan,data)
    p=plan.value['resource_preflight']
    truth_plan=validate_truth_graph(data)
    require(p['truth_materialization_read_capacity']==truth_plan['additional_materialization_read_capacity'] and
            p['worst_case_admitted']['read_bytes']>=p['truth_materialization_read_capacity'],
            'TRUTH_MATERIALIZATION_COSTS_NOT_PREFLIGHTED')
    require(p['budget_qualification_id'] and p['whole_graph_sha256']==identity(data['job_graph']),
            'UNQUALIFIED_WHOLE_PROGRAMME_COST_PLAN')
    require(set(data['job_graph']['operators'])==set(plan.contracts.operators),'JOB_GRAPH_SCOPE_REDUCTION')
    require(set(data['job_graph']['obligations'])==set(plan.contracts.obligations),'JOB_GRAPH_OBLIGATION_REDUCTION')
    require(set(data['input_role_bindings'])=={x['id'] for x in plan.contracts.documents['INPUTS']['roles']},
            'COMPLETE_26_INPUT_ROLE_BINDINGS_REQUIRED')
    require(data['job_graph']['reference_census']==plan.contracts.preflight_census(),
            'JOB_GRAPH_REFERENCE_REDUCTION')
    for key in ('read_bytes','write_bytes','jobs','events','child_cpu_seconds','controller_cpu_seconds'):
        require(p['worst_case_admitted'][key]<=limits[key],'WHOLE_GRAPH_EXCEEDS_SELECTED_BUDGET',key)
    require(p['maximum_failure_closure_bytes']<=limits['closure_bytes'],
            'FAILURE_CLOSURE_CAPACITY_INSUFFICIENT')
    require(p['includes_failed_attempts'] and p['includes_all_provider_jobs'] and
            p['includes_all_descendants_and_original_streams'] and p['no_success_refund'],
            'INCOMPLETE_WHOLE_GRAPH_RESOURCE_PREFLIGHT')


def run(manifest_path,output_dir,condition=None):
    """Central ABI: manifest FILE path, output DIRECTORY, optional named condition."""
    condition=condition or 'complete_finite_programme_v1'
    campaigns=[];results=None;primary=None;secondary=[]
    # Public policy refusal deliberately occurs before caller manifests/data/keys.
    policy,policy_bytes=source_policy()
    require(condition in CONDITIONS,'UNKNOWN_NAMED_CONDITION')
    original_control=policy['invocation_controls'].get(str(Path(manifest_path).absolute()))
    require(original_control is not None,'INVOCATION_CONTROL_NOT_SEPARATELY_SELECTED')
    manifest,n=bounded_control(manifest_path)
    require(n==original_control['bytes'] and identity(manifest)==original_control['canonical_sha256'],
            'SELECTED_INVOCATION_CONTROL_CHANGED')
    require(manifest['schema']=='finite_complete_invocation_v1','WRONG_INVOCATION_SCHEMA')
    require(manifest['condition']==condition,'CONDITION_MANIFEST_MISMATCH')
    routes=CONDITIONS[condition]
    require(set(manifest['arms'])=={r[-1] for r in routes},'INVOCATION_ARM_SCOPE_CHANGED')
    try:
        for route in routes:
            campaigns.append(assemble_arm(manifest['arms'][route[-1]],route,output_dir,policy,policy_bytes+n))
        results=execute_campaigns(campaigns)
        for c in campaigns:c.checkpoint('final_all_arm_completion')
    except BaseException as exc:primary=exc
    finally:
        for c in campaigns:
            try:c.store.close()
            except BaseException as exc:secondary.append(exc)
        for c in campaigns:
            try:c.journal.close(primary,secondary)
            except BaseException as exc:secondary.append(exc)
    if primary is not None:
        if secondary:primary.add_note('Original secondary closure failures: '+repr([error_record(x) for x in secondary]))
        raise primary
    if secondary:raise Refusal('FINAL_CLOSURE_FAILED',[error_record(x) for x in secondary])
    return {'condition':condition,'arms':results,'scientific_benchmark_ready':False,
            'all24_gate_evidence_and_original_completion_required':True}


def validate_pairwise_manifest(plan,data):
    rows=data['mandatory_pairwise_manifest'];ids=[r['comparison_id'] for r in rows]
    require(len(ids)==len(set(ids)),'DUPLICATE_MANDATORY_COMPARISON')
    primary={(r['key_id'],r['endpoint'],r['reference_variant_id']) for r in rows
             if r['kind']=='primary_bank_variant'}
    expected=set()
    for key in plan.contracts.keys:
        expected.update((key,'point',v['id']) for v in plan.contracts.variants(key))
        expected.update((key,'uncertainty',v['id']) for v in plan.contracts.uncertainty_variants(key))
    require(primary==expected,'MANDATORY_UNSELECTED_REFERENCE_OR_CI_OMITTED')
    versions=data['qualified_literal_source_versions']
    require(set(versions)=={'author_infinite_f18de358','author_finite_f18de358',
        'notebook_on_Stringer','notebook_on_TVSD','notebook_Linear_example',
        'notebook_Final_dim','notebook_nonlin_manifold'} and len(versions)==7,
        'EXACT_SEVEN_LITERAL_SOURCE_VERSIONS_REQUIRED')
    diagnostic={(r['key_id'],r['reference_id'],r['reference_source_version']) for r in rows
                if r['kind']=='diagnostic_or_literal'}
    expected_diagnostic=set()
    for key_id,key in plan.contracts.keys.items():
        for ref in plan.contracts.bank.values():
            if int(ref['id'][3:5])<13 or key['family'] not in ref['families']:continue
            for version in (versions if ref['id']=='REF13_LITERAL_SOURCE' else [ref['variants'][0]]):
                expected_diagnostic.add((key_id,ref['id'],version))
    require(diagnostic==expected_diagnostic,'MANDATORY_DIAGNOSTIC_OR_LITERAL_VERSION_OMITTED')
    require(len(rows)==len(primary)+len(diagnostic),'REPEATED_COMPARISON_SCOPE')
    require(data['literal_source_version_qualification_id'],'LITERAL_VERSION_PROVENANCE_UNQUALIFIED')
