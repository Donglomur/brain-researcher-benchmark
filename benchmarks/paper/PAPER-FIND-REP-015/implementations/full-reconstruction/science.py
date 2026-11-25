"""Task-specific science only. Caller owns bounded JSON I/O and isolated execution.

No data is opened/imported here. A wrong, well-formed reconstruction is scored,
not rejected for performance. References are operator-only decoded records.
"""
import bisect
import math
import sys

GRIDS = {'F2': 150001, 'F3': 30001}
EPS = sys.float_info.epsilon


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def identity_key(identity):
    return (identity['figure'], identity['mouse_source_label'], identity['source_index1'])


def curve_validate(curve, figure, trials):
    require(type(curve) is dict and set(curve) == {'starts_index1', 'FP', 'TP'}, 'Curve keys')
    starts, fp, tp = (curve[k] for k in ('starts_index1', 'FP', 'TP'))
    require(all(type(v) is list for v in (starts, fp, tp)), 'Curve lists')
    require(1 <= len(starts) == len(fp) == len(tp) <= min(GRIDS[figure], 174 * trials + 1),
            'Complete bounded step representation')
    require(starts[0] == 1 and all(type(x) is int and 1 <= x <= GRIDS[figure] for x in starts)
            and all(x < y for x, y in zip(starts, starts[1:])), 'Increasing inclusive starts')
    require(all(finite(x) and 0 <= x <= 1 for x in fp + tp), 'Finite probabilities')


def at(curve, index):
    pos = bisect.bisect_right(curve['starts_index1'], index) - 1
    return curve['FP'][pos], curve['TP'][pos]


def first_max(curve):
    gaps = [abs(t - f) for f, t in zip(curve['FP'], curve['TP'])]
    return curve['starts_index1'][gaps.index(max(gaps))]


def area(curve, figure):
    fp, tp = curve['FP'], curve['TP']
    # Constant intervals have zero trapezoid width. Retain threshold order.
    terms = [(fp[i-1] - fp[i]) * (tp[i-1] + tp[i]) / 2 for i in range(1, len(fp))]
    endpoint = (1 - fp[0]) * tp[0] if figure == 'F2' else 1 - fp[0]
    return math.fsum(terms) + endpoint, math.fsum(abs(x) for x in terms)


def curve_error(candidate, reference, figure):
    """Compare every logical grid location, regardless of step segmentation."""
    ends = sorted(set(candidate['starts_index1'] + reference['starts_index1'] + [GRIDS[figure] + 1]))
    fp_parts, tp_parts, maximum, fp_max, tp_max = [], [], 0.0, 0.0, 0.0
    for left, right in zip(ends, ends[1:]):
        cf, ct = at(candidate, left); rf, rt = at(reference, left)
        df, dt = abs(cf - rf), abs(ct - rt)
        fp_parts.append((right - left) * df); tp_parts.append((right - left) * dt)
        fp_max = max(fp_max, df); tp_max = max(tp_max, dt)
        maximum = max(maximum, df, dt)
    return {'FP_MAE': math.fsum(fp_parts) / GRIDS[figure],
            'TP_MAE': math.fsum(tp_parts) / GRIDS[figure],
            'FP_max_abs_error': fp_max, 'TP_max_abs_error': tp_max,
            'curve_max_abs_error': maximum}


def count_validate(row):
    require(type(row) is list and len(row) == 4 and all(type(x) is int for x in row),
            'Detection/FalseAlarm/Hit/Boundary integer row')
    detected, false, hit, boundary = row
    require(0 <= detected <= 174 and 0 <= false <= detected and 0 <= boundary <= 2
            and false + boundary <= detected and hit in (0, 1)
            and hit == int(detected - false - boundary > 0), 'Peak count conservation')


