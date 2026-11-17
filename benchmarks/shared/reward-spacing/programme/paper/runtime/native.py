"""Complete original-source job/export/collection boundary.

Missing original drivers/models remain operative source gates. No saved model
result can stand in for a source recipe. This module does not launch science.
"""
from pathlib import Path
from reward_common import need, verify_pin, object_sha256, strict_json_loads, unique_records, finite_number,sha256

EXPERIMENT_DRIVERS = {
 'F1_ED1_ED2':'Figure1_ExtDataFig12.py', 'F2_ED4':'Figure2_ExtDataFig4.py',
 'F3_ED6ae':'Figure3_ExtDataFig6ae.py', 'F4_ED6fp':'Figure4_ExtDataFig6fp.py',
 'F5_ED7':'Figure5_ExtDataFig7.py', 'F6_ED8af_ED9':'Figure6_ExtDataFig8af9.py',
 'F7_ED10':'Figure7_ExtDataFig10.py', 'F8':'Figure8.py','ED8fk':'ExtendedDataFig8fk.py'}
SIMULATION_DRIVERS = {
 'TD_full':'microstim_parametersweep.m','TD_scaling':'microstim_scaling_parametersweep.m',
 'TD_scaling_extended':'microstim_scaling_parametersweep_bestFit_extraTrials.m',
 'SOP_full':'sop_parametersweep.m','ANCCR_full':'anccr_parametersweep.m',
 'all_model_fit':'behavior_fit.m'}
EXTRA_ROLES = ('TD_400_refit_recipe','SOP_unconstrained_recipe','ANCCR_latent_inhibition_recipe',
               'fear_ED5_recipe','histology_ED3_recipe','raw_photometry_conversion',
               'raw_video_eztrack_recipe','Supplementary_Note1','Supplementary_Table1','reporting_summary')


def build_native_jobs(source_manifest,model_programme,corpus_pin,environment_pin,figure_obligations=None):
    roles=source_manifest['roles'];jobs=[]
    recipes=[(name,'CODE_figures_and_experimental_analysis/'+path,'python') for name,path in EXPERIMENT_DRIVERS.items()]
    recipes += [(name,'CODE_simulations/'+path,'matlab') for name,path in SIMULATION_DRIVERS.items()]
    recipes += [(name,name,'adjudicated') for name in EXTRA_ROLES]
    for name,role,engine in recipes:
        recipe=roles.get(role)
        missing=[]
        if recipe is None:missing.append(role)
        for dependency in ([] if recipe is None else recipe['requires']):
            if dependency not in roles:missing.append(dependency)
        if environment_pin is None:missing.append('qualified_environment')
        if recipe is None or not recipe.get('export_adapter_qualified'):
            missing.append('qualified_source_export_adapter:'+role)
        panel_ids=[]
        for fig in (figure_obligations or {}).get('figures',[]):
            driver=role.split('/')[-1]
            if driver in fig['native_driver_role']:
                panel_ids += [fig['figure']+letter for p in fig['panels'] for letter in p['letters']]
        subsets={'F3_ED6ae':[('F3',0,8),('ED6',0,5)],
                 'F4_ED6fp':[('F4',0,10),('ED6',5,16)],
                 'F6_ED8af_ED9':[('F6',0,12),('ED8',0,6),('ED9',0,8)],
                 'ED8fk':[('ED8',5,11)]}
        if name in subsets:
            panel_ids=[fig+chr(97+i) for fig,start,end in subsets[name] for i in range(start,end)]
        if name=='fear_ED5_recipe':panel_ids=['ED5'+chr(97+i) for i in range(12)]
        if name=='histology_ED3_recipe':panel_ids=['ED3'+chr(97+i) for i in range(3)]
        panel_contracts={} if recipe is None else recipe.get('panel_contracts',{})
        if set(panel_contracts)!=set(panel_ids):missing.append('adjudicated_panel_provenance_and_content_contracts')
        jobs.append({'job_id':name,'recipe_role':role,'engine':engine,
                     'status':'required-unscorable' if missing else 'source-ready-not-authorized',
                     'missing_roles':missing,'recipe':recipe,'corpus_pin':corpus_pin,
                     'environment_pin':environment_pin,'model_programme_sha256':object_sha256(model_programme),
                     'required_panel_ids':panel_ids,'panel_contracts':panel_contracts,
                     'expected_output_schema':'reward_native_export_v1','source_execution_authority':False})
    return {'schema':'reward_complete_native_jobs_v1','jobs':jobs,
            'all_native_roles_closed':all(not j['missing_roles'] for j in jobs),
            'full_model_programme':model_programme,'execution_authority':False}


