"""Complete obligation reconciliation across native, numeric and missing nodes."""
from .protocol import require, unique, digest
from .admission import scope_inventory
from .scientific import OPERATIONS
from .identity import job_digest


def reconcile(manifest, catalog, native_results, product_results, numerical_results):
    """Keep every job and obligation, including failures and unresolved producers.

    Inputs must be previously selected protected receipts, not model answers.
    This is reporting/composition only and cannot upgrade a native schema check
    to scientific agreement or historical reproduction.
    """
    jobs=unique(manifest['jobs']);coverage=unique(manifest['coverage'],'obligation_id')
    require(set(coverage)==scope_inventory(catalog),'full-scope-loss','121 obligations')
    require(set(native_results)<=set(jobs) and set(product_results)<=set(jobs)
            and set(numerical_results)<=set(jobs),'unknown-graph-result','complete graph')
    outputs={}
    for key,job in jobs.items():
        descriptor=manifest['producer_profiles'][job['producer_id']]
        if descriptor['status']!='concrete-source-bound':
            state='required-unscorable';reason=descriptor['gaps']
        elif key in numerical_results:
            nr=numerical_results[key]
            require(nr['job_digest']==job_digest(job),'numeric-job-binding',key)
            require(nr['independent_banks']==['R1','R2'],'missing-independent-bank',key)
            state='numerically-checked-not-native-qualified' if nr['status']=='agreed' else 'required-unscorable'
            reason=nr.get('gaps',[])
        elif key in product_results:
            pr=product_results[key]
            require(pr['job_id']==key,'product-job-binding',key)
            state=pr['validation']['status'];reason=[]
        elif key in native_results:
            state=native_results[key]['status'];reason=native_results[key].get('gaps',[])
        else:state='not-executed';reason=[{'id':'missing-execution','reason':key}]
        outputs[key]={'status':state,'gaps':reason,'depends_on':job['depends_on'],
                      'profile':job['profile'],'scientific_pass':None}
    obligations=[]
    for key,row in sorted(coverage.items()):
        require(row['job_ids'] and set(row['job_ids'])<=set(jobs),'missing-obligation-producer',key)
        obligations.append({'obligation_id':key,'required_job_ids':row['job_ids'],
                            'job_statuses':{j:outputs[j]['status'] for j in row['job_ids']},
                            'scientific_status':'required-unscorable',
                            'reason':'No full scientific qualification selected or demonstrated'})
    return {'schema':'kilosort4_full_obligation_composition_v3','jobs':outputs,
            'obligations':obligations,'obligation_count':len(obligations),
            'source20_paper40_bijectiveI_separate':True,
            'complete_software':False,'scientific_ready':False,
            'counts_added':0,'minimum_core_reference_sorts':44}


def source_coverage(catalog):
    """Record concrete new capabilities without assigning absent figure callers."""
    original=scope_inventory(catalog)
    require(len(original)==121,'catalog-obligation-count','all original scope')
    families={row['id']:dict(row) for row in catalog['jobs']['rows']}
    for key,row in families.items():
        row['whole_family_software_complete']=False
        row['new_concrete_operations']=[]
    families['G02']['new_concrete_operations']=['drift512_processed']
    families['G17']['new_concrete_operations']=['native_ccg_v4_0_2','native_split_projection_v4_0_2',
                                               'native_bimodality_v4_0_2']
    families['G21']['new_concrete_operations']=['waveform_statistics','runtime_mean_sem','score_curves','ablation_deltas',
                                               'native_gui_diagnostic_v4_0_2']
    return {'schema':'kilosort4_full_software_source_coverage_v3',
            'all_obligation_ids':sorted(original),'families':list(families.values()),
            'source_operation_registry':OPERATIONS,'new_operations':len(OPERATIONS),
            'native_parity':False,'full_software_complete':False,
            'unimplemented_not_replaced_by_callbacks':['paper40 original metric','original pyKilosort 11 extraction',
               'historical comparator wrappers and environments','older-method full fitting graph',
               'original figure windows/embeddings and GUI event/capture script',
               'independent banks for unresolved summary constructors','qualified physical observer/capture'],
            'source_512_processed_is_not_raw512_regeneration':True}
