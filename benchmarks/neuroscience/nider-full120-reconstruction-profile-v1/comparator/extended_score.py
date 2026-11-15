"""Additive full-result comparison interface; no estimator and no file loading.

Use the existing pinned reporting_core definition for strict JSON/decimal
handling. The owner authenticates the reference and policy, never the candidate.
All real-valued fields remain HELD in the supplied policy until a separately
reviewed criterion exists. This implemented absolute-bound route is optional;
a reporting-resolution or scientific-accuracy policy needs its own source review.
Native reference collection does not require formal floating-point certification. Matching undefined values is not a pass.
"""
from fractions import Fraction
import re
import reporting_core as reporting

TASK = 'PAPER-EXP-20261113-003'
SCHEMA = 'nider_extended_reproduction_submission_v1'
IDS = ('quest_self', 'amy_quest', 'amy_self')
N_COLUMNS = {'quest_self': 'sample size quest', 'amy_quest': 'sample size quest',
             'amy_self': 'sample size rating'}
POOLED = ('estimate', 'se', 'statistic', 'p', 'lower', 'upper')
FIELDS = tuple(f'{model}_z_{field}' for model in ('common', 'random') for field in POOLED) + tuple(
    f'{model}_r_{field}' for model in ('common', 'random') for field in ('estimate', 'lower', 'upper')) + (
    'Q', 'df_Q', 'p_Q', 'tau', 'tau2', 'se_tau2', 'lower_tau', 'upper_tau',
    'lower_tau2', 'upper_tau2', 'H', 'lower_H', 'upper_H', 'I2', 'lower_I2', 'upper_I2',
    'k', 'k_all', 'k_TE', 'k_study', 'N_author_sum', 'submitted_rows')
COUNTS = frozenset(('df_Q', 'k', 'k_all', 'k_TE', 'k_study', 'N_author_sum', 'submitted_rows'))
SETTINGS = {'sm': 'ZCOR', 'method_tau': 'DL', 'method_random_ci': 'classic',
            'level': '0.95', 'level_ma': '0.95', 'common': True, 'random': True,
            'three_level': False, 'cluster_supplied': False}
SHA = re.compile(r'[0-9a-f]{64}\Z')
STATES = ('finite', 'NA', 'NaN', '+Inf', '-Inf')
PASS = frozenset(('EXACT_COUNT_AGREEMENT', 'QUALIFIED_BOUND_AGREEMENT'))


def need(ok, code):
    reporting.require(ok, code)


def cell(value):
    need(type(value) is dict and set(value) in ({'state'}, {'state', 'value'}), 'cell_keys')
    need(value['state'] in STATES, 'cell_state')
    if value['state'] == 'finite':
        need(set(value) == {'state', 'value'}, 'finite_value_required')
        return reporting.exact_number(value['value'])
    need(set(value) == {'state'}, 'nonfinite_payload_forbidden')
    return None


def integer(value):
    number = reporting.exact_number(value)
    need(number.denominator == 1 and number > 0, 'positive_integer')
    return int(number)


def membership(units, contrast):
    need(type(units) is list and 1 <= len(units) <= 39, 'membership_extent')
    source_seen, rows_seen, labels = set(), set(), set()
    for unit in units:
        need(type(unit) is dict and set(unit) == {'source_id', 'source_rows', 'retained_row',
             'author_label', 'n_column', 'contributes_to_k'}, 'membership_keys')
        for name in ('source_id', 'author_label'):
            need(type(unit[name]) is str and 0 < len(unit[name]) <= 256 and
                 not any(ord(c) < 32 for c in unit[name]), 'membership_string')
        need(unit['source_id'] not in source_seen and unit['author_label'] not in labels,
             'duplicate_source_unit')
        source_seen.add(unit['source_id']); labels.add(unit['author_label'])
        need(type(unit['source_rows']) is list and len(unit['source_rows']) in (1, 2), 'source_rows')
        rows = [integer(x) for x in unit['source_rows']]
        retained = integer(unit['retained_row'])
        need(rows == sorted(set(rows)) and all(x <= 40 for x in rows) and
             retained == rows[0] and not rows_seen.intersection(rows), 'row_lineage')
        rows_seen.update(rows)
        need((len(rows) == 2) == (unit['source_id'] == 'Morawetz2016b'), 'duplicate_convention')
        need(unit['n_column'] == N_COLUMNS[contrast] and type(unit['contributes_to_k']) is bool,
             'membership_sample_size_or_fit_flag')
    return units