def original_process_commit(execution,unit_commit,outcome,expected,unit_commit_bytes=None,scope_commit=None):
    """Consume the original stopped producer/holder/volume commitment fields.

    The caller supplies receipts from a qualified trusted owner, never candidate
    JSON. Existing38-mouse receipts cannot satisfy a full166-panel scope digest.
    """
    need(execution['all_owned_absent'] is True,'Original producer cleanup')
    need(execution['status']=='unit_committed','Original unit committed')
    for key in ('producer_removed_before_capture','all_candidate_holder_volume_absent'):
        need(unit_commit[key] is True,'Original stopped-output boundary')
    need(outcome['all_candidate_resources_absent'] is True and outcome['before_private_inputs'] is True,
         'Original target-last outcome commit')
    need(unit_commit['program_sha256']==expected['program_sha256'],'Exact producer source')
    need(unit_commit['public_inputs']==expected['public_inputs'],'Exact full public inputs')
    if 'scope_sha256' in unit_commit:
        need(unit_commit['scope_sha256']==expected['scope_sha256'],'Full programme scope, not legacy slice')
    else:
        # Original commits lack a scope field. Bind a separate pre-release scope
        # receipt without rewriting or reserializing the original receipt bytes.
        need(scope_commit is not None,'Original unit requires separate full-scope commitment')
        need(scope_commit['before_public_input_release'] is True and
             scope_commit['scope_sha256']==expected['scope_sha256'] and
             scope_commit['program_sha256']==expected['program_sha256'] and
             scope_commit['public_inputs']==expected['public_inputs'],'Full scope/source/input pre-release commitment')
    if unit_commit_bytes is None:
        need(expected.get('engineering_only') is True,'Original byte receipt required for production')
        digest=object_sha256(unit_commit)
    else:
        need(strict_json_loads(unit_commit_bytes)==unit_commit,'Exact parsed original commit bytes')
        digest=sha256(unit_commit_bytes)
    need(outcome['unit_commit_sha256']==digest,'Original unit/outcome byte binding')
    return {'schema':'reward_original_process_bridge_v1','program_sha256':expected['program_sha256'],
            'scope_sha256':expected['scope_sha256'],'output':unit_commit['output'],
            'unit_commit_sha256':digest,'outcome_canonical_sha256':object_sha256(outcome),
            'all_candidate_resources_absent':True,'before_private_inputs':True}