def validate(record, identity):
    figure, n = identity['figure'], identity['trials']
    keys = {'identity', 'curve', 'selected_index1', 'selected_trial_counts'}
    if figure == 'F3':
        keys.add('timing')
    require(type(record) is dict and set(record) == keys and record['identity'] == identity,
            'Exact public identity and output fields')
    actual_identity = record['identity']
    require(type(actual_identity) is dict and
            all(type(actual_identity[k]) is int for k in ('source_index1', 'trials')) and
            all(type(actual_identity[k]) is str for k in ('figure', 'mouse_source_label')),
            'Typed identity; JSON booleans/floats cannot alias integer keys')
    curve_validate(record['curve'], figure, n)
    require(type(record['selected_index1']) is int and 1 <= record['selected_index1'] <= GRIDS[figure],
            'Selected threshold index')
    counts = record['selected_trial_counts']
    require(type(counts) is list and len(counts) == n, 'Every trial count row')
    for row in counts:
        count_validate(row)
    if figure == 'F3':
        t = record['timing']
        require(type(t) is dict and set(t) == {'mean_silencing', 'mean_peak_index1',
                'trial_peak_indices1', 'trial_flat_selected_window'}, 'Timing fields')
        require(type(t['mean_silencing']) is list and len(t['mean_silencing']) == 350
                and all(finite(x) for x in t['mean_silencing']), 'Complete finite mean trace')
        require(type(t['mean_peak_index1']) is int and 1 <= t['mean_peak_index1'] <= 350,
                'Mean peak index')
        require(type(t['trial_peak_indices1']) is list and len(t['trial_peak_indices1']) == n
                and all(type(x) is int and 1 <= x <= 350 for x in t['trial_peak_indices1']),
                'Complete trial timing')
        require(type(t['trial_flat_selected_window']) is list and len(t['trial_flat_selected_window']) == n
                and all(type(x) is bool for x in t['trial_flat_selected_window']), 'Explicit flat flags')


def reference_counts(reference, index):
    rows = []
    for steps in reference['trial_count_steps']:
        i = bisect.bisect_right([row[0] for row in steps], index) - 1
        require(i >= 0, 'Reference count coverage')
        rows.append(steps[i][1:])
    return rows


def grade(record, reference):
    """Continuous reconstruction errors plus explicit protocol-conformance flags.

    Reference includes candidate-shaped target plus private trial_count_steps.
    Selection mismatch is diagnostic, not a zero/one performance cliff.
    """
    target = reference['target']; identity = target['identity']; figure = identity['figure']
    validate(record, identity); validate(target, identity)
    curve, gold = record['curve'], target['curve']; index = record['selected_index1']
    result = curve_error(curve, gold, figure)
    ca, _ = area(curve, figure); ra, absolute_terms = area(gold, figure)
    probability_bound = (1e-10 + 1e-10 * max(gold['FP'] + gold['TP']) if figure == 'F2'
                         else 64 * EPS * identity['trials'])
    area_bound = (1e-9 + 1e-10 * abs(ra) if figure == 'F2'
                  else 32 * EPS * GRIDS[figure] * max(1, absolute_terms))
    selected = at(gold, index); optimum = at(gold, first_max(gold))
    regret = max(0.0, abs(optimum[1] - optimum[0]) - abs(selected[1] - selected[0]))
    expected = reference_counts(reference, index)
    mismatch = sum(a != b for a, b in zip(record['selected_trial_counts'], expected))
    counts = record['selected_trial_counts']; n = identity['trials']
    count_fp = math.fsum((f * 100 / d) / 100 if d else 0.0 for d, f, h, b in counts) / n
    count_tp = math.fsum(h for d, f, h, b in counts) / n
    chosen_fp, chosen_tp = at(curve, index)
    result.update(identity=identity, candidate_literal_area=ca, reference_literal_area=ra,
                  literal_area_abs_error=abs(ca-ra), curve_probability_bound=probability_bound,
                  literal_area_bound=area_bound, selection_regret=regret,
                  selection_gap_uncertainty=4 * probability_bound,
                  selected_index_disagrees=index != target['selected_index1'],
                  selected_index_is_own_first_argmax=index == first_max(curve),
                  selected_counts_mismatch_fraction=mismatch / n,
                  counts_curve_consistent=max(abs(count_fp-chosen_fp), abs(count_tp-chosen_tp)) <= probability_bound,
                  curve_within_reference_tolerance=result['curve_max_abs_error'] <= probability_bound,
                  literal_area_within_reference_tolerance=abs(ca-ra) <= area_bound,
                  selection_within_reference_uncertainty=regret <= 4 * probability_bound)
    if figure == 'F3':
        t, g = record['timing'], target['timing']
        center = t['mean_peak_index1']; left, right = max(1, center - 2), min(350, center + 1)
        difference = [abs(x-y) for x, y in zip(t['mean_silencing'], g['mean_silencing'])]
        require(all(math.isfinite(x) for x in difference), 'Finite representable timing errors')
        result.update(mean_trace_MAE=finite_mean(difference),
                      mean_trace_max_abs_error=max(difference),
                      mean_peak_abs_error_ms=10 * abs(center - g['mean_peak_index1']),
                      trial_timing_MAE_ms=math.fsum(10 * abs(x-y) for x, y in
                          zip(t['trial_peak_indices1'], g['trial_peak_indices1'])) / n,
                      flat_flag_mismatch_fraction=sum(x != y for x, y in
                          zip(t['trial_flat_selected_window'], g['trial_flat_selected_window'])) / n,
                      reference_flat_trial_count=sum(g['trial_flat_selected_window']),
                      mean_peak_is_own_first_argmax=center == t['mean_silencing'].index(max(t['mean_silencing'])) + 1,
                      trial_indices_within_own_selected_window=all(left <= x <= right for x in t['trial_peak_indices1']))
    return result


