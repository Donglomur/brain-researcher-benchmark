"""Complete influence sweep construction and native-output support checks.

This module does not solve an operator. Native solvers below own that work;
literal branch identities are never converted to a paper-equation reference.
"""
from dataclasses import dataclass
from .codec import need, finite_number, encode, pin


@dataclass(frozen=True)
class Sweep:
    threshold: int
    seed: str
    seed_ids: tuple
    target_ids: tuple
    operator_branch: str
    graph_variant: str
    metadata_identity: str


def sensory_sweeps(metadata, *, sensory_seed_order, effector_ids, mapping,
                   metadata_identity, operator_branch, graph_variant, meter):
    """The full sensory seed_02 list, not 19 independently stimulated groups.

    BANC panels_sensory_motor.R82-101 takes distinct non-NA seed_02 values
    from the complete precomputed sensory cohort, then selects each seed's
    root IDs from the complete metadata. The sensory/effector cohorts must
    have their own authentic upstream lineage. This function does not invent
    cohort rules from the reduced metadata projection.
    """
    need(type(metadata) is tuple and type(sensory_seed_order) is tuple and
         type(effector_ids) is tuple, 'immutable complete admitted tables')
    need(graph_variant in ('full_CNS_source/sequential_supplied_calculator',
                           'no_neck_CNS_source/sequential_supplied_calculator'),
         'literal parallel loop hardcodes threshold5; it cannot produce distinct 3/5/10 sweeps')
    need(len(sensory_seed_order)==len(set(sensory_seed_order)) and
         all(type(x) is str and x for x in sensory_seed_order), 'complete unique seed_02 order')
    need(len(effector_ids)==len(set(effector_ids)) and
         all(type(x) is str and x for x in effector_ids), 'complete unique target IDs')
    need(len(mapping['seed_order'])==19 and len(mapping['target_order'])==17
         and len(mapping['matched_groups'])==14, 'frozen GCS complete 17x19/14x14 support')
    need(len(metadata_identity)==64, 'explicit complete metadata binding')
    meter.admit_rows(len(metadata))
    byseed={x:[] for x in sensory_seed_order}
    all_ids=set()
    for row in metadata:
        need(type(row) is dict and type(row.get('root_id')) is str, 'unaltered string root ID')
        all_ids.add(row['root_id'])
        if row.get('seed_02') in byseed:
            if row['root_id'] not in byseed[row['seed_02']]:
                byseed[row['seed_02']].append(row['root_id'])
    need(set(effector_ids)<=all_ids, 'every target is in complete metadata')
    need(all(byseed.values()), 'every declared seed has original source IDs')
    meter.admit_pairs(3*len(sensory_seed_order)*len(effector_ids))
    return tuple(Sweep(t,s,tuple(byseed[s]),effector_ids,operator_branch,
                       graph_variant,metadata_identity)
                 for t in (3,5,10) for s in sensory_seed_order)


def validate_native_rows(rows, *, ordered_node_ids, score_column, branch,
                         raw_operator_identity, meter):
    """Validate complete native response before selecting effector targets."""
    need(branch in ('captured_Python_unsigned_literal','captured_Python_signed_literal',
                    'captured_R_unsigned_literal','captured_R_signed_labelled_literal',
                    'R_to_Python_literal_wrapper'), 'only explicit literal native responses')
    need(type(rows) is tuple and len(rows)==len(ordered_node_ids),
         'complete native all-node response required')
    meter.admit_rows(len(rows))
    need(tuple(r.get('id') for r in rows)==tuple(ordered_node_ids),
         'literal native ordered node support')
    need(len(set(ordered_node_ids))==len(ordered_node_ids), 'unique node identity')
    need(all(type(r.get('is_seed')) is bool and finite_number(r.get(score_column))
             for r in rows), 'finite native response and literal seed flags')
    signed = branch=='captured_Python_signed_literal'
    if not signed:
        need(all(r[score_column]>=0 for r in rows), 'literal magnitude response contract')
    return {'rows':rows,'operator_identity':raw_operator_identity,
            'branch':branch,'raw_response_hash':pin(encode(rows))['sha256'],
            'residual_qualified':False,'native_parity_qualified':False}


