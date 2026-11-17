"""Complete immutable plan admission; a disabled deployment cannot be promoted by flags."""
from .common import require,keys,integer,finite,encoded,sha
from .registry import campaign,PEOPLE,ARMS,SEEDS,VERSION,token

REQUIRED=('schema','task_id','protocol_version','system','source_manifest','submission','limits','phase_limits','native_profile',
          'input_index','input_qualification','pre_exposure_review','reference_qualification','semantic_reviews','protected_scoring_authority',
          'trust','protected_panel','paired_schedule','interpretation','exposure_declaration','runtime_environment',
          'isolation_contract','mode_permissions','report_hierarchy','contrasts','policy','cells','dimensions','resource_policy')

def admit(plan,source,contracts):
    keys(plan,REQUIRED)
    require(plan['schema']=='neural055-complete-campaign-plan-v2' and plan['task_id']=='NEURAL-055' and plan['protocol_version']==VERSION,'exact complete programme version')
    require(type(plan['system'])is str and plan['system'] and plan['system'] not in ('R0','R1','R2','R3'),'one independent candidate system identity')
    expected=campaign(plan['system']);require(plan['cells']==expected,'full precommitted960 registry')
    require(plan['dimensions']=={'people':10,'training_images':16540,'development_concepts':330,'queries':200,'candidates':200,'channels':17,'times':100,'training_repeats':4,'query_repeats':80,'image_features':4096},'full original dimensions')
    require(plan['source_manifest']['sha256']==source.identity,'original complete source commitment')
    for name,file in [('isolation_contract','ISOLATION_CONTRACT.json'),('mode_permissions','MODE_PERMISSIONS.json'),('report_hierarchy','REPORT_HIERARCHY.json'),('contrasts','CONTRASTS.json')]:
        require(plan[name]=={'bytes':len(contracts[file]),'sha256':sha(contracts[file])},'exact accepted '+file)
    require(plan['policy']['no_other_cell_state'] is True and plan['policy']['no_query_fit'] is True,'preserved isolation/nesting policy')
    require(plan['policy']['target_access']=='after_all960_safe_original_dispositions' and plan['policy']['diagnostic_incomplete_scoring'] in (False,True),'full safety barrier')
    require(plan['policy']['physical_and_attributable_costs']=='separate_not_summed','cost attribution convention')
    for k in ('fit','infer','reference_fit','reference_infer','prepare','grade_report'):
        finite(plan['phase_limits'][k],True)
    require(plan['phase_limits']['fit']<=43200 and plan['phase_limits']['infer']<=3600,'original selected per-fold limits retained')
    require(plan['native_profile']['model_cap']==268435456 and plan['native_profile']['prediction_cap']==4194304 and plan['native_profile']['programme_cap']==131072,'original programme/model/output caps')
    require(plan['native_profile']['sidecar_abi']=='neural055-native-sidecars-v2','separately versioned selected sidecar allowance')
    require(plan['native_profile']['schema']=='neural055-linux-cgroupfs-broker-profile-v4','prospective measured-envelope native ABI')
    require(plan['policy']['broker_contract']=='neural055-trusted-host-broker-contract-v4','pre-exposure measured-envelope broker contract')
    require(type(plan['semantic_reviews'])is dict,'explicit cell/operation semantic review registry')
    require(plan['paired_schedule']['committed_before_exposure'] is True,'original shared paired schedule commitment')
    from .postscore_policy import admit_policy
    admit_policy(plan['interpretation'])
    return expected,sha(encoded(plan))
