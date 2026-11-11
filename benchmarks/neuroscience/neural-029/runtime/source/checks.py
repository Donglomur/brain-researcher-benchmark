"""Invented numerical and complete-submission boundary checks only."""
import copy
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
import prepare
from source_identity_join import bind_public_identity
from inert_checks import raw_fixture
from timing import fixed_warp_mean


def run(np):
    start = time.monotonic(); checks = []
    def ck(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    public = {'pairs': [{'pair_id': str(i), 'query_ids': ['q0', 'q1'], 'cell_ids': ['c0'],
              'calibration_trials': 4, 'validation_trials': 1, 'source_delay_seconds': 1,
              'target_delay_seconds': 2, 'reward_type': 'DAT'} for i in range(3)]}
    identity = bind_public_identity(raw_fixture(), public, '0' * 64)
    y = np.tile(np.arange(61, dtype=float), (2, 1, 1))
    private = [{'pair_id': str(i), 'mouse_id': 'A' if i < 2 else 'B', 'target': y,
                'baseline': y[0], 'fixed_warp_baseline': y[0] + 1, 'training_scale_squared': 1.0} for i in range(3)]
    doc = {'schema': 'neural029-predictions-v1', 'predictions': [
        {'pair_id': str(i), 'values': (y + (0 if i < 2 else 3)).tolist()} for i in range(3)]}
    calls = []
    def get():
        calls.append(1); return {'pairs': private, 'identity': identity}
    answer = core.grade(doc, public, get, np)
    ck('mouse_macro_not_pair_weighted', answer['primary_nrmse'] == 1.5 and answer['baseline_nrmse'] == 0)
    ck('paired_mouse_differences', answer['mice'][0]['candidate_minus_fixed_warp'] == -1 and answer['mice'][1]['candidate_minus_fixed_warp'] == 2)
    ck('per_pair_r2_uses_target_cell_centering', abs(answer['pairs'][2]['r_squared'] - (1 - 9 / 310)) < 1e-14)
    for name, mutate in [
        ('last_boolean_rejected_before_private', lambda d: d['predictions'][-1]['values'][0][0].__setitem__(0, True)),
        ('last_missing_cell_rejected_before_private', lambda d: d['predictions'][-1]['values'].__setitem__(0, [])),
        ('duplicate_pair_rejected_before_private', lambda d: d['predictions'][-1].__setitem__('pair_id', '0'))]:
        wrong = copy.deepcopy(doc); mutate(wrong); calls.clear()
        try: core.grade(wrong, public, get, np)
        except ValueError: ck(name, calls == [])
        else: raise AssertionError(name)
    private[-1]['training_scale_squared'] = 0
    ck('undefined_scale_propagates_without_dropping_mouse', core.grade(doc, public, get, np)['primary_nrmse'] is None)
    private[-1]['training_scale_squared'] = 1
    wrong = copy.deepcopy(doc); wrong['predictions'][-1]['values'][0][0][0] = 1e308
    try: core.grade(wrong, public, get, np)
    except (ValueError, OverflowError, FloatingPointError): checks.append('overflow_rejected_without_partial_grade')
    else: raise AssertionError('overflow')
    t = np.array([-.1, .4, 1.1, 2.7, 3.2]); x = (7 + 2 * t)[None, None]
    projected = prepare.interpolate(x, t, np)
    ck('nonuniform_clock_linear_interpolation', np.allclose(projected[0, 0], 7 + 2 * np.arange(61) / 20, atol=1e-14))
    try: prepare.interpolate(x, t + 1, np)
    except ValueError: checks.append('clock_extrapolation_rejected')
    else: raise AssertionError('extrapolation')
    grid = [i / 20 for i in range(61)]
    warp = fixed_warp_mean((7 + 2 * np.array(grid))[None], grid, grid, np)
    ck('fixed_warp_boundary_and_support', warp[0, 0] == 7 and warp[0, 40] == 9 and warp[0, 60] == 11)
    return {'schema': 'neural029-generated-checks-v1', 'status': 'passed', 'count': len(checks),
        'checks': checks, 'numpy': np.__version__, 'elapsed_seconds': time.monotonic() - start,
        'empirical_payloads_read': 0, 'model_fits': 0, 'empirical_scores': 0, 'invented_only': True}


if __name__ == '__main__':
    import numpy as np
    print(json.dumps(run(np), indent=2))
