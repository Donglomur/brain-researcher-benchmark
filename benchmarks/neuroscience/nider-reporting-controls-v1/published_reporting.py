"""Source-only research reporting criterion; no estimator or automatic execution.

This checks explicitly reported quantities at publication precision. It does not
certify full numerical estimator accuracy or reuse R-specific formatted strings.
All arithmetic defining reporting intervals uses exact rational numbers.
"""
from decimal import Decimal
from fractions import Fraction
import json
import re

IDS = ('amy_self', 'quest_self', 'amy_quest')
METRICS = ('pearson_r', 'p_two_sided', 'k', 'N')
FLOAT_METRICS = ('pearson_r', 'p_two_sided')
FIXED = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')


class InvalidInput(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise InvalidInput(code)


def exact_number(value):
    require(isinstance(value, Decimal) and value.is_finite(), 'finite_JSON_number_required')
    require(len(value.as_tuple().digits) <= 400 and -400 <= value.as_tuple().exponent <= 400, 'numeric_extent')
    return Fraction(value)


def decode_numeric_json(raw):
    require(isinstance(raw, bytes) and len(raw) <= 65536, 'candidate_extent')

    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, 'duplicate_JSON_key')
            obj[key] = value
        return obj

    def forbidden(value):
        raise InvalidInput('nonfinite_JSON_constant')

    return json.loads(raw, parse_float=Decimal, parse_int=Decimal,
                      parse_constant=forbidden, object_pairs_hook=pairs)


def validate_rows(candidate):
    require(isinstance(candidate, dict) and set(candidate) == {'schema', 'rows'}, 'candidate_schema_keys')
    require(candidate['schema'] == 'nider_published_numeric_submission_v1', 'candidate_schema')
    rows = candidate['rows']
    require(isinstance(rows, list) and len(rows) == 3, 'three_complete_contrasts_required')
    found = {}
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'contrast', 'fields'}, 'row_keys')
        contrast = row['contrast']
        require(isinstance(contrast, str) and contrast in IDS and contrast not in found, 'contrast_identity')
        fields = row['fields']
        require(isinstance(fields, dict) and set(fields) == set(METRICS), 'complete_four_fields_required')
        values = {key: exact_number(value) for key, value in fields.items()}
        require(-1 <= values['pearson_r'] <= 1, 'Pearson_range')
        require(0 <= values['p_two_sided'] <= 1, 'p_range')
        for key in ('k', 'N'):
            require(values[key].denominator == 1 and values[key] >= 1, 'positive_exact_count')
        require(values['N'] >= values['k'], 'count_order')
        found[contrast] = values
    require(set(found) == set(IDS), 'complete_contrast_support')
    return found


def validate_target(target):
    require(isinstance(target, dict) and set(target) == {'schema', 'source_pin', 'source_url', 'locator', 'rows'}, 'target_keys')
    require(target['schema'] == 'nider_published_caption_targets_v1', 'target_schema')
    require(target['locator'] == 'Figure 1 caption; The correlations were; all tests two-sided and uncorrected', 'target_locator')
    pin = target['source_pin']
    require(isinstance(pin, dict) and set(pin) == {'path', 'bytes', 'sha256'}, 'target_source_pin')
    require(isinstance(pin['sha256'], str) and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'target_source_digest')
    require(target['source_url'] == 'https://www.nature.com/articles/s41586-026-11203-1', 'target_source_url')
    require(isinstance(target['rows'], list) and len(target['rows']) == 3, 'target_three_rows')
    found = {}
    for row in target['rows']:
        require(isinstance(row, dict) and set(row) == {'contrast', 'display_lexemes'}, 'target_row_keys')
        contrast = row['contrast']
        require(contrast in IDS and contrast not in found, 'target_contrast_identity')
        values = row['display_lexemes']
        require(isinstance(values, dict) and set(values) == set(METRICS), 'target_metric_support')
        parsed = {}
        for key, lexeme in values.items():
            require(isinstance(lexeme, str) and len(lexeme) <= 32 and FIXED.fullmatch(lexeme), 'target_fixed_decimal_lexeme')
            decimal = Decimal(lexeme)
            places = -decimal.as_tuple().exponent
            require(places == {'pearson_r': 2, 'p_two_sided': 3, 'k': 0, 'N': 0}[key], 'published_display_precision')
            value = Fraction(decimal)
            if key == 'pearson_r':
                require(-1 <= value <= 1, 'target_Pearson_range')
            elif key == 'p_two_sided':
                require(0 <= value <= 1, 'target_p_range')
            else:
                require(value.denominator == 1 and value >= 1, 'target_count')
            parsed[key] = (value, Fraction(1, 10 ** places))
        require(parsed['N'][0] >= parsed['k'][0], 'target_count_order')
        found[contrast] = parsed
    return found


def classify_interval(low, high, center, quantum):
    """Nearest-reporting interior; unresolved ties are not silently passed.

    The publication does not identify its tie-breaking convention. Exact boundary
    equality, or a certified input interval crossing it, remains indeterminate.
    Domain clipping is unnecessary because input domain is validated separately.
    """
    require(low <= high and quantum > 0, 'interval_shape')
    left, right = center - quantum / 2, center + quantum / 2
    if left < low and high < right:
        return 'REPORTING_AGREEMENT'
    if high < left or low > right:
        return 'REPORTING_DISAGREEMENT'
    return 'INDETERMINATE_REPORTING_BOUNDARY'


