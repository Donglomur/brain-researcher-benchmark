"""Paired held-mouse response endpoint; generated checks are not qualification.

This successor adds to, and does not alter, the preserved registered runtime.
Preparation is operator-only. Every public case needs a separate participant
process/view: another case's training labels can contain this case's targets.
"""
from collections import Counter

from .contracts import digest, require, unique
from .packets import _opaque, equal_arm_specs, response_prediction_packet

SCHEMA = 'neural044-response-comparison/v2'
RECIPE = {
    'scaler': 'StandardScaler fitted on training rows only (unweighted)',
    'estimator': 'Ridge', 'alpha': 1.0, 'solver': 'svd',
    'fit_intercept': True, 'ridge_sample_weight': '1 / training-mouse pair count',
    'minimum_eligible_mice': 3,
}
FEATURES = ['distance_um_div_100', 'distance_um_div_100_squared',
            'independent_baseline_dff', 'measured_movement', 'power_mw',
            'nonresponding_site', 'tuning_similarity',
            'tuning_similarity_x_nonresponding_site']
UNITS = 'dF/F (fraction), lag-width-averaged calcium-response coefficient'


def _hash(value, label):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), label)


def _vector(values, length, label):
    import math
    import numpy as np
    require(type(values) is list and len(values) == length and
            all(type(x) in (int, float) and math.isfinite(x) for x in values), label)
    return np.asarray(values, dtype=float)


def _fixed_references(public):
    """Only public training labels/features and query features enter either fit."""
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    train = np.asarray(public['training_features'], dtype=float)
    query = np.asarray(public['query_features'], dtype=float)
    y = _vector(public['training_responses'], len(train), 'finite training responses')
    require(train.shape == (len(y), len(FEATURES)) and
            query.shape == (len(public['ids']), len(FEATURES)) and
            np.isfinite(train).all() and np.isfinite(query).all(), 'finite response design')
    units = public['training_unit_ids']
    require(len(units) == len(train) and len(set(units)) >= 2, 'independent training mice')
    counts = Counter(units)
    weights = np.asarray([1.0 / counts[u] for u in units])
    result = {}
    for name, width in (('nuisance', 6), ('tuning', 8)):
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0, solver='svd'))
        model.fit(train[:, :width], y, ridge__sample_weight=weights)
        pred = model.predict(query[:, :width])
        require(np.isfinite(pred).all(), 'finite fixed-reference prediction')
        result[name] = pred.tolist()
    return result


def prepare_response_comparison(construction, population_mice, private_key, limits,
                                source_digest):
    """Prepare same-row references and a complete operator-owned mouse roster.

    population_mice must come from the complete authenticated release manifest,
    including excluded/behavior-only mice. The versioned operator supplies it.
    Response-selected sites remain outside prediction, as in the original code.
    """
    _hash(source_digest, 'source digest')
    _hash(construction['disposition_digest'], 'disposition digest')
    require(type(population_mice) is list and population_mice and
            all(type(m) is str and m for m in population_mice), 'source mouse roster')
    unique(population_mice, 'source mouse')
    require(all(r['mouse'] in population_mice for r in construction['rows']),
            'response mouse outside source roster')
    rows = [r for r in construction['rows'] if r['control'] == 'lagged']
    identity = lambda r: [r['mouse'], r['session'], r['epoch'], r['target_id'],
                          r['power'], r['condition'], r['follower_roi']]
    unique([digest(identity(r)) for r in rows], 'source response identity')
    eligible = [r for r in rows if r['classification_basis'] == 'independent_pretest']
    mice = {r['mouse'] for r in eligible}
    cases, roster = [], []
    for mouse in sorted(population_mice):
        all_count = sum(r['mouse'] == mouse for r in rows)
        count = sum(r['mouse'] == mouse for r in eligible)
        row = {'mouse': mouse, 'n_joined_lagged_pairs': all_count,
               'n_independent_pretest_pairs': count,
               'response_selected_pairs_excluded': all_count - count}
        reason = ('no fully joined lagged pairs' if not all_count else
                  'no independent pretest site classification' if not count else
                  'fewer than three mice with independent pretest site classification'
                  if len(mice) < 3 else None)
        if reason:
            roster.append({**row, 'status': 'not_estimable', 'reason': reason})
            continue
        public, private = response_prediction_packet(eligible, mouse, private_key)
        train = [r for r in eligible if r['mouse'] != mouse]
        public.update(comparison_schema=SCHEMA, feature_names=FEATURES.copy(),
                      response_units=UNITS, source_digest=source_digest,
                      disposition_digest=construction['disposition_digest'],
                      reference_recipe=dict(RECIPE),
                      training_unit_ids=[_opaque(private_key,
                          ['training_mouse', public['case_id'], r['mouse']]) for r in train])
        # Reference fitting precedes attaching private test responses to scoring.
        references = _fixed_references(public)
        _vector(private['responses'], count, 'finite private response coefficients')
        private.update(comparison_schema=SCHEMA, public_digest=digest(public),
                       references=references, reference_recipe=dict(RECIPE),
                       source_digest=source_digest,
                       disposition_digest=construction['disposition_digest'])
        cases.append({'public': public, 'private': private,
                      'arms': equal_arm_specs(public, limits)})
        roster.append({**row, 'status': 'estimable', 'case_id': public['case_id']})
    cohort = {'schema': SCHEMA, 'source_digest': source_digest,
              'disposition_digest': construction['disposition_digest'],
              'mouse_roster': roster, 'reference_recipe': dict(RECIPE)}
    return {'cases': cases, 'cohort': cohort, 'canonical_task_count': 1,
            'held_stimulation_signals_not_exposed': True}


