"""Source-order command and time diagnostics, never eligibility or targets."""
from bisect import bisect_right
from fractions import Fraction
import math


def finite(v):
    return type(v) is int or (type(v) is float and math.isfinite(v))


def rational(v):
    if not finite(v):
        raise ValueError('finite represented scalar required')
    return Fraction(v)


def ratio(v):
    v = Fraction(v)
    return {'numerator': str(v.numerator), 'denominator': str(v.denominator)}


def scalar(v):
    if type(v) is int:
        return {'integer': str(v)}
    if math.isfinite(v):
        return {'binary_float_hex': v.hex()}
    return {'nonfinite': 'nan' if math.isnan(v) else ('+inf' if v > 0 else '-inf')}


def segments(clock):
    """Original-order maximal finite strictly increasing runs; never sort."""
    result, start, active = [], None, []
    for i, value in enumerate(clock):
        if not finite(value):
            if active:
                result.append((start, i, active))
            start, active = None, []
            continue
        value = rational(value)
        if active and value <= active[-1]:
            result.append((start, i, active))
            start, active = None, []
        if not active:
            start = i
        active.append(value)
    if active:
        result.append((start, len(clock), active))
    return result


def clock_diagnostics(clock, fps):
    nominal = 1 / rational(fps) if finite(fps) and fps > 0 else None
    histogram, breaks, comparisons = {}, [], {'below': 0, 'equal': 0, 'above': 0, 'above_two': 0}
    missing = 0
    for i in range(1, len(clock)):
        left, right = clock[i-1:i+1]
        if not (finite(left) and finite(right)):
            missing += 1
            continue
        gap = rational(right)-rational(left)
        if gap <= 0:
            breaks.append({'left_index': i-1, 'right_index': i, 'left': scalar(left),
                           'right': scalar(right), 'difference_seconds': ratio(gap)})
        else:
            histogram[gap] = histogram.get(gap, 0)+1
            if nominal is not None:
                comparisons['below' if gap < nominal else 'equal' if gap == nominal else 'above'] += 1
                comparisons['above_two'] += gap > 2*nominal
    return {'positive_gap_distribution': [{'gap_seconds': ratio(g), 'count': n}
                                          for g, n in sorted(histogram.items())],
            'positive_edges': sum(histogram.values()), 'nonincreasing_edges': breaks,
            'adjacent_edges_with_nonfinite_endpoint': missing,
            'declared_fps': scalar(fps), 'nominal_interval_seconds': ratio(nominal) if nominal else None,
            'positive_gap_vs_declared_interval': comparisons if nominal else None,
            'strict_finite_runs': [[a, b] for a, b, _ in segments(clock)],
            'clock_repaired': False, 'sampling_rate_inferred': False,
            'gap_comparison_is_not_eligibility': True}


def command_boundaries(values, clock):
    runs, active = [], None
    for i in range(len(values)+1):
        ok = i < len(values) and finite(values[i])
        if ok and active is None:
            active = i
        if not ok and active is not None:
            end = i-1
            runs.append({'start_index': active, 'end_index_exclusive': i,
                         'first_state': scalar(values[active]), 'last_state': scalar(values[end]),
                         'left_state_nonzero_without_observed_onset': values[active] != 0,
                         'right_state_nonzero_without_observed_offset': values[end] != 0,
                         'left_missing_command_boundary': active > 0,
                         'right_missing_command_boundary': i < len(values),
                         'first_clock': scalar(clock[active]) if active < len(clock) else None,
                         'last_clock': scalar(clock[end]) if end < len(clock) else None})
            active = None
    return {'finite_command_runs': runs, 'command_elements': len(values),
            'clock_elements': len(clock), 'length_match': len(values) == len(clock),
            'physical_censoring_not_inferred': True}


def window_support(runs, anchor, before, after):
    """Diagnostic sample support in (anchor-before, anchor+after].

    Each original strict run is reported independently, including overlapping
    clock ranges after resets. Bracketing does not imply continuous coverage.
    """
    lower, upper = anchor-before, anchor+after
    rows = []
    for start, end, values in runs:
        first, stop = bisect_right(values, lower), bisect_right(values, upper)
        brackets = values[0] <= lower and values[-1] >= upper
        if first != stop or brackets:
            rows.append({'clock_run': [start, end], 'sample_range': [start+first, start+stop],
                         'sample_count': stop-first, 'run_brackets_both_boundaries': brackets})
    return {'lower_open_seconds': ratio(lower), 'upper_closed_seconds': ratio(upper),
            'original_run_support': rows, 'coverage_fraction': None, 'eligibility': None}


def falling_edge_windows(command, clock):
    runs = segments(clock)
    result = []
    for i in range(1, len(command)):
        if not (finite(command[i-1]) and finite(command[i]) and command[i-1] != 0 and command[i] == 0):
            continue
        valid = i < len(clock) and finite(clock[i-1]) and finite(clock[i]) and clock[i-1] < clock[i]
        row = {'left_index': i-1, 'right_index': i, 'strict_finite_clock_bracket': valid,
               'anchor_interpretation': 'both_observed_command_bracket_endpoints_not_physical_offset',
               'endpoint_windows': None}
        if valid:
            row['endpoint_windows'] = [{
                'endpoint': label, 'anchor_seconds': ratio(rational(clock[index])),
                'history_10s': window_support(runs, rational(clock[index]), 10, 0),
                'goal_1s': window_support(runs, rational(clock[index]), 1, 0),
                'horizon_5s': window_support(runs, rational(clock[index]), 0, 5)}
                for label, index in (('left', i-1), ('right', i))]
        result.append(row)
    return {'observed_nonzero_to_zero_changes': result, 'control_pseudo_offsets': None,
            'physical_offsets': None, 'outcome_values_read_for_diagnostics': False,
            'eligibility_assigned': False}


def describe(values):
    clock = values['calc_ts']
    return {'behavior_clock': clock_diagnostics(clock, values['fps'][0]),
            'imaging_clock': clock_diagnostics(values['dff_ts'], float('nan')),
            'imaging_clock_status': 'released_nominal_clock_not_hardware_qualified',
            'command_boundaries': {k: command_boundaries(values[k], clock)
                                   for k in ('odor', 'wind', 'plume_valve')},
            'odor_command_window_boundaries': falling_edge_windows(values['odor'], clock),
            'biological_animal': None, 'condition': None, 'physical_offsets': None,
            'trial_retained': True, 'scientific_admission': False}