def finite_mean(values):
    """Preserve ordinary reductions and avoid premature subnormal rounding.

    Dividing each term first avoids sum overflow, but may erase representable
    mean errors. Only the subnormal/overflow cases use an exact binary mean.
    """
    values = list(values)
    require(values, 'Nonempty mean support required')
    scaled = [value / len(values) for value in values]
    if not any(value != 0 and abs(part) < sys.float_info.min
               for value, part in zip(values, scaled)):
        try:
            return math.fsum(scaled)
        except OverflowError:
            pass
    from fractions import Fraction
    return float(sum((Fraction(value) for value in values), Fraction()) / len(values))


def aggregate(rows, roster):
    require(type(rows) is list and len(rows) == len(roster), 'Complete fixed roster required')
    require([r['identity'] for r in rows] == roster and
            len({identity_key(x) for x in roster}) == len(roster), 'Ordered unique complete identities')
    fields = ['FP_MAE', 'TP_MAE', 'literal_area_abs_error', 'selection_regret',
              'selected_counts_mismatch_fraction']
    answer = {}
    for figure in ('F2', 'F3'):
        subset = [r for r in rows if r['identity']['figure'] == figure]
        require(subset, 'Both figure supports required')
        mice = sorted({r['identity']['mouse_source_label'] for r in subset})
        columns = fields + (['mean_trace_MAE', 'mean_peak_abs_error_ms', 'trial_timing_MAE_ms',
                             'flat_flag_mismatch_fraction'] if figure == 'F3' else [])
        by_mouse = {}
        for mouse in mice:
            group = [r for r in subset if r['identity']['mouse_source_label'] == mouse]
            by_mouse[mouse] = {k: finite_mean(r[k] for r in group) for k in columns}
        answer[figure] = {'records': len(subset), 'mice': len(mice), 'by_mouse': by_mouse,
            'equal_mouse_mean': {k: finite_mean(by_mouse[m][k] for m in mice) for k in columns},
            'worst_curve_abs_error': max(r['curve_max_abs_error'] for r in subset),
            'exact_selected_index_disagreements': sum(r['selected_index_disagrees'] for r in subset),
            'selection_outside_uncertainty': sum(not r['selection_within_reference_uncertainty'] for r in subset),
            'own_selection_rule_violations': sum(not r['selected_index_is_own_first_argmax'] for r in subset),
            'counts_curve_inconsistencies': sum(not r['counts_curve_consistent'] for r in subset)}
    return {'status': 'complete_scored_reconstruction', 'contract_valid': True,
            'aggregation': 'equal mouse; equal unit or reward panel within mouse',
            'figures': answer, 'combined_scalar_score': None,
            'interpretation': 'Errors against explicit source protocol; no larger-area reward or biological inference.'}