def score_response_comparison(submissions, public_packets, private_packets, cohort):
    """Paired MSE differences, equally weighted over eligible held mice.

    Inputs are operator-owned and authenticated by the versioned operator after
    all arms commit. No scorer output is feedback for another case or arm.
    """
    import numpy as np
    from .inference import uncertainty
    require(cohort['schema'] == SCHEMA and cohort['reference_recipe'] == RECIPE,
            'fixed comparison protocol')
    for key in ('source_digest', 'disposition_digest'):
        _hash(cohort[key], key)
    roster = cohort['mouse_roster']
    require(type(roster) is list and roster, 'complete mouse roster')
    unique([r['mouse'] for r in roster], 'cohort mouse')
    require(all(r['status'] in ('estimable', 'not_estimable') for r in roster),
            'mouse disposition')
    eligible = [r for r in roster if r['status'] == 'estimable']
    require(not eligible or len(eligible) >= 3, 'fixed minimum eligible mouse count')
    case_ids = [r['case_id'] for r in eligible]
    unique(case_ids, 'cohort case')
    for table in (submissions, public_packets, private_packets):
        require(type(table) is dict and set(table) == set(case_ids), 'complete exact case set')
    values, all_ids = [], []
    for row in roster:
        if row['status'] == 'not_estimable':
            require(type(row.get('reason')) is str and row['reason'], 'missing disposition reason')
            values.append({**row, 'candidate_mse': None, 'nuisance_mse': None,
                           'tuning_mse': None, 'improvement': None})
            continue
        case_id = row['case_id']
        public, private, submission = (table[case_id]
            for table in (public_packets, private_packets, submissions))
        require(public['task'] == 'NEURAL-044' and
                public['claim'] == 'held_mouse_response_prediction', 'response task/claim')
        require(public['comparison_schema'] == private['comparison_schema'] == SCHEMA and
                public['reference_recipe'] == private['reference_recipe'] == RECIPE and
                public['feature_names'] == FEATURES and public['response_units'] == UNITS,
                'response recipe and units')
        require(public['case_id'] == private['case_id'] == submission['case_id'] == case_id,
                'response case identity')
        require(public['ids'] == private['ids'] == submission['ids'], 'response identity/order')
        ids = public['ids']
        require(type(ids) is list and ids and all(type(i) is str and i for i in ids),
                'nonempty response IDs')
        unique(ids, 'held response')
        all_ids.extend(ids)
        n = len(ids)
        require(row['n_independent_pretest_pairs'] == n and
                private['units'] == [row['mouse']] * n, 'complete single-mouse response unit')
        require(private['public_digest'] == digest(public), 'prepared public packet changed')
        for key in ('source_digest', 'disposition_digest'):
            require(public[key] == private[key] == cohort[key], 'comparison source binding')
        y = _vector(private['responses'], n, 'finite private response vector')
        candidate = _vector(submission['responses'], n, 'finite submitted response vector')
        errors = {}
        require(set(private['references']) == {'nuisance', 'tuning'}, 'both fixed references')
        for name, pred in [('candidate', candidate)] + [(name, _vector(
                private['references'][name], n, 'finite reference response vector'))
                for name in ('nuisance', 'tuning')]:
            with np.errstate(over='ignore', invalid='ignore'):
                mse = float(np.mean((pred - y) ** 2))
            require(np.isfinite(mse), 'response MSE overflow')
            errors[name + '_mse'] = mse
        values.append({**row, **errors,
                       'improvement': errors['nuisance_mse'] - errors['candidate_mse'],
                       'tuning_reference_improvement': errors['nuisance_mse'] - errors['tuning_mse']})
    unique(all_ids, 'cohort response')
    estimated = [r for r in values if r['status'] == 'estimable']
    improvements = [r['improvement'] for r in estimated]
    with np.errstate(over='ignore', invalid='ignore'):
        mean = float(np.mean(improvements)) if improvements else None
        interval = uncertainty(improvements) if len(improvements) >= 2 else None
    require(mean is None or np.isfinite(mean), 'aggregate response improvement overflow')
    if interval:
        require(np.isfinite(interval['ci95']).all(), 'mouse uncertainty overflow')
        interval['limitation'] = ('Descriptive approximate mouse t interval; shared training folds '
            'and uncertainty in model-estimated response labels are not propagated.')
    return {'task': 'NEURAL-044', 'schema': SCHEMA, 'mouse_values': values,
            'primary': {'name': 'held_mouse_nuisance_mse_minus_candidate_mse',
                        'value': mean,
                        'direction': 'higher', 'aggregation': 'equal eligible mouse weight',
                        'units': '(' + UNITS + ') squared', 'uncertainty': interval},
            'n_mice': len(estimated), 'n_source_mice': len(roster),
            'source_digest': cohort['source_digest'],
            'disposition_digest': cohort['disposition_digest'],
            'status': 'scored' if estimated else 'not_estimable',
            'scientific_qualification': False, 'provider_verified': False,
            'label_provenance': 'benchmark-estimated full-schedule lag-model coefficients'}
