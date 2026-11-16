"""Independent scalar arithmetic on saved predictions; imports no scoring core."""
import math


def calculate(target, prediction):
    n = len(target)
    if n == 0 or len(prediction) != n:
        raise ValueError('Exact nonempty scalar vectors')
    axis = []
    for coordinate in (0, 1):
        truth = [float(row[coordinate]) for row in target]
        guessed = [float(row[coordinate]) for row in prediction]
        if not all(math.isfinite(x) for x in truth + guessed):
            raise ValueError('Finite scalar audit inputs')
        average = math.fsum(truth) / n
        sst = 0.0 if all(x == truth[0] for x in truth) else math.fsum((x - average) ** 2 for x in truth)
        errors = [p - y for p, y in zip(guessed, truth)]
        mse = math.fsum(x * x for x in errors) / n
        mae = math.fsum(abs(x) for x in errors) / n
        axis.append({'r2': None if sst == 0 else 1 - mse * n / sst, 'mse': mse, 'mae': mae, 'sst': sst})
    return {'rows': n, 'r2_by_axis': [x['r2'] for x in axis],
            'mean_axis_r2': None if any(x['r2'] is None for x in axis) else math.fsum(x['r2'] for x in axis) / 2,
            'mse_by_axis': [x['mse'] for x in axis], 'mae_by_axis': [x['mae'] for x in axis],
            'mse': math.fsum(x['mse'] for x in axis) / 2, 'mae': math.fsum(x['mae'] for x in axis) / 2,
            'zero_sst_axes': [i for i, value in enumerate(axis) if value['sst'] == 0]}


def audit(target, streams, saved):
    checks = 0

    def same(actual, expected):
        nonlocal checks
        checks += 1
        if expected is None:
            if actual is not None:
                raise ValueError('Undefined score must remain undefined')
        elif not isinstance(actual, (float, int)) or not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError('Independent saved arithmetic mismatch')

    def compare(value, fresh):
        for key in ('rows', 'mean_axis_r2', 'mse', 'mae'):
            same(value[key], fresh[key])
        for key in ('r2_by_axis', 'mse_by_axis', 'mae_by_axis'):
            if len(value[key]) != 2:
                raise ValueError('Both fixed axes required')
            for a, b in zip(value[key], fresh[key]):
                same(a, b)
        if value['zero_sst_axes'] != fresh['zero_sst_axes']:
            raise ValueError('Constant-axis declaration mismatch')

    recomputed = {arm: calculate(target, prediction) for arm, prediction in streams.items()}
    if set(saved['metrics']) != set(streams):
        raise ValueError('All reference streams required')
    for arm in streams:
        compare(saved['metrics'][arm], recomputed[arm])
    if len(saved['fixed_clock_blocks']) != math.ceil(len(target) / 3000):
        raise ValueError('Every fixed block including final remainder required')
    for number, row in enumerate(saved['fixed_clock_blocks']):
        begin, end = number * 3000, min(len(target), (number + 1) * 3000)
        if (row['block'], row['row_start'], row['row_stop_exclusive']) != (number, begin, end):
            raise ValueError('Fixed block boundaries changed')
        for arm, prediction in streams.items():
            compare(row['metrics'][arm], calculate(target[begin:end], prediction[begin:end]))
    for arm, candidate in recomputed.items():
        for name, reference in recomputed.items():
            value = saved['signed_comparisons'][arm][name]
            same(value['candidate_minus_reference_r2'], None if candidate['mean_axis_r2'] is None or reference['mean_axis_r2'] is None else candidate['mean_axis_r2'] - reference['mean_axis_r2'])
            same(value['reference_minus_candidate_mse'], reference['mse'] - candidate['mse'])
            same(value['reference_minus_candidate_mae'], reference['mae'] - candidate['mae'])
    return {'status': 'independent_saved_metric_arithmetic_pass', 'scalar_checks': checks,
            'absolute_tolerance': 1e-10, 'relative_tolerance': 1e-10,
            'limits': 'Saved metric arithmetic only; no refit, biological validation or population uncertainty.'}
