"""Numeric-only paper reporting and separate hypothetical procedure screen.

Targets are owner operands. This module never accepts target paths, case support
or a scoring policy from a candidate. No model, estimator or subprocess runs.
"""
from decimal import Decimal
from fractions import Fraction
import hashlib
import json

import reporting_core as reporting
from custody import Invalid, need

TASK = 'PAPER-EXP-20261113-003'
POLICY = 'nider-paper-reporting-and-coarse-procedure-v1'
IDS = reporting.IDS
METRICS = reporting.METRICS
NATIVE_FIELDS = {'TE_random', 'lower_random', 'upper_random', 'pval_random', 'k',
                 'N', 'tau', 'lower_tau', 'upper_tau', 'Q', 'df_Q', 'pval_Q'}
PASS = {'REPORTING_AGREEMENT', 'EXACT_COUNT_AGREEMENT'}


def unique_reporting_bin(low, high, quantum):
    """Return a rational bin center only if the entire enclosure is interior.

    The half-open floor operation only proposes a center. The subsequent strict
    test rejects both exact ties and crossing enclosures; it never breaks a tie.
    """
    need(isinstance(low, Fraction) and isinstance(high, Fraction) and low <= high,
         'target_interval')
    midpoint = (low + high) / 2
    index = (midpoint / quantum + Fraction(1, 2)).numerator // (midpoint / quantum + Fraction(1, 2)).denominator
    center = index * quantum
    if center - quantum / 2 < low <= high < center + quantum / 2:
        return center
    return None


def original_target(raw):
    target = reporting.decode_numeric_json(raw)
    values = reporting.validate_target(target)
    return {'schema': 'nider_owner_published_targets_v1', 'fields': values,
            'origin': 'authenticated_Nature_Figure1_caption'}


def procedure_target(raw):
    """Project frozen native outputs; do not read or score R print strings.

    A derivative has no published result. Its target schema and provenance are
    deliberately distinct from the original caption target. The same reporting
    resolution is a predeclared coarse computation screen, not an error bound.
    """
    data = reporting.decode_numeric_json(raw)
    need(type(data) is dict and set(data) == {'schema', 'rows'} and
         data['schema'] == 'nider-reproduction-values-v1', 'native_schema')
    need(type(data['rows']) is list and len(data['rows']) == 3, 'native_support')
    found = {}
    for row in data['rows']:
        need(type(row) is dict and set(row) == {'contrast', 'fields', 'formatted_table'}, 'native_row')
        key = row['contrast']
        need(type(key) is str and key in IDS and key not in found, 'native_contrast')
        need(type(row['fields']) is dict and set(row['fields']) == NATIVE_FIELDS, 'native_fields')
        # Only the four selected scientific operands are interpreted. Remaining
        # native values and archived strings are authenticated by the file pin.
        f = {name: reporting.exact_number(row['fields'][name])
             for name in ('TE_random', 'pval_random', 'k', 'N')}
        need(0 <= f['pval_random'] <= 1, 'native_p_domain')
        need(f['N'] >= f['k'] >= 1 and all(f[x].denominator == 1 for x in ('k', 'N')), 'native_counts')
        low, high = reporting.tanh_rational_bounds(f['TE_random'])
        q_r, q_p = Fraction(1, 100), Fraction(1, 1000)
        r = unique_reporting_bin(low, high, q_r)
        p = unique_reporting_bin(f['pval_random'], f['pval_random'], q_p)
        found[key] = {'pearson_r': (r, q_r), 'p_two_sided': (p, q_p),
                      'k': (f['k'], Fraction(1)), 'N': (f['N'], Fraction(1))}
    need(set(found) == set(IDS), 'native_complete_contrasts')
    return {'schema': 'nider_owner_hypothetical_coarse_targets_v1', 'fields': found,
            'origin': 'fixed_hypothetical_input_native_author_reference',
            'indeterminate_fields': sum(center is None for row in found.values() for center, _ in row.values())}


def candidate_rows(rows):
    return reporting.validate_rows({'schema': 'nider_published_numeric_submission_v1', 'rows': rows})


