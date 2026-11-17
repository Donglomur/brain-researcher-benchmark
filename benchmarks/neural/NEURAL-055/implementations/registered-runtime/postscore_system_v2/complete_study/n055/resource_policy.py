"""Exact prospective measured envelopes; no native total-I/O inference."""
from .common import require,parse,sha,encoded
VERSION='n055-measured-envelopes-v1'
EXCLUDED=('native_cumulative_logical_read_bytes','native_cumulative_logical_write_bytes','native_cumulative_file_churn')
DISPOSITIONS=('containment_custody','remaining_envelope_admission','numerical_availability','semantic_mode_qualification','measured_resource_comparison_qualification')
WORDING='Compared under the same prospectively selected measured resource envelopes; native cumulative logical I/O and native file churn were not measured.'

def bind(plan,source,budget):
    raw=source.bodies['contracts/RESOURCE_POLICY_V1.json'];doc=parse(raw)
    expected={'version':VERSION,'bytes':len(raw),'sha256':sha(raw)}
    require(doc['schema']==VERSION and doc['expected_unobserved_native_quantities']==list(EXCLUDED)and doc['interpretation']==WORDING,'exact source-owned resource definition')
    require(plan['resource_policy']==expected and plan['policy']['resource_policy']==expected and plan['native_profile']['resource_policy']==expected and plan['runtime_environment']['resource_policy']==expected,'one pre-exposure policy in source/profile/environment/campaign')
    require(plan['native_profile']['schema']=='neural055-linux-cgroupfs-broker-profile-v4','new prospective profile, no legacy default')
    require(plan['policy']['broker_contract']=='neural055-trusted-host-broker-contract-v4','matching prospective broker contract')
    require(plan['native_profile']['whole_resource_scope']=='original_controller_control_actor_holder_provider_transport_scoring_publication_host_daemon_memory','no silent whole-resource scope narrowing')
    budget.bind_resource_policy(expected,doc)
    return expected

def unobserved(operation,policy):
    return [{'operation':operation,'quantity':key,'value':None,'status':'unobserved_by_selected_observer',
             'scope':'all original actor/holder/provider cumulative native logical I/O or file churn',
             'reason':'managed host adapters, CPU/closure and live capacity do not observe this total',
             'resource_policy':policy,'lower_bound':None}for key in EXCLUDED]

def states(policy,custody,admission,numerical,semantic,resource):
    return {'resource_policy':policy,**dict(zip(DISPOSITIONS,(custody,admission,numerical,semantic,resource)))}

def annotate_contrasts(paired,registry,terminals,system,policy):
    from .reporting import contrast_terms,condition_key
    require([r['id']for r in paired['contrasts']]==['C%02d'%i for i in range(1,33)],'all32 original contrasts retained')
    from .registry import campaign,token
    expected=campaign(system);require(set(terminals)=={token(c)for c in expected},'whole original960 disposition domain for contrast dependencies')
    definitions={r['id']:r for r in registry['contrasts']};qualified=[]
    for row in paired['contrasts']:
        left,right=contrast_terms(definitions[row['id']],system)
        expected_cells=[c for c in expected if condition_key(c)in(left[0],right[0])]
        cells=[terminals[token(c)]for c in expected_cells]
        require(bool(cells)and all(t['cell_key']==c for t,c in zip(cells,expected_cells)),'exact original dependency cell keys, no subset')
        numerical=row['status']=='available'
        semantic=bool(cells)and all(t.get('resource_dispositions',{}).get('semantic_mode_qualification')=='qualified_current_semantics'for t in cells)
        resource=bool(cells)and all(t.get('resource_dispositions',{}).get('resource_policy')==policy and t['resource_dispositions']['measured_resource_comparison_qualification']=='qualified_current_measured_envelope'for t in cells)
        row['qualification_dependencies']={'resource_policy':policy,'expected_cell_keys':[t['cell_key']for t in cells],
            'numerical_availability':'available'if numerical else'unavailable','semantic_mode_qualification':'qualified'if semantic else'unavailable',
            'measured_resource_comparison_qualification':'qualified'if resource else'unavailable','interpretation':WORDING,
            'setup_attribution':'full standalone setup plus own work; physical unique-operation ledger separate',
            'native_cumulative_io_and_churn':'unobserved_by_selected_observer','same_allowances_not_same_consumption':True}
        qualified.append(numerical and semantic and resource)
    complete=all(qualified)
    for row in paired['contrasts']:
        row['qualified_joint_family_disposition']={'status':'available_conditional_only'if complete else'unavailable',
            'required_family':32,'reason':None if complete else'at_least_one_required_numerical_semantic_or_measured_resource_dependency_unavailable',
            'raw_numerical_band_retained_separately':True,'validated_familywise_coverage':False}
    paired['resource_policy']=policy;paired['resource_interpretation']=WORDING
    return paired