def validate(document, arm, workbook_sha):
    need(type(document) is dict and set(document) == {'schema', 'task', 'arm', 'workbook_sha256',
         'contrasts'}, 'document_keys')
    need(document['schema'] == SCHEMA and document['task'] == TASK and document['arm'] == arm and
         arm in ('A', 'B') and type(workbook_sha) is str and SHA.fullmatch(workbook_sha) and
         document['workbook_sha256'] == workbook_sha, 'document_identity')
    need(type(document['contrasts']) is list and len(document['contrasts']) == 3, 'three_contrasts')
    rows = {}
    for row in document['contrasts']:
        need(type(row) is dict and set(row) == {'contrast', 'settings', 'tau_interval', 'membership', 'fields'},
             'contrast_keys')
        key = row['contrast']
        need(type(key) is str and key in IDS and key not in rows, 'contrast_identity')
        need(type(row['settings']) is dict and row['settings'] == SETTINGS and
             all(type(row['settings'][k]) is type(v) for k, v in SETTINGS.items()), 'exact_native_settings')
        tau = row['tau_interval']
        need(type(tau) is dict and set(tau) == {'method', 'lower_sign', 'upper_sign'}, 'tau_interval_keys')
        need(tau['method'] in ('J', '') and all(type(tau[k]) is str and tau[k] in ('', '<', '>')
             for k in ('lower_sign', 'upper_sign')), 'tau_interval_method_sign')
        units = membership(row['membership'], key)
        need(type(row['fields']) is dict and set(row['fields']) == set(FIELDS), 'complete_numeric_fields')
        values = {name: cell(value) for name, value in row['fields'].items()}
        for name, value in values.items():
            if value is None:
                continue
            if name in COUNTS:
                need(value.denominator == 1 and value >= 0, 'count_domain')
            if name.endswith('_p') or name == 'p_Q' or name in ('I2', 'lower_I2', 'upper_I2'):
                need(0 <= value <= 1, 'probability_or_fraction_domain')
            if '_r_' in name:
                need(-1 <= value <= 1, 'correlation_scale_domain')
            if name in ('Q', 'tau', 'tau2', 'se_tau2', 'lower_tau', 'upper_tau', 'lower_tau2',
                        'upper_tau2', 'H', 'lower_H', 'upper_H') or name.endswith('_se'):
                need(value >= 0, 'nonnegative_domain')
        for prefix in ('common_z', 'random_z', 'common_r', 'random_r'):
            low, high = values[prefix + '_lower'], values[prefix + '_upper']
            need(low is None or high is None or low <= high, 'pooled_interval_order')
        for low, high in (('lower_tau', 'upper_tau'), ('lower_tau2', 'upper_tau2'),
                          ('lower_H', 'upper_H'), ('lower_I2', 'upper_I2')):
            need(values[low] is None or values[high] is None or values[low] <= values[high],
                 'heterogeneity_interval_order')
        need(values['submitted_rows'] == len(units), 'submitted_membership_count')
        need(values['k'] == sum(u['contributes_to_k'] for u in units), 'fitted_membership_count')
        # These are package/source counts, never a claim of participant independence.
        need(values['k_study'] == values['k'], 'unclustered_native_k_study')
        rows[key] = (row, values)
    need(set(rows) == set(IDS), 'complete_contrast_universe')
    return rows


