"""Portable copies of the accepted five independent scientific witnesses.

The private registry-integration check and absolute-path report writer are not
public runtime dependencies. Numerical witness function bodies are unchanged.
"""
import copy
from fractions import Fraction
import math
import struct
import unittest

import fullfield
import test_fullfield
f = fullfield

def refused(call):
    try:
        call()
    except f.ConstructionError:
        return
    raise AssertionError('Expected construction refusal')

def represented(bits, width):
    return struct.unpack('>f' if width == 32 else '>d', bits.to_bytes(width // 8, 'big'))[0]

def rounding_neighbor_witnesses():
    count = 0
    for width, dtype, mantissa, emax in ((32, 'binary32', 23, 127), (64, 'binary64', 52, 1023)):
        # Distances to adjacent representable values supply an independent oracle.
        # No conversion through binary64 is used to choose a binary32 midpoint.
        exponents = [0, 1, 2, 3, 17, (1 << (width - mantissa - 1)) // 2,
                     (1 << (width - mantissa - 1)) - 3]
        for exp in exponents:
            for frac in (0, 1, 2, 3, (1 << mantissa) // 2 - 1, (1 << mantissa) - 2):
                bits = (exp << mantissa) | frac
                a, b = represented(bits, width), represented(bits + 1, width)
                midpoint = (Fraction(a) + Fraction(b)) / 2
                epsilon = (Fraction(b) - Fraction(a)) / (1 << 60)
                even = a if bits % 2 == 0 else b
                assert f.rounded(midpoint, dtype) == even
                assert f.rounded(midpoint - epsilon, dtype) == a
                assert f.rounded(midpoint + epsilon, dtype) == b
                assert f.rounded(-midpoint, dtype) == -even
                count += 4
        maximum = Fraction((1 << (mantissa + 1)) - 1) * Fraction(2) ** (emax - mantissa)
        threshold = maximum + Fraction(2) ** (emax - mantissa - 1)
        assert math.isinf(f.rounded(threshold, dtype))
        assert Fraction(f.rounded(threshold - Fraction(2) ** (emax - mantissa - 20), dtype)) == maximum
        tiny = Fraction(represented(1, width))
        assert f.rounded(tiny / 2, dtype) == 0
        assert math.copysign(1, f.rounded(-tiny / 2, dtype)) == -1
        assert f.rounded(3 * tiny / 2, dtype) == represented(2, width)
        count += 5
    return {'adjacent_value_and_boundary_assertions': count}

def separate_arithmetic_witnesses():
    for dtype, p in (('binary32', 24), ('binary64', 53)):
        m, b = math.ldexp(1.0, -(p - 1)), 3.0
        assert f.delta_pixel(m, b, dtype) == -1.0
        # The exact whole expression rounds differently: subtraction must round first.
        exact = (Fraction(m) - Fraction(b)) / Fraction(b)
        assert f.rounded(exact, dtype) == -1.0 + math.ldexp(1.0, -p)
        refused(lambda: f.delta_pixel(True, 1, dtype))
        for invalid in ('nan', '+inf', '-inf'):
            assert f.delta_pixel(invalid, b, dtype) is None
        assert f.delta_pixel(1, -0.0, dtype) is None
    return {'formats': 2, 'separate_subtraction_witnesses': 2, 'unreassociated_result': -1}

def quantizer_exact_boundaries():
    # s=255 makes every half-bin boundary an exact integer source value.
    for k in range(1, 256):
        d = float(2 * k - 256)
        assert f.encode(d, 255)[0] == (k,) * 3
        assert f.encode(math.nextafter(d, -math.inf), 255)[0] == (k - 1,) * 3
        assert f.encode(math.nextafter(d, math.inf), 255)[0] == (k,) * 3
    for d in range(-765, 766):
        value = Fraction(d, 2)
        pixel, saturated = f.encode(float(value), 255)
        assert saturated == (abs(value) > 255)
        decoded = Fraction(255) * (Fraction(2 * pixel[0], 255) - 1)
        if not saturated:
            assert abs(decoded - value) <= 1
    assert f.encode(None, 255) == ((255, 0, 255), False)
    refused(lambda: f.encode(float('nan'), 255))
    return {'half_bin_boundaries': 255, 'reconstruction_cases': 1531, 'invalid_mask': 'magenta'}

def complete_interval_witnesses():
    timing = dict(cue=0, memory_start=2, memory_end=4, go=5,
                  baseline_start=-2, baseline_end=-1, acquisition_start=3, acquisition_end=4)
    intervals = [(-4, -3, True), (3, 4, True), (-2, -1, True), (-1, 0, True),
                 (1, 3.5, True), (3.5, 4.5, True), (3.5, 4, False)]
    frames = [dict(frame_id='generated-' + str(i), source_order=i, start=a, end=b,
                   complete=c, pixels=[1]) for i, (a, b, c) in enumerate(intervals)]
    base, memory = f.select_frames(frames, timing)
    assert base is frames[2] and memory is frames[1]
    tied = frames + [dict(frame_id='tie', source_order=len(frames), start=2.5,
                          end=4, complete=True, pixels=[999])]
    refused(lambda: f.select_frames(tied, timing))
    missing = copy.deepcopy(frames)
    missing[1]['complete'] = False
    refused(lambda: f.select_frames(missing, timing))
    return {'nonchronological_catalogue_order': 'latest eligible end selected',
            'crossing_and_incomplete_frames': 'excluded from selection', 'ambiguous_latest': 'refused'}

def complete_fold_nontrivial_calibration():
    # Reuse only the author's all-roster invented fixture constructor, not its tests.
    intake = test_fullfield.invented_intake()
    positive = [r for r in intake['records'] if r['trials']]
    held = positive[-1]
    train = positive[:-1]
    maximum_record = train[-1]['record_id']
    for n, r in enumerate(positive):
        r['native_hz'] = 1 if n % 2 else 2
        for i in range(16):
            r['trials'][i]['direction'] = i // 2
    for r in (held, train[0]):
        t = r['trials'][16]
        t.update(disposition='adjudicated_excluded', query_id=None, direction=None,
                 timing=None, exclusion_reason='missing_timing',
                 adjudication_sha256=intake['intake_review_sha256'])
    lookup = {r['record_id']: r for r in positive}
    calls, outputs = [], []

    def load(rid):
        calls.append(rid)
        r = lookup[rid]
        trials = []
        for i, t in enumerate(r['trials']):
            if t['disposition'] == 'adjudicated_excluded':
                frames = None
            else:
                memory = [42, 1, -14] if r is held else [4, 5, -2]
                if rid == maximum_record and i == len(r['trials']) - 1:
                    memory = [18, 5, -2]
                frames = [dict(frame_id='base', source_order=0, start=-2, end=-1,
                               complete=True, pixels=[2, 0, 2]),
                          dict(frame_id='memory', source_order=1, start=2, end=3,
                               complete=True, pixels=memory),
                          dict(frame_id='not-eligible', source_order=2, start=3, end=4,
                               complete=False, pixels=[999, 999, 999])]
            trials.append(dict(source_trial_id=t['source_trial_id'], source_order=i, frames=frames))
        return dict(schema='fus_normalized_fullfield_record_v1', record_id=rid,
                    native_hz=r['native_hz'], source_float='binary64' if r is held else 'binary32',
                    shape=[1, 3], spatial_pitch=[0.25, 0.5], spatial_pitch_unit='mm',
                    acquisition_census_sha256='b' * 64, trials=trials)

    def emit(payload):
        assert payload['shape'] == [1, 3] and payload['rgb'] == bytes([255,255,255,255,0,255,0,0,0])
        assert payload['invalid_pixels'] == payload['saturated_pixels'] == 1
        assert payload['scale'] == 8 and payload['source_float'] == 'binary64'
        keys = {'schema','fold_key','query_id','role','scale','shape','spatial_pitch',
                'spatial_pitch_unit','native_hz','source_float','rgb','invalid_pixels','saturated_pixels'}
        assert set(payload) == keys | ({'direction'} if payload['role'] == 'calibration' else set())
        outputs.append((payload['query_id'], payload['role'], payload.get('direction')))

    receipt = f.prepare_fold(intake, load, emit, held_record_id=held['record_id'], fold_key='fold_'+'9'*32)
    assert calls == [r['record_id'] for r in train] + [held['record_id']]
    assert len(calls) == 48 and len(set(calls)) == 48
    expected = [(held['trials'][i]['query_id'], 'calibration', i // 2) for i in range(0, 16, 2)]
    assert [v for v in outputs if v[1] == 'calibration'] == expected
    assert outputs[1][1] == 'query' and outputs[14][1] == 'calibration'
    assert receipt['scale'] == 8 and receipt['training_records'] == 47
    assert receipt['training_maps'] == 20622 - len(held['trials']) - 1
    assert receipt['training_valid_pixels'] == 2 * receipt['training_maps']
    assert receipt['training_invalid_pixels'] == receipt['training_maps']
    assert receipt['held_adjudicated_exclusions'] == 1
    assert receipt['calibration_maps'] == 8 and receipt['query_maps'] == len(held['trials']) - 9
    assert receipt['roster_records'] == 49 and receipt['declared_source_trials'] == 20622
    assert all(receipt[k] is False for k in ('native_source_authenticated', 'full_resolution_delivery_qualified',
                                            'protected_evaluation_established', 'scientifically_qualified'))
    # Unselected pixels cannot silently have a smaller native field.
    malformed = load(held['record_id'])
    malformed['trials'][0]['frames'][2]['pixels'] = [1]
    refused(lambda: next(f.record_deltas(held, malformed)))
    return {'roster_records':49, 'declared_slots':20622, 'training_records':47,
            'fixed_exclusions':2, 'late_training_maximum':8,
            'calibration_source_positions':list(range(0,16,2)), 'receipt':receipt,
            'unselected_frame_cropping':'refused'}

class IndependentScientificChecks(unittest.TestCase):
    def test_rounding_neighbors(self):
        rounding_neighbor_witnesses()

    def test_separate_arithmetic(self):
        separate_arithmetic_witnesses()

    def test_quantizer(self):
        quantizer_exact_boundaries()

    def test_intervals(self):
        complete_interval_witnesses()

    def test_full_fold_calibration(self):
        complete_fold_nontrivial_calibration()


if __name__ == '__main__':
    if __debug__ is not True:
        raise RuntimeError('controls require assertions enabled')
    unittest.main()