def collect_native(job,root,export_pin,process_receipt,source_manifest,artifact_validators=None):
    need(job['status']=='source-ready-not-authorized','Native source roles unresolved')
    need(process_receipt['status']=='completed' and process_receipt['exit_code']==0,'Native completion')
    need(process_receipt['job_sha256']==object_sha256(job),'Original job identity')
    need(process_receipt['environment_pin']==job['environment_pin'],'Qualified environment identity')
    need(process_receipt['corpus_pin']==job['corpus_pin'],'Exact original corpus')
    need(process_receipt['original_source_pin']==job['recipe']['pin'],'Exact native recipe')
    need(process_receipt['output']==export_pin,'Native output receipt')
    need(process_receipt['all_owned_absent'] is True,'Native process closed before collection')
    # Authenticate every declared source dependency, not just the script name.
    for role in [job['recipe_role']]+job['recipe']['requires']:
        verify_pin(root,source_manifest['roles'][role]['pin'],max_bytes=33554432)
    export=strict_json_loads(verify_pin(root,export_pin,max_bytes=33554432),33554432)
    need(export['schema']=='reward_native_export_v1' and export['job_id']==job['job_id'],'Native export schema')
    need(export['recipe_sha256']==job['recipe']['pin']['sha256'],'Export source binding')
    need(type(export['panels']) is list and type(export['model_cases']) is list,'Native values, not success flags')
    rows=unique_records(export['panels'],['panel_id'])
    need(set(rows)=={(x,) for x in job['required_panel_ids']},'Exact native panel scope')
    from provenance import SealedArtifacts,validate_panel_provenance
    for row in rows.values():
        need(row.get('status') in ('computed','required-unscorable'),'Explicit native panel status')
        if row['status']=='computed':
            need(set(('value','cohort_manifest','statistical_recipe','artifact_pins'))<=set(row),
                 'Native values need membership, inference and figure artifacts')
            need(row['cohort_manifest'] and row['statistical_recipe'],'Native scientific provenance')
            bodies={pin['path']:verify_pin(root,{k:pin[k] for k in ('path','bytes','sha256')},max_bytes=33554432) for pin in row['artifact_pins']}
            need(row['panel_id'] in job['panel_contracts'],'Adjudicated native panel provenance contract')
            validate_panel_provenance(job['panel_contracts'][row['panel_id']],row,
                     SealedArtifacts(bodies,export_pin['sha256']),artifact_validators)
            row['artifact_contract']=job['panel_contracts'][row['panel_id']]['artifact_contract']
        else:need(row.get('reason'),'Missing original obligation is not silent')
    export['receipt_sha256']=object_sha256(process_receipt)
    export['verified_native_collection']=True
    export['collection_tier']='engineering_mock' if process_receipt.get('engineering_only') else 'original_owner_receipt_collected'
    return export


def execute_with_original_owner(owner,job,source_manifest,scope_sha256):
    """Future qualified launch using original process owner, with exact argv.

    The trusted source recipe must supply an independently qualified exporter;
    absent source cannot be substituted by an invented simulation. No invocation
    of this function is made by the BUILD ONLY engineering suite.
    """
    need(job['status']=='source-ready-not-authorized','Full source/runtime/exporter closure')
    owner.assert_execution_authorized(job['job_id'])
    owner.assert_qualified_full_programme(scope_sha256)
    recipe=job['recipe'];need(recipe.get('export_adapter_qualified') is True,'Original export adapter qualification')
    argv=recipe['launch_argv'];need(type(argv) is list and all(type(a) is str for a in argv) and argv,'Literal argv')
    resources=recipe['registered_resources'];need(all(k in resources for k in ('seconds','memory_bytes','temporary_bytes')),
                                                'Measured/preregistered resource limits')
    return owner.run_sealed_original_recipe(argv=argv,source_pins=[source_manifest['roles'][r]['pin'] for r in
               [job['recipe_role']]+recipe['requires']],corpus_pin=job['corpus_pin'],
               environment_pin=job['environment_pin'],resources=resources,
               expected_output_schema=job['expected_output_schema'],job_sha256=object_sha256(job),
               scope_sha256=scope_sha256,target_access=False)


def validate_model_cases(cases,expected_cases):
    """Exact full configuration/condition/iteration support; failures retained."""
    from reward_common import unique_records,finite_number
    keys=['family','configuration_sha256','condition','iteration']
    actual=unique_records(cases,keys);expected=unique_records(expected_cases,keys)
    need(set(actual)==set(expected),'Full model sweep case coverage')
    for key,row in actual.items():
        need(row['status'] in ('computed','never_crossed','failed'),'Explicit simulation outcome')
        if row['status']=='computed':
            need(type(row['trials']) is list and type(row['value']) is list and len(row['trials'])==len(row['value']),
                 'Full simulated trajectory')
            need(row['trials']==list(range(1,expected[key]['n_trials']+1)),'Exact full native trial horizon')
            for v in row['value']:finite_number(v)
            need(type(row['learned_trial']) is int and row['learned_trial']>0,'Native threshold crossing')
            need(row['learned_trial']<=expected[key]['n_trials'],'Threshold crossing within trajectory')
            for field in expected[key].get('required_trajectories',[]):
                need(len(row[field])==expected[key]['n_trials'],'Full required model trajectory')
                for v in row[field]:finite_number(v)
        else:need(row.get('reason'),'No silent failed/noncrossing simulation')
    return {'complete_case_coverage':True,'cases':cases,'scientific_qualification':False}