def validate_policy(policy):
    need(type(policy) is dict and set(policy) == {'schema', 'task', 'fields'} and
         policy['schema'] == 'nider_extended_numeric_policy_v1' and policy['task'] == TASK,
         'owner_policy_schema')
    need(type(policy['fields']) is dict and set(policy['fields']) == set(FIELDS), 'owner_policy_support')
    for name, rule in policy['fields'].items():
        need(type(rule) is dict and type(rule.get('kind')) is str, 'owner_policy_rule')
        if name in COUNTS:
            need(rule == {'kind': 'exact_count'}, 'exact_count_policy_required')
        elif rule['kind'] == 'held':
            need(set(rule) == {'kind', 'reason'} and rule['reason'] == 'UNQUALIFIED_NUMERIC_ERROR_BOUND',
                 'held_policy_reason')
        else:
            need(set(rule) == {'kind', 'absolute_bound', 'qualification_sha256', 'scope'} and
                 rule['kind'] == 'qualified_absolute_bound' and
                 type(rule['qualification_sha256']) is str and SHA.fullmatch(rule['qualification_sha256']) and
                 rule['scope'] == 'owner_independent_numeric_error_analysis', 'qualified_policy_evidence')
            need(reporting.exact_number(rule['absolute_bound']) >= 0, 'nonnegative_error_bound')
    return policy['fields']


def score(candidate_raw, reference_raw, policy_raw, *, arm, workbook_sha256):
    """Owner-only entry; reference/policy bytes are never accepted from a candidate.

    It is the calling existing protected owner that authenticates these operands
    and isolates the scorer. This function does not infer trusted provenance from
    a JSON flag, load a path, or create a new submission gateway.
    """
    candidate = validate(reporting.decode_numeric_json(candidate_raw), arm, workbook_sha256)
    reference = validate(reporting.decode_numeric_json(reference_raw), arm, workbook_sha256)
    rules = validate_policy(reporting.decode_numeric_json(policy_raw))
    results, exact_records = [], []
    for key in IDS:
        c, cv = candidate[key]; r, rv = reference[key]
        for name in ('membership', 'settings', 'tau_interval'):
            exact_records.append({'contrast': key, 'component': name,
                                  'status': 'EXACT_AGREEMENT' if c[name] == r[name] else 'EXACT_DISAGREEMENT'})
        for name in FIELDS:
            rule, x, y = rules[name], cv[name], rv[name]
            if r['fields'][name]['state'] != 'finite':
                status = 'REFERENCE_UNAVAILABLE' if c['fields'][name] == r['fields'][name] else 'MISSINGNESS_DISAGREEMENT'
            elif x is None:
                status = 'MISSINGNESS_DISAGREEMENT'
            elif rule['kind'] == 'exact_count':
                status = 'EXACT_COUNT_AGREEMENT' if x == y else 'EXACT_COUNT_DISAGREEMENT'
            elif rule['kind'] == 'held':
                status = 'HELD_NUMERIC_ERROR_BOUND'
            else:
                bound = reporting.exact_number(rule['absolute_bound'])
                status = 'QUALIFIED_BOUND_AGREEMENT' if abs(x - y) <= bound else 'QUALIFIED_BOUND_DISAGREEMENT'
            results.append({'contrast': key, 'field': name, 'status': status})
    return {'schema': 'nider_extended_numeric_score_v1', 'task': TASK, 'arm': arm,
            'numeric_field_count': len(results), 'structural_checks': exact_records, 'fields': results,
            'implemented_components_agree': all(x['status'] in PASS for x in results) and
                all(x['status'] == 'EXACT_AGREEMENT' for x in exact_records),
            'registered_full_reproduction_qualified': False,
            'unresolved_registered_components': ['participant_cohort_join',
                'correlation_leave_one_study_rule_and_reference', 'full_published_claim_comparison'],
            'R_print_strings_scored': 0, 'new_benchmarks': 0}
