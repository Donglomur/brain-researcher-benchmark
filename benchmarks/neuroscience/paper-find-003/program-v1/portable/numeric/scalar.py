"""Source-only proposal: fixed three-phase numerical agreement, no fitting or I/O.

Only grade() may call the supplied private loader, after complete public admission.
This is an analysis-artifact scorer; it does not attest candidate computation.
"""
from decimal import Decimal, localcontext
import hashlib
import json
import math

TASK = 'PAPER-FIND-003'
PHASES = ('stimulus', 'feedback', 'interval')
NAMES = ('(Intercept)', 'ACC', 'trial', 'ACC:trial')
ROLES = ('subject', 'nested_contact', 'residual')
L = ((0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (0, 1, 0, 0))
CONTRASTS = ('wrong_trial_slope', 'correct_trial_slope',
             'accuracy_by_trial_interaction', 'ACC_difference_at_trial0')
MAX_BYTES = 32768
REML_CONVENTION = 'lme4_profiled_REML_original_design_including_constants'


class AdmissionError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise AdmissionError(message)


def exact(value, keys, where):
    need(type(value) is dict and set(value) == set(keys), where + ': exact fields')


def text(value, where, nullable=False):
    if nullable and value is None:
        return
    need(type(value) is str and 0 < len(value) <= 512, where + ': bounded string')


def number(value, where):
    need(type(value) in (int, float), where + ': number, not boolean')
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise AdmissionError(where + ': finite binary64') from None
    need(math.isfinite(result), where + ': finite binary64')
    return result


def integer(value, low, high, where):
    need(type(value) is int and low <= value <= high, where + ': integer range')


def sha(value, where):
    need(type(value) is str and len(value) == 64 and
         all(c in '0123456789abcdef' for c in value), where + ': lowercase SHA256')


def decode(body):
    need(type(body) is bytes and 0 < len(body) <= MAX_BYTES, 'bounded submission bytes')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def real(token):
        value = float(token)
        need(math.isfinite(value), 'nonfinite JSON number')
        # json.loads already admitted JSON number grammar. Inspect only the
        # mantissa: Decimal(token) can itself fail on extremely large exponents.
        mantissa = token.lower().split('e', 1)[0]
        need(value != 0 or not any(c in '123456789' for c in mantissa),
             'destructive JSON underflow')
        return value
    def whole(token):
        need(len(token) <= 18, 'integer token limit')
        return int(token)
    def invalid_constant(_):
        raise AdmissionError('JSON constant forbidden')
    try:
        value = json.loads(body.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                           parse_float=real, parse_int=whole, parse_constant=invalid_constant)
    except (UnicodeError, ValueError, OverflowError, RecursionError) as error:
        raise AdmissionError('strict UTF8 JSON: ' + str(error)[:120]) from None
    def walk(x, depth=0):
        need(depth <= 12, 'bounded nesting')
        if type(x) is dict:
            need(len(x) <= 20, 'bounded object')
            for k, v in x.items():
                need(type(k) is str and len(k) <= 96, 'bounded key')
                walk(v, depth + 1)
        elif type(x) is list:
            need(len(x) <= 16, 'bounded array')
            for v in x:
                walk(v, depth + 1)
        elif type(x) is str:
            need(len(x) <= 512, 'bounded string')
    walk(value)
    return value


def validate(value, public):
    exact(value, ('schema_version', 'task_id', 'input_sha256', 'submission_status', 'models'), 'submission')
    need(type(value['schema_version']) is int and value['schema_version'] == 1, 'schema_version')
    need(value['task_id'] == TASK and public['task_id'] == TASK, 'task identity')
    sha(value['input_sha256'], 'input identity')
    need(value['input_sha256'] == public['input_sha256'], 'active input identity')
    need(value['submission_status'] in ('complete', 'partial', 'abstained'), 'submission status')
    rows = value['models']
    need(type(rows) is list and len(rows) == 3, 'three explicit phase entries')
    by_phase = {}
    for row in rows:
        exact(row, ('phase', 'status', 'reason', 'fit'), 'model')
        phase = row['phase']
        need(type(phase) is str and phase in PHASES and phase not in by_phase, 'unique phase identity')
        need(row['status'] in ('reported', 'abstained'), 'phase status')
        if row['status'] == 'abstained':
            text(row['reason'], 'abstention reason')
            need(row['fit'] is None, 'abstention has no numerical payload')
        else:
            need(row['reason'] is None, 'reported reason is null')
            f = row['fit']
            exact(f, ('coefficients', 'covariance', 'variance_components', 'support', 'method', 'reml_diagnostic'), 'fit')
            exact(f['coefficients'], NAMES, 'four named coefficients')
            for name in NAMES:
                number(f['coefficients'][name], 'coefficient')
            c = f['covariance']
            exact(c, ('axes', 'values'), 'full covariance')
            need(type(c['axes']) is list and len(c['axes']) == 4 and
                 all(type(k) is str for k in c['axes']) and set(c['axes']) == set(NAMES), 'covariance axes')
            need(type(c['values']) is list and len(c['values']) == 4, 'covariance rows')
            for matrix_row in c['values']:
                need(type(matrix_row) is list and len(matrix_row) == 4, 'covariance columns')
                for v in matrix_row:
                    number(v, 'covariance entry')
            exact(f['variance_components'], ROLES, 'absolute variance components')
            for role in ROLES:
                number(f['variance_components'][role], 'variance component')
            support = f['support']
            exact(support, ('n_obs', 'n_subjects', 'n_nested_contacts', 'row_ids_sha256'), 'support')
            for key in ('n_obs', 'n_subjects', 'n_nested_contacts'):
                integer(support[key], 0, public['wide_rows'], key)
            sha(support['row_ids_sha256'], 'row membership claim')
            m = f['method']
            exact(m, ('estimator', 'random_effects', 'weights', 'offset'), 'method claim')
            for key, allowed in {
                'estimator': ('REML', 'ML', 'other'),
                'random_effects': ('subject_plus_nested_contact', 'subject_only', 'contact_only', 'pooled_contact', 'other'),
                'weights': ('unit', 'other'), 'offset': ('zero', 'other')}.items():
                need(m[key] in allowed, 'declared method value')
            d = f['reml_diagnostic']
            if d is not None:
                exact(d, ('criterion', 'convention'), 'optional objective')
                number(d['criterion'], 'objective')
                need(d['convention'] in (REML_CONVENTION, 'other'), 'objective convention')
        by_phase[phase] = row
    n = sum(row['status'] == 'reported' for row in rows)
    expected = 'abstained' if n == 0 else 'complete' if n == 3 else 'partial'
    need(value['submission_status'] == expected, 'status agrees with explicit phase coverage')
    return {**value, 'models': [by_phase[p] for p in PHASES]}


def row_digest(ids):
    """Only operator reference projection uses saved IDs; no CSV/fit operations."""
    need(type(ids) is list and ids and all(type(x) is int for x in ids), 'reference row IDs')
    need(ids == sorted(set(ids)) and ids[0] >= 1 and ids[-1] <= 8082, 'reference row roster')
    return hashlib.sha256((''.join(str(x) + '\n' for x in ids)).encode('ascii')).hexdigest()


def project_reference(saved, public):
    need(saved.get('candidate_id') == TASK and set(saved.get('phases', {})) == set(PHASES), 'private model identity')
    rows = []
    for phase in PHASES:
        r = saved['phases'][phase]
        need(r['status'] == 'completed' and r['convergence_ok'] is True and
             r['conditional_audit_status'] == 'conditional_REML_algebra_passed' and
             r['REML'] is True and r['weights'] == 'unit' and r['offset'] == 'zero' and
             not r['col_dropped'] and r['fixed_names'] == list(NAMES), 'qualified private phase')
        f = {'coefficients': dict(zip(NAMES, r['beta'])),
             'covariance': {'axes': list(NAMES), 'values': r['vcov']},
             'variance_components': {k: r['variance_by_role'][k] for k in ROLES},
             'support': {'n_obs': r['n'], 'n_subjects': len(r['subject_levels']),
                         'n_nested_contacts': len(r['nested_contact_levels']), 'row_ids_sha256': row_digest(r['row_ids'])},
             'method': {'estimator': 'REML', 'random_effects': 'subject_plus_nested_contact', 'weights': 'unit', 'offset': 'zero'},
             'reml_diagnostic': {'criterion': r['reml_criterion'], 'convention': REML_CONVENTION}}
        rows.append({'phase': phase, 'status': 'reported', 'reason': None, 'fit': f})
    return validate({'schema_version': 1, 'task_id': TASK, 'input_sha256': public['input_sha256'],
                     'submission_status': 'complete', 'models': rows}, public)


def dec(x):
    return Decimal.from_float(float(x))


def finite_decimal(x):
    """Never convert an overflow or nonzero underflow into a false finite error."""
    try:
        value = float(x)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) and (value != 0 or x == 0) else None


