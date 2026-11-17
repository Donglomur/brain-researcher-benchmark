"""Independent full-person likelihood comparison; future operator use only."""
import math
from core import HMM, need, validate_runs
from likelihood import validate_hmm, hmm_loglikelihood, static_loglikelihood


def held(candidate, fixed_reference, static_reference, query_rows, branch, fold):
    """All models are admitted before query observations are evaluated.

    The caller binds independently produced reference parameters and the query
    pool through external trusted pins. A submitted baseline is never accepted.
    """
    d, k, _ = HMM[branch]
    validate_hmm(candidate, d, k)
    validate_hmm(fixed_reference, d, k)
    validate_hmm({'means': [static_reference['mean']],
                  'covariances': [static_reference['covariance']],
                  'transition': [[1.]], 'initial': [1.]}, d, 1)
    validate_runs(query_rows, branch, fold, 'query')
    rows = []
    for r in query_rows:
        x = r['observations']
        scores = {
            'candidate': hmm_loglikelihood(x, candidate, d, k),
            'reference_hmm': hmm_loglikelihood(x, fixed_reference, d, k),
            'reference_static': static_loglikelihood(x, static_reference['mean'], static_reference['covariance'])}
        need(len({v['samples'] for v in scores.values()}) == 1, 'Identical full represented query support')
        rows.append({'person': r['person'], 'run': r['run'], 'scores': scores})
    people = {}
    for person in sorted({r['person'] for r in rows}):
        rr = [r for r in rows if r['person'] == person]
        n = sum(r['scores']['candidate']['samples'] for r in rr)
        values = {name: math.fsum(r['scores'][name]['log_likelihood'] for r in rr)/n
                  for name in ('candidate', 'reference_hmm', 'reference_static')}
        need(all(math.isfinite(v) for v in values.values()), 'Representable complete person likelihood')
        people[person] = {'samples': n, **values,
                          'candidate_minus_hmm': values['candidate']-values['reference_hmm'],
                          'candidate_minus_static': values['candidate']-values['reference_static']}
    metrics = ('candidate', 'reference_hmm', 'reference_static', 'candidate_minus_hmm', 'candidate_minus_static')
    means = {key: math.fsum(v[key]/len(people) for v in people.values()) for key in metrics}
    need(all(math.isfinite(v) for v in means.values()), 'Representable equal-person means')
    return {'branch': branch, 'fold': fold, 'people': people, 'runs': rows,
            'equal_person': means, 'units': 'nats per represented observation',
            'representation_spaces_pooled': False, 'scientific_success_threshold': None}


def aggregate_folds(reports, branch):
    need(len(reports) == 5 and {r['fold'] for r in reports} == set(range(5))
         and all(r['branch'] == branch for r in reports), 'All five original folds')
    from core import people as original_people
    joined = {}
    for r in reports:
        need(not set(joined).intersection(r['people']), 'Each original person appears once')
        joined.update(r['people'])
    need(set(joined) == set(original_people(branch)), 'Complete original biological denominator')
    metrics = ('candidate', 'reference_hmm', 'reference_static', 'candidate_minus_hmm', 'candidate_minus_static')
    means = {key: math.fsum(p[key]/len(joined) for p in joined.values()) for key in metrics}
    return {'branch': branch, 'people': joined, 'equal_person': means,
            'no_equal_fold_shortcut': True, 'pooled_with_other_branches': False}
