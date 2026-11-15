"""Invented runtime compatibility probe; no real inputs, references or fits.

Use the same selected image as both candidates. This is separate from a
candidate program and does not qualify native FieldTrip or scientific results.
"""
import hashlib
import json
import math
import platform
import random


def observe():
    rng = random.Random(20261114)
    # The complete 2000 by 15 schedule, including randrange rejection behavior.
    schedule = bytes(rng.randrange(15) for _ in range(2000 * 15))
    reset = random.Random(20261114)
    reset_schedule = bytes(reset.randrange(15) for _ in range(2000 * 15))
    cases = ([1e16, 1.0, -1e16], [1.0, 2.0**-53, 2.0**-53],
             [float.fromhex('0x1.0000000000001p-1022'), -2.0**-1022],
             [0.5, -0.5, 0.0], [1.25, -2.5, 3.75, -5.0, 6.25])
    arithmetic = {
        'fsum_hex': [math.fsum(values).hex() for values in cases],
        'ulp_hex': [math.ulp(x).hex() for x in (0.0, 1.0, 15.0, 2.0**-1022)],
        'sqrt_hex': [math.sqrt(x).hex() for x in (2.0, 14.0, 15.0)],
    }
    conventions = {
        'draws': 2000, 'positions': 15, 'seed': 20261114,
        'complete_schedule_bytes': len(schedule),
        'schedule_sha256': hashlib.sha256(schedule).hexdigest(),
        'reset_repeats_complete_schedule': reset_schedule == schedule,
        'arithmetic': arithmetic,
    }
    encoded = json.dumps(conventions, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return {'schema': 'tms_fixed_region_runtime_conventions_v1',
            'runtime': {'implementation': platform.python_implementation(),
                        'version': platform.python_version()},
            'conventions': conventions,
            'conventions_sha256': hashlib.sha256(encoded).hexdigest(),
            'authentic_input_or_reference_reads': 0,
            'scope': 'Invented method primitives only; not scientific parity.'}


def paired(values):
    n = len(values); mean = math.fsum(values) / n
    sd = math.sqrt(math.fsum((v - mean)**2 for v in values) / (n - 1))
    sem = sd / math.sqrt(n)
    return {'mean': mean, 'sample_sd': sd, 'standard_error': sem,
            't': mean / sem if sem else None, 'cohens_dz': mean / sd if sd else None,
            'degenerate': None if sd else ('all_zero' if not mean else 'constant_nonzero')}


def infer(values):
    observed = abs(math.fsum(values))
    tolerance = 32 * math.ulp(math.fsum(abs(v) for v in values))
    extreme = 0
    for mask in range(32768):
        transformed = math.fsum((1 if mask & (1 << i) else -1) * value
                                for i, value in enumerate(values))
        extreme += abs(transformed) >= observed - tolerance
    rng = random.Random(20261114)
    means = sorted(math.fsum(values[rng.randrange(15)] for _ in range(15)) / 15
                   for _ in range(2000))
    def quantile(q):
        at = (len(means) - 1) * q; lower = math.floor(at); part = at - lower
        return means[lower] + (means[min(lower + 1, len(means) - 1)] - means[lower]) * part
    return {'paired': paired(values),
            'sign_flip': {'extreme': extreme, 'p_two_sided': extreme / 32768},
            'bootstrap': {'lower': quantile(.025), 'upper': quantile(.975)},
            'leave_one_out': [{'excluded_position': i, 'paired': paired(values[:i] + values[i+1:])}
                              for i in range(15)]}


def method_fixture(include_artifact=False):
    """All twelve regions on a small invented tensor, including exact edges.

    Seven channels and fifteen positions are retained. The deliberately small
    frequency/time grid is an engineering fixture, never an authentic subset.
    """
    labels = ['O1', 'PO7', 'PO3', 'P1', 'P3', 'P5', 'P7']
    frequencies = [7.999, 8.0, 10.0, 12.0, 13.0, 30.0, 30.001]
    times = [.49, .5, 1.0, 1.5, 1.51, 2.99, 3.0, 3.5, 4.0, 4.5, 4.51]
    bands = [('alpha', (8, 12)), ('beta', (13, 30))]
    windows = [('early', (.5, 1.5)), ('late', (3, 4)), ('extended_late', (3, 4.5))]
    def value(condition, channel, frequency, time_index, position):
        f = frequencies[frequency]; t = times[time_index]
        if not (8 <= f <= 30 and .5 <= t <= 4.5):
            return float('nan')
        base = (channel - 3) / 4 + frequency / 16 + time_index / 32 + (position - 7) / 8
        pin_delta = (0.0 if f <= 12 and t <= 1.5 else
                     (position - 7) / 8 + (channel == 6) / 16 + frequency / 32 + time_index / 64)
        pout_delta = (.125 if f <= 12 and t <= 1.5 else
                      (position - 6) / 16 - (channel == 6) / 32 - frequency / 64)
        return base + (0.25 if condition in (1, 3) else 0) + (
            pin_delta if condition == 2 else pout_delta if condition == 3 else 0)
    regions = []
    for roi, channels in [('primary6', range(6)), ('sensitivity7', range(7))]:
        for band, (flow, fhigh) in bands:
            fi = [i for i, f in enumerate(frequencies) if flow <= f <= fhigh]
            for window, (low, high) in windows:
                ti = [i for i, t in enumerate(times) if low <= t <= high]
                means = []
                for condition in range(4):
                    means.append([math.fsum(value(condition, c, f, t, person)
                        for c in channels for f in fi for t in ti) / (len(channels)*len(fi)*len(ti))
                        for person in range(15)])
                pin = [t - nt for t, nt in zip(means[2], means[0])]
                pout = [t - nt for t, nt in zip(means[3], means[1])]
                effects = []
                for eid, differences in [('pin_T_minus_NT', pin), ('pout_T_minus_NT', pout),
                        ('location_interaction', [a - b for a, b in zip(pin, pout)])]:
                    effects.append({'id': eid, 'differences': differences, **infer(differences)})
                regions.append({'id': '/'.join((roi, band, window)), 'condition_means': means,
                                'selected_frequency_indices': fi, 'selected_time_indices': ti,
                                'effects': effects})
    order = sorted((e['sign_flip']['p_two_sided'], r['id'] + '/' + e['id'], e)
                   for r in regions for e in r['effects'])
    previous = 0.0
    for i, (p, _, effect) in enumerate(order):
        previous = max(previous, min(1.0, (36-i)*p)); effect['holm_p'] = previous
    # A cancellation-sensitive sign-flip vector also exercises the exact
    # comparison tolerance; the result is not taken from neuroscience data.
    edge_values = [1e16, -1e16, 256, 128, 64, 32, 16, 8, 4, 2, 1, .5, .25, .125, .0625]
    sign_edge = infer(edge_values)
    observed = abs(math.fsum(edge_values))
    no_tolerance = sum(abs(math.fsum((1 if mask & (1 << i) else -1) * value
                       for i, value in enumerate(edge_values))) >= observed
                       for mask in range(32768))
    assert 0 < sign_edge['sign_flip']['extreme'] < 32768
    assert no_tolerance != sign_edge['sign_flip']['extreme']
    sign_edge['invented_threshold_control'] = {
        'values': edge_values, 'observed_absolute_sum': observed,
        'without_tolerance_extreme': no_tolerance,
        'with_tolerance_extreme': sign_edge['sign_flip']['extreme'],
        'nontrivial_and_tolerance_sensitive': True}
    result = {'fixture': 'invented_full12_region_edge_grid_v1', 'labels': labels,
              'frequency': frequencies, 'time': times, 'regions': regions, 'sign_edge': sign_edge}
    body = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    summary = {'schema': 'tms_fixed_region_method_fixture_v1',
            'complete_artifact_bytes': len(body), 'complete_artifact_sha256': hashlib.sha256(body).hexdigest(),
            'regions': len(regions), 'effects': sum(len(r['effects']) for r in regions),
            'omissions': sum(len(e['leave_one_out']) for r in regions for e in r['effects']),
            'sign_patterns_each': 32768, 'bootstrap_draws_each': 2000,
            'complete_artifact_is_invented': True,
            'authentic_shape_or_scientific_parity_claim': False}
    return (summary, body) if include_artifact else summary


if __name__ == '__main__':
    primitive = observe()
    print(json.dumps({'schema': 'tms_whole_runtime_compatibility_v1',
        'runtime': primitive['runtime'], 'primitive': primitive,
        'method_fixture': method_fixture(), 'authentic_payload_reads': 0},
        sort_keys=True, allow_nan=False))