def scalar_error(a, b):
    with localcontext() as ctx:
        ctx.prec = 2500
        da, db = dec(a), dec(b)
        delta = da - db
        absolute = abs(delta)
        denominator = abs(da) + abs(db)
        symmetric = Decimal(0) if denominator == 0 else 2 * absolute / denominator
        signed, error, normalized = map(finite_decimal, (delta, absolute, symmetric))
        return {'status': 'compared' if signed is not None and error is not None and normalized is not None else 'unsupported_binary64_error',
                'signed_candidate_minus_reference': signed, 'absolute_error': error,
                'symmetric_relative_error': normalized, 'symmetric_scale': '(|candidate|+|reference|)/2; both zero gives zero'}


def family(actual, expected, names, unit):
    mixed_units = type(unit) is dict
    errors = {name: {'unit': unit[name] if mixed_units else unit, **scalar_error(a, b)}
              for name, a, b in zip(names, actual, expected)}
    mae = rmse = None
    if not mixed_units:
        with localcontext() as ctx:
            ctx.prec = 2500
            ds = [abs(dec(a) - dec(b)) for a, b in zip(actual, expected)]
            mean = sum(ds, Decimal(0)) / len(ds)
            rms = (sum((x*x for x in ds), Decimal(0)) / len(ds)).sqrt()
            mae, rmse = finite_decimal(mean), finite_decimal(rms)
    unsupported = any(e['status'] != 'compared' for e in errors.values()) or (not mixed_units and (mae is None or rmse is None))
    return {'unit': unit, 'expected_scalars': len(names), 'reported_scalars': len(names),
            'status': 'unsupported_binary64_error' if unsupported else 'compared',
            'MAE': None if mixed_units else mae, 'RMSE': None if mixed_units else rmse,
            'aggregate_omitted_for_mixed_units': mixed_units, 'entries': errors}


