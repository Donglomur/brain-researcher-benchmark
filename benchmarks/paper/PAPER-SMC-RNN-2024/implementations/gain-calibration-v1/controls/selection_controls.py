"""Tiny generated checks against the original canonical co-bps implementation.

The independent oracle is test-only. Neither generated rates nor generated
score rows claim original-data admission or a scientific improvement result.
"""
from __future__ import annotations

import copy
import hashlib
import math
import types
import warnings


def exercise_selection(case, selector, transform, oracle, evaluator_path):
    import numpy as np
    raw = evaluator_path.read_bytes()
    case.assertEqual({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
                     oracle.EVALUATOR_SOURCE)
    evaluator = types.ModuleType('_gain_control_original_evaluator')
    evaluator.__file__ = str(evaluator_path)
    exec(compile(raw, str(evaluator_path), 'exec'), evaluator.__dict__)
    score_calls = 0
    oracle_calls = 0
    grid_calls = 0
    for fixture in oracle.fixture_cases():
        rates = np.asarray(fixture['rates'], dtype=np.float64)
        spikes = np.asarray(fixture['spikes'], dtype=np.float64)
        untouched = rates.tobytes(), spikes.tobytes()
        actual = evaluator.bits_per_spike(rates.copy(), spikes.copy())
        expected = oracle.oracle_bits_per_spike(fixture['rates'], fixture['spikes'])
        case.assertAlmostEqual(float(actual), expected, places=12)
        case.assertEqual((rates.tobytes(), spikes.tobytes()), untouched)
        score_calls += 1
        oracle_calls += 1
    for dtype in (np.float32, np.float64):
        fixture = oracle.binary_power_grid_case()
        rates = np.asarray(fixture['rates'], dtype=dtype)
        spikes = np.asarray(fixture['spikes'], dtype=np.float64)
        rates.flags.writeable = False
        spikes.flags.writeable = False
        untouched = rates.tobytes(), spikes.tobytes()
        result = selector._score_grid(rates, spikes, evaluator, transform)
        case.assertEqual(result['selected']['index'], 8)
        case.assertEqual(result['selected']['gain'], [2, 1])
        case.assertEqual(len(result['scores']), 9)
        baseline = result['scores'][0]['co_bps']
        for index, row in enumerate(result['scores']):
            case.assertEqual(row['index'], index)
            case.assertEqual(row['gain'], list(oracle.ORDERED_GAIN_RATIONALS[index]))
            scaled = transform.scale_block(rates, row['gain'])
            expected = oracle.oracle_bits_per_spike(scaled.tolist(), spikes.tolist())
            case.assertAlmostEqual(row['co_bps'], expected, places=12)
            gain = float.fromhex(row['executed_gain']['value_hex'])
            delta = oracle.positive_gain_delta_oracle(rates.tolist(), spikes.tolist(), gain)
            case.assertAlmostEqual(row['co_bps'] - baseline, delta, places=12)
            case.assertEqual(scaled.dtype, rates.dtype)
            oracle_calls += 1
        case.assertEqual((rates.tobytes(), spikes.tobytes()), untouched)
        score_calls += 9
        grid_calls += 1
    fixture = oracle.zero_rate_identity_tie_case()
    rates = np.asarray(fixture['rates'], dtype=np.float32)
    spikes = np.asarray(fixture['spikes'], dtype=np.float64)
    rates.flags.writeable = False
    spikes.flags.writeable = False
    untouched = rates.tobytes(), spikes.tobytes()
    tied = selector._score_grid(rates, spikes, evaluator, transform)
    case.assertEqual(len({row['co_bps'] for row in tied['scores']}), 1)
    case.assertEqual(tied['selected']['index'], 0)
    case.assertEqual(tied['selected']['gain'], [1, 1])
    case.assertEqual((rates.tobytes(), spikes.tobytes()), untouched)
    score_calls += 9
    grid_calls += 1

    # Exact metadata tie policy is separate from the real numerical score test.
    rows = copy.deepcopy(tied['scores'])
    for index, row in enumerate(rows):
        row['co_bps'] = 2.0 if index in (2, 4) else 1.0
    case.assertEqual(selector.choose_best(rows)['index'], 2)
    rows[4]['co_bps'] = math.nextafter(2.0, math.inf)
    case.assertEqual(selector.choose_best(rows)['index'], 4)
    for bad in (math.inf, -math.inf, math.nan, 1, True):
        changed = copy.deepcopy(rows)
        changed[0]['co_bps'] = bad
        with case.assertRaises(ValueError):
            selector.choose_best(changed)
    for changed in (rows[::-1], rows[:-1]):
        with case.assertRaises(ValueError):
            selector.choose_best(changed)
    changed = copy.deepcopy(rows)
    changed[0]['index'] = False
    with case.assertRaises(ValueError):
        selector.choose_best(changed)

    # A genuine canonical zero-denominator result must never select a fallback.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        with case.assertRaisesRegex(ValueError, 'nonfinite canonical'):
            selector._score_grid(np.ones((1, 2, 1), dtype=np.float64),
                                 np.zeros((1, 2, 1), dtype=np.float64), evaluator, transform)
    score_calls += 1
    for bad in (np.array([[[math.nan]]]), np.array([[[-1.0]]]), np.array([[[math.inf]]])):
        with case.assertRaises(ValueError):
            selector._score_grid(bad, np.ones_like(bad), evaluator, transform)
    with case.assertRaises(ValueError):
        selector._score_grid(np.ones((1, 1, 1), dtype=np.float64),
                             np.full((1, 1, 1), math.inf), evaluator, transform)
    case.assertEqual(selector.PRODUCTION_SHAPE, (574, 35, 45))
    case.assertEqual(tuple(selector.GAIN_GRID), tuple(oracle.ORDERED_GAIN_RATIONALS))
    return {'canonical_score_calls': score_calls, 'independent_oracle_calls': oracle_calls,
            'actual_numerical_grid_calls': grid_calls, 'generated_score_metadata_ties': True,
            'original_evaluator_source': oracle.EVALUATOR_SOURCE,
            'named_source_read_bytes': len(raw), 'generated_numeric_work_bound_bytes': 131072,
            'generated_file_write_bytes': 0, 'original_data_accessed': False,
            'fixed_production_geometry_changed': False, 'scientific_improvement': False}
