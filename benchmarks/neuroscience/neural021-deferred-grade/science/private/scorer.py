"""Continuous condition-specific trajectory R². Import public interface explicitly."""
import hashlib
import math


def score(submission_bytes, cases_bytes, load_private_targets, interface):
    """Private callback is invoked only after complete public validation succeeds.

    callback returns {schema, cases_sha256, query_ids, velocity_m_s}; every query
    and all 30 bins must be present. A caller owns filesystem isolation.
    """
    cases = interface.strict_json(cases_bytes)
    digest = hashlib.sha256(cases_bytes).hexdigest()
    queries = interface.validate_queries(cases)
    ordered = interface.validate_submission(interface.strict_json(submission_bytes), cases, digest)
    gold = load_private_targets()
    ids = [x['trial_id'] for x in queries]
    if (not isinstance(gold, dict) or set(gold) != {'schema','cases_sha256','query_ids','velocity_m_s'} or
            gold['schema'] != 'neural021_private_targets_v1' or gold['cases_sha256'] != digest or
            gold['query_ids'] != ids):
        raise ValueError('private target/public roster binding mismatch')
    target = gold['velocity_m_s']
    if not isinstance(target, list) or len(target) != len(ids):
        raise ValueError('private complete trajectory shape')
    for trial in target:
        if not isinstance(trial, list) or len(trial) != 30:
            raise ValueError('private time dimension')
        for pair in trial:
            if (not isinstance(pair, list) or len(pair) != 2 or
                    any(type(x) not in (int,float) or abs(x)>1e6 or not math.isfinite(x) for x in pair)):
                raise ValueError('private finite two-axis target')
    reports = {}
    for condition in ('active', 'passive'):
        indices = [i for i, q in enumerate(queries) if q['condition'] == condition]
        n = len(indices) * 30
        mu = [math.fsum(target[i][t][a] for i in indices for t in range(30))/n for a in range(2)]
        sse = [math.fsum((ordered[i][t][a]-target[i][t][a])**2
                        for i in indices for t in range(30)) for a in range(2)]
        sst = [math.fsum((target[i][t][a]-mu[a])**2
                        for i in indices for t in range(30)) for a in range(2)]
        den = math.fsum(sst)
        r2 = None if den == 0 else 1-math.fsum(sse)/den
        status = 'undefined_constant_target' if den == 0 else 'defined'
        if r2 is not None and not math.isfinite(r2):
            r2, status = None, 'undefined_numeric_range'
        axis_r2 = [None if sst[a] == 0 else 1-sse[a]/sst[a] for a in range(2)]
        axis_r2 = [v if v is None or math.isfinite(v) else None for v in axis_r2]
        reports[condition] = dict(trials=len(indices), trajectory_rows=n,
            r2_variance_weighted=r2, r2_status=status,
            axis_r2=axis_r2,
            squared_euclidean_loss_m2_s2=math.fsum(sse)/n)
    values = [reports[c]['r2_variance_weighted'] for c in ('active','passive')]
    return dict(schema='neural021_condition_scores_v1', task_id='NEURAL-021',
        conditions=reports, mean_condition_r2=None if None in values else math.fsum(values)/2,
        aggregation='equal condition; equal trial and time within condition',
        inferential_unit='one session; whole trials, not independent time bins',
        binary_success_threshold=None)
