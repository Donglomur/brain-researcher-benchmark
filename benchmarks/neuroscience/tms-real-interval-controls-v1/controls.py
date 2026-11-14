"""Finite invented controls; Fraction oracles do not call kernel rational math.

The 248-slot integration repeats four scalar examples. It is not 248 authentic
certifications and does not read any original input, prior result or native code.
"""
from fractions import Fraction
import copy
import json
import math
import struct
import time

import kernel as k
import certificate as c
import scorer as s


def run(budget, context, write):
    records, calls = [], []
    certifier = k.Certifier(budget)
    started = time.monotonic()

    def check(name, condition, evidence=None):
        if not condition:
            raise AssertionError(name)
        records.append({'name': name, 'passed': True, 'evidence': evidence})

    def refuses(name, operation, text):
        try:
            operation()
        except k.Refusal as exc:
            check(name, text in str(exc), {'refusal': str(exc)})
        else:
            raise AssertionError(name + ': expected refusal')

    def enclosed(iv, value):
        # Independent exact cross-products, not Interval.contains or kernel.Rat.
        return iv.lo * value.denominator <= value.numerator * (1 << 768) <= iv.hi * value.denominator

    def pair(name, a, b):
        before = (budget.calls, budget.values, budget.supplied_values)
        tick = time.monotonic()
        try:
            return certifier.pair(a, b)
        finally:
            calls.append({'name': name, 'kind': 'pair', 'calls_before_after': [before[0], budget.calls],
                          'validated_values_before_after': [before[1], budget.values],
                          'supplied_values_before_after': [before[2], budget.supplied_values],
                          'elapsed_seconds': time.monotonic() - tick})

    def direct_exp(name, iv):
        before = budget.calls
        tick = time.monotonic()
        try:
            budget.call()
            return k.positive_exp_reduced(iv, budget)
        finally:
            calls.append({'name': name, 'kind': 'reduced_exp', 'calls_before_after': [before, budget.calls],
                          'validated_values_before_after': [budget.values, budget.values],
                          'supplied_values_before_after': [budget.supplied_values, budget.supplied_values],
                          'elapsed_seconds': time.monotonic() - tick})

    for n, d in [(-7, 3), (-1, 3), (0, 1), (1, 3), (7, 3)]:
        iv = k.from_rat(k.Rat(n, d))
        q = Fraction(n, d)
        check('directed_rational_%s_%s' % (n, d), enclosed(iv, q) and iv.hi - iv.lo <= 1)
    x, y = k.Interval(-2 * k.D, k.D), k.Interval(-3 * k.D, 4 * k.D)
    xy = k.times(x, y)
    check('cross_zero_product', xy.lo == -8 * k.D and xy.hi == 6 * k.D)
    inv = k.positive_reciprocal(k.Interval(2 * k.D, 3 * k.D))
    check('reciprocal_directed', enclosed(inv, Fraction(1, 3)) and enclosed(inv, Fraction(1, 2)))
    refuses('nonpositive_reciprocal', lambda: k.positive_reciprocal(k.Interval(0, k.D)), 'positive reciprocal')
    refuses('boolean_integer', lambda: k.Rat(True), 'nonboolean')
    refuses('zero_denominator', lambda: k.Rat(1, 0), 'nonzero')
    refuses('integer_bit_guard', lambda: k.Rat(1 << 8192), 'bit cap')
    refuses('multiplication_intermediate_guard', lambda: k.mul(1 << 4096, 1 << 4096), 'intermediate bit cap')
    refuses('reversed_interval', lambda: k.Interval(1, 0), 'ordered')

    # Independent Taylor oracle has 193 exact Fraction terms and a geometric
    # remainder. It neither imports the implementation's series nor ln/exp.
    for numerator in (0, 1, 2):
        target = Fraction(numerator, 4)
        got = direct_exp('independent_exp_%d_quarters' % numerator,
                         k.Interval(numerator * k.D // 4, numerator * k.D // 4))
        term = total = Fraction(1)
        for degree in range(1, 193):
            term *= target / degree
            total += term
        remainder = term * target / 193 / (1 - target / 194)
        check('independent_exp_enclosure_%d' % numerator,
              enclosed(got, total) and enclosed(got, total + remainder))
    refuses('exp_domain_refusal', lambda: direct_exp('invalid_exp_domain', k.Interval(0, k.D)), 'half-unit domain')

    cases = [('zero', 0.0, 0.0, Fraction(0)),
             ('positive_decade', 0.0, 10.0, Fraction(9, 11)),
             ('negative_decade', 10.0, 0.0, Fraction(-9, 11)),
             ('two_decades', -10.0, 10.0, Fraction(99, 101)),
             ('shifted_decade', 990.0, 1000.0, Fraction(9, 11)),
             ('positive_extreme', -1000.0, 1000.0, Fraction(10 ** 200 - 1, 10 ** 200 + 1)),
             ('negative_extreme', 1000.0, -1000.0, Fraction(-(10 ** 200 - 1), 10 ** 200 + 1))]
    pairs = {}
    for name, a, b, oracle in cases:
        result = pair(name, [a] * 15, [b] * 15)
        pairs[name] = result
        check('closed_form_' + name, enclosed(result.interval, oracle)
              and result.pin.count == result.pout.count == 15
              and result.pin.positions == result.pout.positions == (1 << 15) - 1)
    check('exact_zero_width', pairs['zero'].interval == k.Interval(0, 0))
    check('antisymmetric_exact_bounds',
          pairs['negative_decade'].interval == k.Interval(-pairs['positive_decade'].interval.hi,
                                                         -pairs['positive_decade'].interval.lo))
    check('common_shift_invariance', pairs['shifted_decade'].interval == pairs['positive_decade'].interval)

    nan = float('nan')
    sparse = pair('sparse_support', [0.0] + [nan] * 14, [nan] * 14 + [10.0])
    check('all15_position_masks_retained', sparse.pin.count == sparse.pout.count == 1
          and sparse.pin.positions == 1 and sparse.pout.positions == 1 << 14
          and enclosed(sparse.interval, Fraction(9, 11)))
    undefined = pair('undefined_group', [nan] * 15, [10.0] * 15)
    check('all_nan_is_undefined', undefined.interval is None and undefined.pin.count == 0
          and undefined.pin.positions == 0 and undefined.pout.count == 15)
    subnormal = float.fromhex('0x0.0000000000001p-1022')
    tiny = k.exact_mean([subnormal] + [0.0] * 14, budget)
    check('smallest_subnormal_exact_mean', Fraction(tiny.value.n, tiny.value.d) == Fraction(1, 15 * (1 << 1074)))
    reordered = k.exact_mean([0.0] * 14 + [subnormal], budget)
    check('exact_mean_permutation_invariance', tiny.value == reordered.value)
    for name, bad, message in [('infinite', float('inf'), 'infinite raw'),
                               ('negative_infinite', -float('inf'), 'infinite raw'),
                               ('out_of_domain', math.nextafter(1000.0, math.inf), 'raw domain'),
                               ('bool_input', True, 'binary64 float'),
                               ('int_input', 0, 'binary64 float')]:
        refuses('raw_' + name, lambda bad=bad, name=name: pair(name, [bad] + [0.0] * 14, [0.0] * 15), message)
    refuses('invalid_second_group_not_hidden_by_nan',
            lambda: pair('undefined_then_infinite', [nan] * 15, [float('inf')] + [0.0] * 14), 'infinite raw')
    refuses('missing_source_position', lambda: pair('fourteen_positions', [0.0] * 14, [0.0] * 15), 'fifteen')
    refuses('extra_source_position', lambda: pair('sixteen_positions', [0.0] * 16, [0.0] * 15), 'fifteen')

    zero, pos = pairs['zero'].interval, pairs['positive_decade'].interval
    rows = [[zero] + [None] * 27, [pos, pos] + [None] * 26] + [[None] * 28 for _ in range(5)]
    nested = k.window(rows)
    check('nested_not_pooled_weighting', enclosed(nested.interval, Fraction(9, 22))
          and not enclosed(nested.interval, Fraction(6, 11))
          and nested.time_counts == (1, 2, 0, 0, 0, 0, 0) and nested.frequency_count == 2)
    empty_window = k.window([[None] * 28 for _ in range(7)])
    check('all_nan_nested_support', empty_window.interval is None and empty_window.frequency_count == 0)
    refuses('wrong_frequency_count', lambda: k.window([[zero] * 28] * 6), 'seven')
    refuses('wrong_time_count', lambda: k.window([[zero] * 27] * 7), 'twenty-eight')
    refuses('wide_final_certificate', lambda: k.window([[k.Interval(-k.D, k.D)] * 28] * 7), 'diameter')
    # Resource controls perform ledger operations only, no extra certifications.
    refuses('deadline_type', lambda: k.Budget(deadline=True, max_calls=1, max_values=1), 'future finite')
    refuses('boolean_call_cap', lambda: k.Budget(deadline=budget.deadline, max_calls=True, max_values=1), 'call limit')
    limited = k.Budget(deadline=budget.deadline, max_calls=1, max_values=1)
    limited.calls = 1
    refuses('call_cap_refusal', limited.call, 'scalar certification cap')
    refuses('raw_cap_refusal', lambda: limited.inputs(2), 'raw value cap')
    refuses('supplied_raw_cap_refusal', lambda: limited.supplied_inputs(2), 'supplied raw value cap')
    limited.deadline = 0.0
    refuses('expired_budget_refusal', limited.check, 'kernel deadline')

    oracles = (Fraction(0), Fraction(9, 11), Fraction(-9, 11), Fraction(99, 101))
    four = [pairs[name].interval for name in ('zero', 'positive_decade', 'negative_decade', 'two_decades')]
    repeated_windows = [k.window([[iv] * 28 for _ in range(7)]) for iv in four]
    windows = [empty_window if i % 62 == 0 else repeated_windows[i // 62] for i in range(248)]
    ref = c.pack_fixture_reference(windows, context)
    ref_pin = c.pin(ref)
    doc = json.loads(ref)
    write('FIXTURE_REFERENCE.private.json', ref)
    c.admit_fixture_reference(ref, ref_pin, context)
    check('complete248_fixture_admitted', len(doc['slots']) == 248 and all(row['index'] == i for i, row in enumerate(doc['slots'])))

    def mutated(name, mutate, message):
        value = copy.deepcopy(doc)
        mutate(value)
        raw = c.encode(value)
        # Rehashing deliberately bypasses the byte mismatch so semantic admission
        # is tested. This is fixture authority only, never authentic custody.
        refuses(name, lambda: c.admit_fixture_reference(raw, c.pin(raw), context), message)
        records[-1]['evidence']['mutated_body_pin'] = c.pin(raw)

    changes = [
        ('flag_int', lambda d: d.__setitem__('authentic_source', 0), 'fixture never authentic'),
        ('promoted_fixture', lambda d: d.__setitem__('authentic_source', True), 'fixture never authentic'),
        ('profile_changed', lambda d: d.__setitem__('schema', 'authentic'), 'fixture profile'),
        ('fraction_float', lambda d: d.__setitem__('fractional_bits', 768.0), 'fractional bits'),
        ('domain_float', lambda d: d.__setitem__('domain_bound', 1000.0), 'prospective domain'),
        ('float_slot_index', lambda d: d['slots'][1].__setitem__('index', 1.0), 'slot index'),
        ('bool_slot_index', lambda d: d['slots'][1].__setitem__('index', True), 'slot index'),
        ('undefined_int', lambda d: d['slots'][1].__setitem__('undefined', 0), 'undefined Boolean'),
        ('endpoint_number', lambda d: d['slots'][1].__setitem__('lo', 0), 'endpoint text'),
        ('endpoint_negative_zero', lambda d: d['slots'][1].__setitem__('lo', '-0'), 'endpoint text'),
        ('endpoint_leading_zero', lambda d: d['slots'][1].__setitem__('lo', '00'), 'endpoint text'),
        ('endpoint_plus', lambda d: d['slots'][1].__setitem__('lo', '+0'), 'endpoint text'),
        ('endpoint_unicode_digit', lambda d: d['slots'][1].__setitem__('lo', '\u0660'), 'endpoint text'),
        ('endpoint_too_long', lambda d: d['slots'][1].__setitem__('lo', '1' * 236), 'endpoint text'),
        ('endpoint_outside_range', lambda d: d['slots'][1].__setitem__('lo', str(k.D + 1)), 'endpoint range'),
        ('endpoint_width', lambda d: d['slots'][1].update(lo='0', hi=str(k.MAX_WIDTH + 1)), 'diameter'),
        ('endpoint_reversed', lambda d: d['slots'][1].update(lo='1', hi='0'), 'diameter'),
        ('time_support_bool', lambda d: d['slots'][1]['time_counts'].__setitem__(0, True), 'time support'),
        ('time_support29', lambda d: d['slots'][1]['time_counts'].__setitem__(0, 29), 'time support'),
        ('frequency_support_float', lambda d: d['slots'][1].__setitem__('frequency_count', 7.0), 'frequency support'),
        ('frequency_support_mismatch', lambda d: d['slots'][1].__setitem__('frequency_count', 6), 'frequency support'),
        ('undefined_numeric_endpoint', lambda d: d['slots'][0].__setitem__('lo', '0'), 'undefined has no'),
        ('undefined_nonzero_support', lambda d: d['slots'][0].update(time_counts=[1]*7, frequency_count=7), 'undefined has no'),
        ('missing_slot', lambda d: d['slots'].pop(), 'all248'),
        ('extra_slot', lambda d: d['slots'].append(d['slots'][-1]), 'all248'),
        ('wrong_label', lambda d: d['slots'][1].__setitem__('channel', 'physical-person'), 'channel identity'),
        ('wrong_map', lambda d: d['slots'][1].__setitem__('map', 'T.delay1'), 'map identity'),
        ('binding_hash_changed', lambda d: d['binding'].__setitem__('fixture_sha256', 'f'*64), 'runtime/attempt binding'),
        ('extra_root_field', lambda d: d.__setitem__('extra', None), 'closed schema'),
        ('extra_row_field', lambda d: d['slots'][1].__setitem__('extra', None), 'closed schema')]
    for name, mutation, message in changes:
        mutated(name, mutation, message)
    refuses('reference_hash_mutant', lambda: c.admit_fixture_reference(ref, {'bytes': len(ref), 'sha256': '0'*64}, context), 'byte/hash')
    refuses('public_reference_oversize_before_hash', lambda: c.admit_fixture_reference(b' ' * (c.MAX_BODY+1), ref_pin, context), 'before hashing')
    refuses('public_reference_nonbytes_before_hash', lambda: c.admit_fixture_reference(bytearray(ref), ref_pin, context), 'before hashing')
    refuses('duplicate_json_key', lambda: c.decode(b'{"x":1,"x":2}'), 'duplicate JSON')
    refuses('nonfinite_json', lambda: c.decode(b'{"x":NaN}'), 'nonfinite JSON')
    refuses('oversized_certificate', lambda: c.decode(b' ' * (c.MAX_BODY + 1)), 'bounded exact')
    refuses('production_rejects_fixture', lambda: c.admit_production_reference(ref, ref_pin, context), 'production source custody')
    promoted = copy.deepcopy(doc)
    promoted['authentic_source'] = True
    promoted['schema'] = 'tms_real_interval_248_authentic_v1'
    promoted_raw = c.encode(promoted)
    refuses('production_rejects_promoted_rehashed_fixture',
            lambda: c.admit_production_reference(promoted_raw, c.pin(promoted_raw), context), 'production source custody')
    refuses('production_scorer_rejects_fixture', lambda: s.score_production(reference_body=ref), 'production source custody')

    values = [nan if i % 62 == 0 else float(oracles[i // 62]) for i in range(248)]
    candidate = s.candidate_bytes(values)
    write('CANDIDATE_BASELINE.private.bin', candidate)
    baseline = s.score_fixture(candidate_body=candidate, reference_body=ref, reference_pin=ref_pin, context=context)
    write('SCORE_BASELINE.private.json', c.encode(baseline))
    errors = [abs(Fraction.from_float(float(q)) - q) for q in oracles]

    def rational_score(x):
        # Independent strict output consumer uses stdlib Fraction only.
        assert set(x) == {'numerator', 'denominator'}
        return Fraction(int(x['numerator']), int(x['denominator']))

    def score_encloses(metric, expected):
        return rational_score(metric['lower']) <= expected <= rational_score(metric['upper'])

    check('baseline_complete_categories', baseline['finite_slots'] == 244 and baseline['undefined_slots'] == 4
          and baseline['all248_categories_match'] and baseline['informative'])
    check('baseline_independent_pooled_mae', score_encloses(baseline['pooled']['MAE'], sum(errors, Fraction(0)) / 4))
    check('baseline_independent_linf', score_encloses(baseline['pooled']['Linf'], max(errors)))
    for i, name in enumerate(c.MAPS):
        check('independent_map_metrics_' + name,
              baseline['maps'][name]['finite_slots'] == 61
              and score_encloses(baseline['maps'][name]['MAE'], errors[i])
              and score_encloses(baseline['maps'][name]['Linf'], errors[i]))
    for i, row in enumerate(baseline['slots']):
        if i % 62:
            signed = Fraction.from_float(values[i]) - oracles[i // 62]
            check('independent_slot_residual_%03d' % i, score_encloses(row['signed'], signed)
                  and score_encloses(row['absolute'], abs(signed)))

    values[17] = 0.125
    mutant = s.candidate_bytes(values)
    write('CANDIDATE_MUTANT.private.bin', mutant)
    altered = s.score_fixture(candidate_body=mutant, reference_body=ref, reference_pin=ref_pin, context=context)
    write('SCORE_MUTANT.private.json', c.encode(altered))
    check('numeric_mutant_exact_mae', score_encloses(altered['pooled']['MAE'], sum(errors, Fraction(0))/4 + Fraction(1, 8*244)))
    check('numeric_mutant_exact_linf', score_encloses(altered['pooled']['Linf'], Fraction(1, 8)))
    check('numeric_mutant_one_changed_slot', [i for i in range(248) if altered['slots'][i] != baseline['slots'][i]] == [17])
    check('no_binary_or_scientific_threshold', altered['binary_threshold'] is None and altered['scientific_tolerance'] is None)
    badmask = bytearray(candidate); badmask[248*8+1] = 1
    refuses('candidate_mask_mismatch', lambda: s.score_fixture(candidate_body=bytes(badmask), reference_body=ref, reference_pin=ref_pin, context=context), 'category coherence')
    badmask[248*8+1] = 2
    refuses('candidate_mask_outside_binary', lambda: s.decode_candidate(bytes(badmask)), 'mask bytes')
    infbody = bytearray(candidate); infbody[8:16] = struct.pack('<d', math.inf)
    refuses('candidate_infinite', lambda: s.decode_candidate(bytes(infbody)), 'category coherence')
    category = list(struct.unpack('<248d', candidate[:248*8])); category[1] = nan
    refuses('candidate_source_category_mismatch', lambda: s.score_fixture(candidate_body=s.candidate_bytes(category), reference_body=ref, reference_pin=ref_pin, context=context), 'reference category')
    refuses('candidate_truncated', lambda: s.decode_candidate(candidate[:-1]), 'complete fixed')
    refuses('candidate_extra_byte', lambda: s.decode_candidate(candidate+b'\0'), 'complete fixed')
    category[1] = 2.0
    outside = s.score_fixture(candidate_body=s.candidate_bytes(category), reference_body=ref, reference_pin=ref_pin, context=context)
    check('outside_range_not_clipped', outside['out_of_proved_range_candidate_values'] == 1
          and score_encloses(outside['slots'][1]['absolute'], Fraction(2)))
    empty_ref = c.pack_fixture_reference([empty_window]*248, context)
    empty_score = s.score_fixture(candidate_body=s.candidate_bytes([nan]*248), reference_body=empty_ref,
                                  reference_pin=c.pin(empty_ref), context=context)
    check('all_undefined_noninformative', not empty_score['informative'] and empty_score['finite_slots'] == 0
          and empty_score['pooled']['MAE'] is None and empty_score['pooled']['Linf'] is None)
    check('exact_call_census', sum(x['calls_before_after'][1]-x['calls_before_after'][0] for x in calls) == budget.calls <= 64)
    check('supplied_raw_value_cap', budget.supplied_values == 540 and budget.supplied_values <= 4096)
    check('validated_raw_value_census', budget.values == 435)
    check('failed_first_group_charges_both_groups', all(x['supplied_values_before_after'][1]-x['supplied_values_before_after'][0] == 30
          and x['validated_values_before_after'][1]-x['validated_values_before_after'][0] == 15
          for x in calls if x['name'] in ('infinite','negative_infinite','out_of_domain','bool_input','int_input')))
    check('supplied_ledger_exact_call_and_direct_mean_join', sum(x['supplied_values_before_after'][1]-x['supplied_values_before_after'][0] for x in calls)+30 == budget.supplied_values)
    check('combined_raw_and_candidate_input_cap', budget.supplied_values + 5*248 == 1780 and budget.supplied_values + 5*248 <= 4096)
    budget.check()
    report = {'schema': 'tms_real_interval_inert_controls_v1', 'all_passed': True,
              'control_count': len(records), 'controls': records, 'scalar_call_ledger': calls,
              'scalar_calls': budget.calls, 'raw_inert_values': budget.supplied_values,
              'validated_raw_inert_values': budget.values,
              'candidate_serialization_input_values': 5 * 248,
              'combined_supplied_raw_and_candidate_serialization_values': budget.supplied_values + 5 * 248,
              'budget_checks': budget.steps, 'elapsed_seconds': time.monotonic()-started,
              'fixture_reuses_four_scalar_examples_across248_slots': True,
              'authentic_certifications': 0, 'primary_reads': 0, 'prior_output_reads': 0,
              'production_admission_implemented': False, 'native_parity': False,
              'full_log_series_evaluations': int(certifier.log_constant is not None)}
    write('CONTROLS.json', c.encode(report))
    return report