def compare_candidate(candidate, target):
    actual = validate_rows(candidate)
    reference = validate_target(target)
    records = []
    for contrast in IDS:
        for metric in METRICS:
            value = actual[contrast][metric]
            center, quantum = reference[contrast][metric]
            if metric in FLOAT_METRICS:
                status = classify_interval(value, value, center, quantum)
            else:
                status = 'EXACT_COUNT_AGREEMENT' if value == center else 'EXACT_COUNT_DISAGREEMENT'
            records.append({'contrast': contrast, 'metric': metric, 'status': status})
    passed = all(x['status'] in ('REPORTING_AGREEMENT', 'EXACT_COUNT_AGREEMENT') for x in records)
    return {'schema': 'nider_published_reporting_comparison_v1',
            'status': 'COMPLETE_PUBLISHED_REPORTING_AGREEMENT' if passed else 'PUBLISHED_REPORTING_NOT_ESTABLISHED',
            'evaluated_fields': 12, 'per_field': records, 'requires_R_formatted_strings': False,
            'numeric_estimator_accuracy_certified': False, 'procedure_correctness_established': False,
            'publication_rounding_assumption': 'nearest displayed decimal; exact ties unresolved',
            'all_36_native_fields_qualified': False, 'scientifically_qualified_benchmark': False}


def tanh_rational_bounds(z):
    """Certified algebraic enclosure for a supplied rational Fisher-z value.

    This is a scale projection, not a fit or an estimator-error analysis.
    For x=2|z|<=16, e^x is enclosed by its degree128 Taylor partial sum
    and S128+t129/(1-x/130). Later successive-term ratios are <=x/130.
    Transform endpoints monotonically with (e^x-1)/(e^x+1), then restore sign.
    """
    require(isinstance(z, Fraction) and abs(z) <= 8, 'bounded_rational_Fisher_z_required')
    x = 2 * abs(z)
    term = Fraction(1)
    total = term
    for order in range(1, 129):
        term = term * x / order
        total += term
    next_term = term * x / 129
    upper_exp = total + next_term / (1 - x / 130)
    low = (total - 1) / (total + 1)
    high = (upper_exp - 1) / (upper_exp + 1)
    return (-high, -low) if z < 0 else (low, high)


def compare_serialized_native(native, target):
    """Audit the frozen serialized native values against the published caption.

    The Fisher-z output remains intact. A separate Pearson-scale enclosure is
    used only for this paper-reporting comparison. Raw-z display agreement is
    diagnostic, since coarse published precision may fail to distinguish scales.
    This evaluates existing output; it does not execute any meta-analysis.
    """
    require(isinstance(native, dict) and set(native) == {'schema', 'rows'} and
            native['schema'] == 'nider-reproduction-values-v1', 'native_schema')
    require(isinstance(native['rows'], list) and len(native['rows']) == 3, 'native_rows')
    names = {'TE_random', 'lower_random', 'upper_random', 'pval_random', 'k', 'N',
             'tau', 'lower_tau', 'upper_tau', 'Q', 'df_Q', 'pval_Q'}
    found = {}
    for row in native['rows']:
        require(isinstance(row, dict) and set(row) == {'contrast', 'fields', 'formatted_table'}, 'native_row_keys')
        contrast = row['contrast']
        require(isinstance(contrast, str) and contrast in IDS and contrast not in found, 'native_contrast_identity')
        require(isinstance(row['fields'], dict) and set(row['fields']) == names, 'native_complete_fields')
        require(isinstance(row['formatted_table'], list) and len(row['formatted_table']) == 11 and
                all(isinstance(x, str) for x in row['formatted_table']), 'native_archived_display_schema')
        found[contrast] = {key: exact_number(value) for key, value in row['fields'].items()}
        require(0 <= found[contrast]['pval_random'] <= 1, 'native_p_range')
        require(found[contrast]['N'] >= found[contrast]['k'] >= 1, 'native_count_order')
        require(all(found[contrast][key].denominator == 1 for key in ('N', 'k', 'df_Q')), 'native_exact_counts')
    reference = validate_target(target)
    records = []
    for contrast in IDS:
        fields = found[contrast]
        for metric in METRICS:
            center, quantum = reference[contrast][metric]
            if metric == 'pearson_r':
                low, high = tanh_rational_bounds(fields['TE_random'])
                status = classify_interval(low, high, center, quantum)
                diagnostic = classify_interval(fields['TE_random'], fields['TE_random'], center, quantum)
                records.append({'contrast': contrast, 'metric': metric, 'status': status,
                                'projection': 'certified_rational_tanh_enclosure_of_serialized_Fisher_z',
                                'raw_Fisher_z_as_r_diagnostic_status': diagnostic,
                                'reporting_status_differs_between_scale_projections': diagnostic != status})
            elif metric == 'p_two_sided':
                value = fields['pval_random']
                records.append({'contrast': contrast, 'metric': metric,
                                'status': classify_interval(value, value, center, quantum),
                                'projection': 'unchanged_serialized_native_pval_random'})
            else:
                records.append({'contrast': contrast, 'metric': metric,
                                'status': 'EXACT_COUNT_AGREEMENT' if fields[metric] == center else 'EXACT_COUNT_DISAGREEMENT'})
    passed = all(x['status'] in ('REPORTING_AGREEMENT', 'EXACT_COUNT_AGREEMENT') for x in records)
    return {'schema': 'nider_serialized_native_published_reporting_audit_v1',
            'status': 'COMPLETE_PUBLISHED_REPORTING_AGREEMENT' if passed else 'PUBLISHED_REPORTING_NOT_ESTABLISHED',
            'evaluated_fields': 12, 'per_field': records,
            'input_semantics': 'exact decimal values represented by authenticated native JSON serialization',
            'original_binary64_reconstruction_claimed': False,
            'native_Fisher_z_values_overwritten': False, 'statistical_fits': 0,
            'all_36_native_fields_qualified': False, 'independent_estimator_accuracy_certified': False,
            'procedure_correctness_established': False, 'scientifically_qualified_benchmark': False}