def canonical(f):
    index = [f['covariance']['axes'].index(k) for k in NAMES]
    return ([f['coefficients'][k] for k in NAMES],
            [[f['covariance']['values'][i][j] for j in index] for i in index])


def derived(beta, covariance):
    # Decimal avoids intermediate binary64 overflow; no model fitting/algebra solve.
    with localcontext() as ctx:
        ctx.prec = 2500
        b = [dec(x) for x in beta]
        v = [[dec(x) for x in row] for row in covariance]
        contrasts = [sum((Decimal(z)*x for z, x in zip(row, b)), Decimal(0)) for row in L]
        cv = [[sum((Decimal(L[i][k])*v[k][l]*Decimal(L[j][l]) for k in range(4) for l in range(4)), Decimal(0))
               for j in range(4)] for i in range(4)]
        flat = [finite_decimal(x) for x in contrasts] + [finite_decimal(x) for row in cv for x in row]
        if any(x is None for x in flat):
            return None
        return flat[:4], [flat[4+i*4:8+i*4] for i in range(4)]


def compare(candidate, reference):
    output = []
    for row, truth in zip(candidate['models'], reference['models']):
        phase = row['phase']
        if row['status'] == 'abstained':
            output.append({'phase': phase, 'status': 'abstained', 'reason': row['reason'],
                           'expected': {'coefficients': 4, 'covariance_entries': 16, 'variance_components': 3},
                           'numerical_errors': None, 'support_agreement': None})
            continue
        a, b = row['fit'], truth['fit']
        ab, av = canonical(a); bb, bv = canonical(b)
        numerical = {
            'coefficients': family(ab, bb, NAMES, {k: 'source ripple-rate' if i < 2 else 'source ripple-rate/trial' for i, k in enumerate(NAMES)}),
            'covariance': family([x for r in av for x in r], [x for r in bv for x in r],
                                 [f'{i}|{j}' for i in NAMES for j in NAMES],
                                 {f'{i}|{j}': 'rate^2/trial^' + str((u >= 2) + (v >= 2)) for u, i in enumerate(NAMES) for v, j in enumerate(NAMES)}),
            'variance_components': family([a['variance_components'][k] for k in ROLES],
                                          [b['variance_components'][k] for k in ROLES], ROLES, 'source ripple-rate squared')}
        ac, bc = derived(ab, av), derived(bb, bv)
        if ac is None or bc is None:
            numerical['derived_contrasts'] = {'status': 'unsupported_binary64_derivation'}
        else:
            numerical['derived_contrasts'] = {
                'values': family(ac[0], bc[0], CONTRASTS, {k: 'source ripple-rate/trial' if i < 3 else 'source ripple-rate' for i, k in enumerate(CONTRASTS)}),
                'covariance': family([x for r in ac[1] for x in r], [x for r in bc[1] for x in r],
                                     [f'{i}|{j}' for i in CONTRASTS for j in CONTRASTS],
                                     {f'{i}|{j}': 'rate^2/trial^' + str((u < 3) + (v < 3)) for u, i in enumerate(CONTRASTS) for v, j in enumerate(CONTRASTS)})}
        objective = a['reml_diagnostic']
        numerical['optional_reml_criterion'] = ({'status': 'not_reported'} if objective is None else
            {'status': 'incomparable_convention_or_estimator'} if objective['convention'] != REML_CONVENTION or a['method']['estimator'] != 'REML' else
            scalar_error(objective['criterion'], b['reml_diagnostic']['criterion']))
        symmetry = [scalar_error(av[i][j], av[j][i]) for i in range(4) for j in range(i+1,4)]
        output.append({'phase': phase, 'status': 'scored', 'numerical_errors': numerical,
                       'support_agreement': {k: a['support'][k] == b['support'][k] for k in b['support']},
                       'method_claim_agreement': {k: a['method'][k] == b['method'][k] for k in b['method']},
                       'candidate_consistency': {'covariance_diagonal_nonnegative': all(av[i][i] >= 0 for i in range(4)),
                                                'variance_components_nonnegative': all(x >= 0 for x in a['variance_components'].values()),
                                                'covariance_symmetry_errors': symmetry,
                                                'positive_semidefinite_covariance_not_independently_certified': True}})
    reported = sum(x['status'] == 'scored' for x in output)
    interval = next(x for x in output if x['phase'] == 'interval')
    primary = None
    if interval['status'] == 'scored':
        d = interval['numerical_errors']['derived_contrasts']
        if 'values' in d:
            primary = d['values']['entries']['correct_trial_slope']
    return {'task_id': TASK, 'status': 'scored', 'reported_phases': reported, 'expected_phases': 3,
            'complete_numerical_coverage': reported == 3,
            'complete_support_claim_agreement': reported == 3 and all(all(x['support_agreement'].values()) for x in output),
            'expected_scalar_denominators': {'coefficients': 12, 'covariance_entries': 48, 'variance_components': 9},
            'primary_interval_correct_trial_slope_error': primary, 'phases': output,
            'optional_reml_criterion_reported_phases': sum(r['status'] == 'reported' and r['fit']['reml_diagnostic'] is not None for r in candidate['models']),
            'blended_reward': None, 'sign_success_threshold': None, 'scientific_success': None,
            'input_dependence_or_actual_fitting_verified': False, 'historical_inference_parity_claimed': False}


def grade(body, public, load_reference):
    try:
        candidate = validate(decode(body), public)
    except (AdmissionError, KeyError, TypeError) as error:
        return {'task_id': TASK, 'status': 'invalid_submission', 'reason': str(error)[:200], 'private_loads': 0}
    if candidate['submission_status'] == 'abstained':
        return {'task_id': TASK, 'status': 'abstained', 'reported_phases': 0, 'expected_phases': 3,
                'complete_numerical_coverage': False, 'numerical_errors': None, 'private_loads': 0}
    try:
        reference = project_reference(load_reference(), public)
    except Exception:
        return {'task_id': TASK, 'status': 'operator_reference_error', 'private_loads': 1}
    result = compare(candidate, reference)
    result['private_loads'] = 1
    return result