def mapped_sensory_rows(sweep, native_rows, effector_lookup, mapping, *, score_column,
                        normalizer_seed_count, meter):
    """Exact explicit join support before the captured R normalizer.

    The loop's influence_norm convention must supply its actual denominator;
    no inferred replacement from a graph node count is permitted. Duplicated
    distinct effector annotation rows are preserved as the original left join.
    """
    need(type(normalizer_seed_count) is int and normalizer_seed_count>0,
         'source loop normalization denominator required')
    lookup={}
    for row in effector_lookup:
        need(set(row)>={'id','target','target_super_class'}, 'complete distinct effector join')
        lookup.setdefault(row['id'],[]).append(row)
    need(set(sweep.target_ids)<=set(lookup), 'every target has complete original annotation')
    seed=mapping['seed_map'].get(sweep.seed,sweep.seed)
    if seed not in mapping['seed_order']:
        return ()
    result=[]
    selected_targets=set(sweep.target_ids)
    for row in native_rows:
        if row['id'] not in selected_targets:
            continue
        for annotation in lookup[row['id']]:
            target=mapping['target_map'].get(annotation['target'],annotation['target'])
            if target in mapping['target_order']:
                value=row[score_column]
                need(finite_number(value), 'finite joined influence')
                result.append({**row,**annotation,'seed':seed,'target':target,
                               'influence_original':value,
                               'influence_norm_original':value/normalizer_seed_count,
                               'influence':value,'influence_norm':value/normalizer_seed_count})
    meter.admit_rows(len(result))
    return tuple(result)


def full_panel(normalized_rows, *, mapping, threshold, meter):
    """Complete 17x19 values/support; missing cells are never implicit success.

    Original plotting fills absent cells with zero. Both that plot value and
    the distinct observed-support mask are returned, preventing missingness
    from passing a reconstruction test as an observed zero.
    """
    need(threshold in (3,5,10), 'all source/extension thresholds explicit')
    targets=tuple(mapping['target_order']); seeds=tuple(mapping['seed_order'])
    groups={}
    for row in normalized_rows:
        key=(row['target'],row['seed'])
        need(key[0] in targets and key[1] in seeds, 'full mapped matrix namespace')
        need(finite_number(row['influence_log_minmax']) and
             0<=row['influence_log_minmax']<=1, 'native normalizer output in [0,1]')
        groups.setdefault(key,[]).append(row['influence_log_minmax'])
    meter.admit_pairs(len(targets)*len(seeds))
    import math
    values=tuple(tuple(math.fsum(groups[(t,s)])/len(groups[(t,s)])
                       if (t,s) in groups else None for s in seeds) for t in targets)
    return {'threshold':threshold,'target_order':targets,'seed_order':seeds,
            'values':values,'supported':tuple(tuple(v is not None for v in r) for r in values),
            'original_plot_zero_filled':tuple(tuple(0.0 if v is None else v for v in r) for r in values),
            'historical_snapshot_equivalence':False}


def collect_three_panels(panels, mapping):
    need(type(panels) is tuple and tuple(p['threshold'] for p in panels)==(3,5,10),
         'all three complete threshold panels required')
    for p in panels:
        need(tuple(p['target_order'])==tuple(mapping['target_order']) and
             tuple(p['seed_order'])==tuple(mapping['seed_order']), 'unchanged complete matrix support')
        need(len(p['values'])==17 and all(len(r)==19 for r in p['values']), '969-cell sweep')
    return {'panels':panels,'cells':969,'original_threshold':5,'extension_thresholds':(3,10),
            'biological_units':1,'scientific_qualification':False}
