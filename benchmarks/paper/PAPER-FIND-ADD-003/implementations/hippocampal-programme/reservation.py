"""Conservative complete-program logical retention, derived before first launch."""
from core import encoded,expected_counts,need

ACTIONS=('prepare_originals','prepare_fold','native_attempt','train_model','analytic_prior','evaluate_model','grade','report')


def derive(op):
    counts=expected_counts();r=op['phase_resources'];model=op['model_limits'];prep=op['preparation_limits']
    metadata=op['controller_metadata_bytes'];event_cap=op['recovery_limits']['max_record_bytes'];return_cap=op['recovery_limits']['max_metadata_bytes']
    whole_phase_seconds=sum(counts[a]*(op['host_setup_seconds'][a]+op['host_finish_seconds'][a]+sum(r[a][k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))) for a in ACTIONS)
    event_count=16+4*counts['phases']+counts['phases']*(3*max(p['max_cli_calls'] for p in r.values())+64)
    provider_retained=sum(counts[a]*r[a]['host_write_bytes'] for a in ACTIONS)
    preparation_captures=sum(counts[a]*r[a]['host_write_bytes'] for a in ('prepare_originals','prepare_fold'))
    model_bodies=counts['model_slots']*model['max_model_bytes']
    for action in ('train_model','analytic_prior'):
        need(r[action]['max_output_bytes']>=model['max_model_bytes']+2*metadata,'Full admitted model plus completion metadata output capacity')
    for action in ACTIONS:need(r[action]['host_write_bytes']>=r[action]['max_output_bytes'],'Host capture reservation covers the complete declared output extent')
    # Source/static VIEW framing is exactly computable from metadata. All
    # role sets are summed as a conservative upper for the largest one phase.
    inventories=[s['files'] for s in op['sources'].values()]+[p['files'] for p in op['programs'].values()]
    bridge={n.removeprefix('native/'):d for n,d in op['sources']['reference']['files'].items() if n.startswith('native/')};inventories.append(bridge)
    static_views=sum(sum(d['bytes'] for d in files.values())+len(encoded({'schema':'h_closed_role_view_v1','files':files})) for files in inventories)
    dynamic_views=max(5*model['max_training_array_bytes']+model['max_training_metadata_bytes']+metadata,
                      model['max_model_bytes']+metadata,
                      2*model['max_query_array_bytes']+model['max_query_metadata_bytes']+metadata)
    # All outputs remain retained. Private grading adds its own full metadata
    # copies after all producer closure; these are not already provider copies.
    grade_copies=(counts['evaluate_model']*prep['grade_limits']['max_prediction_bytes']
                  +counts['native_attempt']*prep['grade_limits']['max_native_bytes']
                  +counts['prepare_fold']*prep['max_metadata_bytes']+prep['max_grade_index_bytes'])
    host_metadata=(4*counts['phases']*metadata+event_count*event_cap+4*return_cap
                   +op['identity_evidence']['bytes']+32)
    # Model bodies already occur inside provider captures. Charge them once;
    # surplus model reservation remains conservative if it dominates that part.
    other_captures=max(0,provider_retained-preparation_captures-model_bodies)
    concurrent=static_views+dynamic_views+max(p['scratch_bytes']+p['max_output_bytes']+4096+2*16777216 for p in r.values())
    minima={'model_count':counts['model_slots'],'all_model_bytes':model_bodies,
            'captures_receipts_logs_bytes':other_captures+host_metadata,
            'preparation_bytes':preparation_captures+grade_copies,
            'concurrent_partial_bytes':concurrent}
    return {'schema':'h_complete_retention_derivation_v1','minima':minima,'phase_counts':{a:counts[a] for a in ACTIONS},
            'whole_phase_seconds':whole_phase_seconds,'event_count_bound':event_count,'event_body_cap':event_cap,'phase_metadata_file_cap':metadata,
            'provider_retained_upper':provider_retained,'model_bodies_counted_once':True,
            'private_grade_copy_upper':grade_copies,'static_view_upper':static_views,'dynamic_view_upper':dynamic_views,
            'complete_retained_logical_upper':sum(v for k,v in minima.items() if k!='model_count'),
            'measurement':'Conservative logical retained bytes and separately bounded scratch/output capacity; not filesystem block allocation or process RSS; no observed cost or feasibility claim'}