def compare_rows(rows, target):
    actual = candidate_rows(rows)
    records = []
    for contrast in IDS:
        for metric in METRICS:
            center, quantum = target['fields'][contrast][metric]
            value = actual[contrast][metric]
            if center is None:
                status = 'INDETERMINATE_REFERENCE_REPORTING_BOUNDARY'
            elif metric in ('k', 'N'):
                status = 'EXACT_COUNT_AGREEMENT' if value == center else 'EXACT_COUNT_DISAGREEMENT'
            else:
                status = reporting.classify_interval(value, value, center, quantum)
            records.append({'contrast': contrast, 'metric': metric, 'status': status})
    return {'complete_agreement': all(x['status'] in PASS for x in records),
            'evaluated_fields': 12, 'fields': records}


def score_submission(raw, owner_cases, arm):
    """owner_cases comes only from authenticated owner admission, never JSON.

    No partial-support credit. One original case plus exactly three derivative
    cases are mandatory. A valid JSON submission cannot override their universe.
    """
    need(arm in ('A', 'B'), 'owner_arm')
    need(len(owner_cases) == 4 and sum(x['kind'] == 'original' for x in owner_cases) == 1 and
         sum(x['kind'] == 'procedure' for x in owner_cases) == 3, 'owner_case_universe')
    expected = {x['case_id']: x for x in owner_cases}
    need(len(expected) == 4, 'owner_case_unique')
    document = reporting.decode_numeric_json(raw)
    need(type(document) is dict and set(document) == {'schema', 'task', 'policy', 'arm', 'cases'}, 'submission_keys')
    need(document['schema'] == 'nider_scientific_submission_v1' and document['task'] == TASK and
         document['policy'] == POLICY and document['arm'] == arm, 'submission_identity')
    need(type(document['cases']) is list and len(document['cases']) == 4, 'complete_four_case_support')
    found = {}
    for item in document['cases']:
        need(type(item) is dict and set(item) == {'case_id', 'workbook_sha256', 'rows'}, 'case_response_keys')
        key = item['case_id']
        need(type(key) is str and key in expected and key not in found, 'unknown_or_duplicate_case')
        need(item['workbook_sha256'] == expected[key]['workbook']['sha256'], 'response_input_identity')
        found[key] = item
    need(set(found) == set(expected), 'complete_case_universe')
    records = []
    for case in owner_cases:
        result = compare_rows(found[case['case_id']]['rows'], case['target'])
        records.append({'case_id': case['case_id'], 'role': case['kind'], **result})
    original = next(x for x in records if x['role'] == 'original')
    procedures = [x for x in records if x['role'] == 'procedure']
    return {'schema': 'nider_scientific_reporting_score_v1', 'policy': POLICY, 'arm': arm,
            'submission_sha256': hashlib.sha256(raw).hexdigest(), 'original_published_quantities': 12,
            'original_reporting_agreement': original['complete_agreement'],
            'hypothetical_control_cases': 3, 'coarse_procedure_agreement': all(x['complete_agreement'] for x in procedures),
            'complete_original_and_procedure_agreement': all(x['complete_agreement'] for x in records),
            'per_case': records, 'R_print_strings_scored': 0, 'engineering_numeric_fields_scored': 0,
            'remaining_native_numeric_fields_qualified': False,
            'estimator_accuracy_or_portability_established': False,
            'scientifically_qualified_benchmark': False, 'new_empirical_benchmarks': 0}


def normalize_case_response(raw, case):
    """Strict stdout-only response for one fresh process, owner binds identity."""
    item = reporting.decode_numeric_json(raw)
    need(type(item) is dict and set(item) == {'schema', 'case_id', 'workbook_sha256', 'rows'}, 'one_case_schema')
    need(item['schema'] == 'nider_scientific_case_response_v1' and
         item['case_id'] == case['case_id'] and item['workbook_sha256'] == case['workbook']['sha256'], 'one_case_identity')
    candidate_rows(item['rows'])
    return {k: item[k] for k in ('case_id', 'workbook_sha256', 'rows')}


def json_numbers(value):
    """Losslessly re-encode validated Decimal JSON values; no float conversion."""
    if isinstance(value, Decimal):
        reporting.exact_number(value)
        return str(value)
    if type(value) is str:
        return json.dumps(value)
    if type(value) is list:
        return '[' + ','.join(json_numbers(x) for x in value) + ']'
    if type(value) is dict:
        return '{' + ','.join(json.dumps(k) + ':' + json_numbers(v) for k, v in value.items()) + '}'
    raise Invalid('unexpected_response_type')


def assemble_responses(responses, arm):
    return json_numbers({'schema': 'nider_scientific_submission_v1', 'task': TASK,
                         'policy': POLICY, 'arm': arm, 'cases': responses}).encode()
