"""Continuous fixed-axis velocity metrics; no scientific pass threshold."""
import numpy as np


def metrics(target, prediction):
    if target.shape != prediction.shape or target.ndim != 2 or target.shape[1] != 2 or not len(target):
        raise ValueError('Aligned nonempty two-axis vectors required')
    if not np.isfinite(target).all() or not np.isfinite(prediction).all():
        raise ValueError('Finite targets and predictions required')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        residual = prediction - target
        squared_error = np.sum(residual * residual, axis=0, dtype=np.float64)
        absolute_error = np.sum(np.abs(residual), axis=0, dtype=np.float64)
        centered = target - target.mean(axis=0)
        squared_total = np.sum(centered * centered, axis=0, dtype=np.float64)
        constant = np.all(target == target[0], axis=0)
        squared_total[constant] = 0.0
        r2 = [None if squared_total[i] == 0 else float(1 - squared_error[i] / squared_total[i])
              for i in range(2)]
        primary = None if any(value is None for value in r2) else float(sum(r2) / 2)
    result = {'rows': len(target), 'r2_by_axis': r2, 'mean_axis_r2': primary,
              'mse_by_axis': (squared_error / len(target)).tolist(),
              'mae_by_axis': (absolute_error / len(target)).tolist(),
              'mse': float(squared_error.sum() / (2 * len(target))),
              'mae': float(absolute_error.sum() / (2 * len(target))),
              'zero_sst_axes': [i for i in range(2) if squared_total[i] == 0]}
    if not all(np.isfinite(x) for key in ('mse', 'mae') for x in (result[key],)):
        raise ValueError('Metrics cannot overflow to nonfinite values')
    return result


def score(target, streams):
    overall = {arm: metrics(target, prediction) for arm, prediction in streams.items()}
    blocks = []
    for block, begin in enumerate(range(0, len(target), 3000)):
        end = min(len(target), begin + 3000)
        blocks.append({'block': block, 'row_start': begin, 'row_stop_exclusive': end,
                       'metrics': {arm: metrics(target[begin:end], prediction[begin:end])
                                   for arm, prediction in streams.items()}})
    signed = {}
    for arm, value in overall.items():
        signed[arm] = {}
        for comparator, reference in overall.items():
            signed[arm][comparator] = {
                'candidate_minus_reference_r2': None if value['mean_axis_r2'] is None or reference['mean_axis_r2'] is None
                else value['mean_axis_r2'] - reference['mean_axis_r2'],
                'reference_minus_candidate_mse': reference['mse'] - value['mse'],
                'reference_minus_candidate_mae': reference['mae'] - value['mae']}
    return {'primary_metric': 'mean_axis_r2', 'metrics': overall, 'fixed_clock_blocks': blocks,
            'signed_comparisons': signed, 'binary_scientific_success': None,
            'primary_defined_for_all_streams': all(value['mean_axis_r2'] is not None for value in overall.values()),
            'biological_independent_units': 1, 'unseen_final_evaluation': False}
